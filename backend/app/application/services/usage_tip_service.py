from app.core.safe_html import sanitize_html
import base64
import html
import re
from datetime import datetime, timezone
from io import BytesIO

from docx import Document as DocxDocument
from docx.document import Document as _Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError

from app.application.schemas.auth_schemas import AccountResponse
from app.application.schemas.tip_schemas import (
    SaveUsageTipRequest,
    TipImportWordResponse,
    UsageTipDetailResponse,
    UsageTipListItemResponse,
)
from app.core.auth_scope import normalize_client_variant
from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError
from app.core.id_generator import generate_public_id
from app.infrastructure.db.models.auth import AuthAccountModel
from app.infrastructure.db.models.tip import UsageTipModel

class UsageTipService:
    def __init__(self, db):
        self._db = db
        self._variant = normalize_client_variant(settings.internal_auth_variant)

    def list_tips(
        self,
        query: str = "",
        account: AccountResponse | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UsageTipListItemResponse], int]:
        statement = (
            self._db.query(UsageTipModel)
            .join(AuthAccountModel, AuthAccountModel.id == UsageTipModel.author_account_id)
            .filter(AuthAccountModel.client_variant == self._variant)
        )
        if account is None:
            statement = statement.filter(UsageTipModel.is_published.is_(True))
        else:
            statement = statement.filter(
                (UsageTipModel.is_published.is_(True)) | (UsageTipModel.author_account_id == account.id)
            )

        normalized_query = (query or "").strip()
        if normalized_query:
            like_query = f"%{normalized_query}%"
            statement = statement.filter(
                (UsageTipModel.title.like(like_query)) | (UsageTipModel.plain_text.like(like_query))
            )

        total = statement.count()
        rows = (
            statement
            .order_by(UsageTipModel.updated_at.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return [self._to_list_item(row, account) for row in rows], total

    def get_tip(self, tip_id: str, account: AccountResponse | None = None) -> UsageTipDetailResponse:
        row = (
            self._db.query(UsageTipModel)
            .join(AuthAccountModel, AuthAccountModel.id == UsageTipModel.author_account_id)
            .filter(
                UsageTipModel.id == tip_id,
                AuthAccountModel.client_variant == self._variant,
            )
            .first()
        )
        if row is None:
            raise ResourceNotFoundError(f"Usage tip '{tip_id}' was not found.")
        if not row.is_published and (account is None or row.author_account_id != account.id):
            raise ResourceNotFoundError(f"Usage tip '{tip_id}' was not found.")
        return self._to_detail(row, account)

    def create_tip(self, payload: SaveUsageTipRequest, account: AccountResponse) -> UsageTipDetailResponse:
        now = self._now_millis()
        row = UsageTipModel(
            id=generate_public_id("tip"),
            title=payload.title.strip(),
            html_content=sanitize_html(payload.htmlContent),
            plain_text=self._extract_plain_text(payload.htmlContent),
            contributor_qq=payload.contributorQq.strip(),
            is_published=payload.isPublished,
            author_account_id=account.id,
            author_username=account.username,
            created_at=now,
            updated_at=now,
        )
        try:
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
        except SQLAlchemyError as exception:
            self._db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存使用技巧失败，请稍后重试。",
            ) from exception
        return self._to_detail(row, account)

    def update_tip(self, tip_id: str, payload: SaveUsageTipRequest, account: AccountResponse) -> UsageTipDetailResponse:
        row = (
            self._db.query(UsageTipModel)
            .join(AuthAccountModel, AuthAccountModel.id == UsageTipModel.author_account_id)
            .filter(
                UsageTipModel.id == tip_id,
                AuthAccountModel.client_variant == self._variant,
            )
            .first()
        )
        if row is None:
            raise ResourceNotFoundError(f"Usage tip '{tip_id}' was not found.")
        if row.author_account_id != account.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能编辑自己发布的使用技巧。")

        row.title = payload.title.strip()
        row.html_content = sanitize_html(payload.htmlContent)
        row.plain_text = self._extract_plain_text(payload.htmlContent)
        row.contributor_qq = payload.contributorQq.strip()
        row.is_published = payload.isPublished
        row.updated_at = self._now_millis()
        try:
            self._db.commit()
            self._db.refresh(row)
        except SQLAlchemyError as exception:
            self._db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存使用技巧失败，请稍后重试。",
            ) from exception
        return self._to_detail(row, account)

    def delete_tip(self, tip_id: str, account: AccountResponse) -> None:
        row = (
            self._db.query(UsageTipModel)
            .join(AuthAccountModel, AuthAccountModel.id == UsageTipModel.author_account_id)
            .filter(
                UsageTipModel.id == tip_id,
                AuthAccountModel.client_variant == self._variant,
            )
            .first()
        )
        if row is None:
            raise ResourceNotFoundError(f"Usage tip '{tip_id}' was not found.")
        if row.author_account_id != account.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能删除自己发布的使用技巧。")
        self._db.delete(row)
        self._db.commit()

    def import_word(self, upload: UploadFile) -> TipImportWordResponse:
        filename = (upload.filename or "").lower()
        if not filename.endswith(".docx"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目前仅支持导入 .docx 文档。")
        raw = upload.file.read()
        if not raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Word 文档内容为空。")

        try:
            document = DocxDocument(BytesIO(raw))
            html_content = self._convert_document_to_html(document).strip()
        except Exception as exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Word 文档解析失败。") from exception

        plain_text = self._extract_plain_text(html_content)
        return TipImportWordResponse(htmlContent=sanitize_html(html_content), plainText=plain_text)

    def _convert_document_to_html(self, document: _Document) -> str:
        html_parts: list[str] = []
        current_list_tag: str | None = None

        for block in self._iter_block_items(document):
            if isinstance(block, Paragraph):
                list_tag = self._resolve_list_tag(block)
                if list_tag:
                    if current_list_tag != list_tag:
                        if current_list_tag is not None:
                            html_parts.append(f"</{current_list_tag}>")
                        html_parts.append(f"<{list_tag}>")
                        current_list_tag = list_tag
                    html_parts.append(f"<li>{self._convert_paragraph_content(block)}</li>")
                else:
                    if current_list_tag is not None:
                        html_parts.append(f"</{current_list_tag}>")
                        current_list_tag = None
                    html_parts.append(self._convert_paragraph(block))
            elif isinstance(block, Table):
                if current_list_tag is not None:
                    html_parts.append(f"</{current_list_tag}>")
                    current_list_tag = None
                html_parts.append(self._convert_table(block))

        if current_list_tag is not None:
            html_parts.append(f"</{current_list_tag}>")

        return "".join(html_parts)

    def _iter_block_items(self, parent):
        parent_element = parent.element.body if isinstance(parent, _Document) else parent._tc
        for child in parent_element.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, parent)
            elif child.tag == qn("w:tbl"):
                yield Table(child, parent)

    def _resolve_list_tag(self, paragraph: Paragraph) -> str | None:
        style_name = (paragraph.style.name if paragraph.style is not None else "").lower()
        if "list bullet" in style_name:
            return "ul"
        if "list number" in style_name:
            return "ol"
        return None

    def _convert_paragraph(self, paragraph: Paragraph) -> str:
        content = self._convert_paragraph_content(paragraph)
        tag = self._resolve_paragraph_tag(paragraph)
        styles = self._resolve_paragraph_styles(paragraph)
        style_attr = f' style="{";".join(styles)}"' if styles else ""
        if not content:
            return f"<{tag}{style_attr}><br/></{tag}>"
        return f"<{tag}{style_attr}>{content}</{tag}>"

    def _resolve_paragraph_tag(self, paragraph: Paragraph) -> str:
        style_name = (paragraph.style.name if paragraph.style is not None else "").lower()
        if style_name.startswith("heading 1") or style_name == "title":
            return "h1"
        if style_name.startswith("heading 2") or style_name == "subtitle":
            return "h2"
        if style_name.startswith("heading 3"):
            return "h3"
        return "p"

    def _resolve_paragraph_styles(self, paragraph: Paragraph) -> list[str]:
        styles: list[str] = []
        alignment = getattr(paragraph, "alignment", None)
        if alignment is not None:
            alignment_map = {
                0: "text-align:left",
                1: "text-align:center",
                2: "text-align:right",
                3: "text-align:justify",
            }
            mapped = alignment_map.get(int(alignment))
            if mapped:
                styles.append(mapped)
        return styles

    def _convert_paragraph_content(self, paragraph: Paragraph) -> str:
        fragments: list[str] = []
        for run in paragraph.runs:
            fragments.append(self._convert_run(run))
        return "".join(fragment for fragment in fragments if fragment)

    def _convert_run(self, run: Run) -> str:
        fragments: list[str] = []
        for child in run._r.iterchildren():
            if child.tag == qn("w:t"):
                fragments.append(html.escape(child.text or ""))
            elif child.tag == qn("w:tab"):
                fragments.append("&emsp;")
            elif child.tag == qn("w:br") or child.tag == qn("w:cr"):
                fragments.append("<br/>")
            elif child.tag == qn("w:drawing"):
                fragments.append(self._convert_image_node(child, run))
            elif child.tag == qn("w:pict"):
                fragments.append(self._convert_image_node(child, run))

        content = "".join(fragment for fragment in fragments if fragment)
        if not content:
            return ""

        styles: list[str] = []
        if run.bold:
            styles.append("font-weight:bold")
        if run.italic:
            styles.append("font-style:italic")
        if run.underline:
            styles.append("text-decoration:underline")
        if run.font.size is not None:
            styles.append(f"font-size:{max(run.font.size.pt, 1):.2f}pt")
        if run.font.color is not None and run.font.color.rgb is not None:
            styles.append(f"color:#{run.font.color.rgb}")

        if not styles:
            return content
        return f'<span style="{";".join(styles)}">{content}</span>'

    def _convert_image_node(self, node, run: Run) -> str:
        relationship_ids = []
        try:
            relationship_ids.extend(node.xpath(".//a:blip/@r:embed"))
        except Exception:
            pass
        try:
            relationship_ids.extend(node.xpath(".//v:imagedata/@r:id"))
        except Exception:
            pass

        html_images: list[str] = []
        for relationship_id in relationship_ids:
            image_part = run.part.related_parts.get(relationship_id)
            if image_part is None:
                continue
            encoded = base64.b64encode(image_part.blob).decode("ascii")
            html_images.append(
                f'<img src="data:{image_part.content_type};base64,{encoded}" alt="word-image" />'
            )
        return "".join(html_images)

    def _convert_table(self, table: Table) -> str:
        rows_html: list[str] = []
        for row in table.rows:
            cell_html: list[str] = []
            for cell in row.cells:
                blocks = []
                for block in self._iter_block_items(cell):
                    if isinstance(block, Paragraph):
                        blocks.append(self._convert_paragraph(block))
                    elif isinstance(block, Table):
                        blocks.append(self._convert_table(block))
                cell_html.append(f"<td>{''.join(blocks)}</td>")
            rows_html.append(f"<tr>{''.join(cell_html)}</tr>")
        return f"<table>{''.join(rows_html)}</table>"

    def _to_list_item(self, row: UsageTipModel, account: AccountResponse | None) -> UsageTipListItemResponse:
        plain_text = row.plain_text or ""
        excerpt = plain_text[:120] + ("..." if len(plain_text) > 120 else "")
        return UsageTipListItemResponse(
            id=row.id,
            title=row.title,
            excerpt=excerpt,
            contributorQq=row.contributor_qq or "",
            authorUsername=row.author_username or "",
            isPublished=row.is_published,
            editable=account is not None and row.author_account_id == account.id,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )

    def _to_detail(self, row: UsageTipModel, account: AccountResponse | None) -> UsageTipDetailResponse:
        return UsageTipDetailResponse(
            id=row.id,
            title=row.title,
            htmlContent=sanitize_html(row.html_content),
            plainText=row.plain_text or "",
            contributorQq=row.contributor_qq or "",
            authorAccountId=row.author_account_id,
            authorUsername=row.author_username or "",
            isPublished=row.is_published,
            editable=account is not None and row.author_account_id == account.id,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )

    def _extract_plain_text(self, html_content: str) -> str:
        normalized = html_content or ""
        normalized = re.sub(r"(?i)<br\s*/?>", "\n", normalized)
        normalized = re.sub(r"(?i)</?(p|div|h[1-6]|li|tr|ul|ol|table|blockquote)[^>]*>", "\n", normalized)
        normalized = re.sub(r"<[^>]+>", "", normalized)
        normalized = html.unescape(normalized).replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in normalized.split("\n")]
        return "\n".join(line for line in lines if line)

    def _now_millis(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
