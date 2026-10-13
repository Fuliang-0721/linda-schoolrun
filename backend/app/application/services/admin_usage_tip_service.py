from app.core.safe_html import sanitize_html
from fastapi import HTTPException, UploadFile, status

from app.application.schemas.tip_schemas import (
    AdminSaveUsageTipRequest,
    TipImportWordResponse,
    UsageTipDetailResponse,
    UsageTipListItemResponse,
)
from app.application.services.usage_tip_service import UsageTipService
from app.core.auth_scope import normalize_client_variant
from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError
from app.core.id_generator import generate_public_id
from app.infrastructure.db.models.auth import AuthAccountModel
from app.infrastructure.db.models.tip import UsageTipModel


class AdminUsageTipService:
    def __init__(self, db):
        self._db = db
        self._shared_service = UsageTipService(db)
        self._variant = normalize_client_variant(settings.internal_auth_variant)

    def list_tips(
        self,
        query: str = "",
        published: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UsageTipListItemResponse], int]:
        statement = (
            self._db.query(UsageTipModel)
            .join(AuthAccountModel, AuthAccountModel.id == UsageTipModel.author_account_id)
            .filter(AuthAccountModel.client_variant == self._variant)
        )
        normalized_query = (query or "").strip()
        if normalized_query:
            like_query = f"%{normalized_query}%"
            statement = statement.filter(
                (UsageTipModel.title.like(like_query))
                | (UsageTipModel.plain_text.like(like_query))
                | (UsageTipModel.author_username.like(like_query))
                | (UsageTipModel.contributor_qq.like(like_query))
            )

        if published == "published":
            statement = statement.filter(UsageTipModel.is_published.is_(True))
        elif published == "draft":
            statement = statement.filter(UsageTipModel.is_published.is_(False))

        total = statement.count()
        rows = (
            statement
            .order_by(UsageTipModel.updated_at.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return [self._shared_service._to_list_item(row, None) for row in rows], total

    def get_tip(self, tip_id: str) -> UsageTipDetailResponse:
        row = self._find_tip(tip_id)
        if row is None:
            raise ResourceNotFoundError(f"Usage tip '{tip_id}' was not found.")
        return self._shared_service._to_detail(row, None)

    def create_tip(self, payload: AdminSaveUsageTipRequest) -> UsageTipDetailResponse:
        account = self._require_account(payload.authorAccountId)
        now = self._shared_service._now_millis()
        row = UsageTipModel(
            id=generate_public_id("tip"),
            title=payload.title.strip(),
            html_content=sanitize_html(payload.htmlContent),
            plain_text=self._shared_service._extract_plain_text(payload.htmlContent),
            contributor_qq=payload.contributorQq.strip(),
            is_published=payload.isPublished,
            author_account_id=account.id,
            author_username=account.display_username or account.username,
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._shared_service._to_detail(row, None)

    def update_tip(self, tip_id: str, payload: AdminSaveUsageTipRequest) -> UsageTipDetailResponse:
        row = self._find_tip(tip_id)
        if row is None:
            raise ResourceNotFoundError(f"Usage tip '{tip_id}' was not found.")
        account = self._require_account(payload.authorAccountId)
        row.title = payload.title.strip()
        row.html_content = sanitize_html(payload.htmlContent)
        row.plain_text = self._shared_service._extract_plain_text(payload.htmlContent)
        row.contributor_qq = payload.contributorQq.strip()
        row.is_published = payload.isPublished
        row.author_account_id = account.id
        row.author_username = account.display_username or account.username
        row.updated_at = self._shared_service._now_millis()
        self._db.commit()
        self._db.refresh(row)
        return self._shared_service._to_detail(row, None)

    def delete_tip(self, tip_id: str) -> None:
        row = self._find_tip(tip_id)
        if row is None:
            raise ResourceNotFoundError(f"Usage tip '{tip_id}' was not found.")
        self._db.delete(row)
        self._db.commit()

    def import_word(self, upload: UploadFile) -> TipImportWordResponse:
        return self._shared_service.import_word(upload)

    def _find_tip(self, tip_id: str) -> UsageTipModel | None:
        return (
            self._db.query(UsageTipModel)
            .join(AuthAccountModel, AuthAccountModel.id == UsageTipModel.author_account_id)
            .filter(
                UsageTipModel.id == tip_id,
                AuthAccountModel.client_variant == self._variant,
            )
            .first()
        )

    def _require_account(self, account_id: str) -> AuthAccountModel:
        normalized_id = (account_id or "").strip()
        account = (
            self._db.query(AuthAccountModel)
            .filter(
                AuthAccountModel.id == normalized_id,
                AuthAccountModel.client_variant == self._variant,
            )
            .first()
        )
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="使用技巧作者账号不存在。")
        return account
