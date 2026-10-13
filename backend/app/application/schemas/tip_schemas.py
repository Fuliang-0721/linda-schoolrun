from pydantic import BaseModel, Field


class UsageTipListItemResponse(BaseModel):
    id: str
    title: str
    excerpt: str
    contributorQq: str = ""
    authorUsername: str = ""
    isPublished: bool
    editable: bool = False
    createdAt: int
    updatedAt: int


class UsageTipDetailResponse(BaseModel):
    id: str
    title: str
    htmlContent: str
    plainText: str
    contributorQq: str = ""
    authorAccountId: str = ""
    authorUsername: str = ""
    isPublished: bool
    editable: bool = False
    createdAt: int
    updatedAt: int


class SaveUsageTipRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    htmlContent: str = Field(default="", max_length=2_000_000)
    contributorQq: str = Field(default="", max_length=64)
    isPublished: bool = True


class AdminSaveUsageTipRequest(SaveUsageTipRequest):
    authorAccountId: str = Field(min_length=1, max_length=64)


class UsageTipListEnvelope(BaseModel):
    page: int = 1
    pageSize: int = 10
    total: int = 0
    totalPages: int = 0
    items: list[UsageTipListItemResponse]


class UsageTipEnvelope(BaseModel):
    data: UsageTipDetailResponse


class TipImportWordResponse(BaseModel):
    htmlContent: str
    plainText: str
