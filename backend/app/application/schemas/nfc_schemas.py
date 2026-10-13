from pydantic import BaseModel, Field


class CreateSharedNfcRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=1, max_length=1024)
    packageName: str = Field(min_length=1, max_length=255)
    source: str = Field(default="manual", max_length=64)


class SharedNfcResponse(BaseModel):
    id: str
    name: str
    url: str
    packageName: str
    source: str
    createdAt: int


class SharedNfcListEnvelope(BaseModel):
    page: int = 1
    pageSize: int = 10
    total: int = 0
    totalPages: int = 0
    items: list[SharedNfcResponse]


class SharedNfcEnvelope(BaseModel):
    data: SharedNfcResponse
