from pydantic import BaseModel, Field


class InternalSoftwareNameResponse(BaseModel):
    id: str
    name: str
    status: str
    submitterUsername: str = ""
    submitterTesterType: str = ""
    reviewedAt: int = 0
    createdAt: int
    updatedAt: int


class InternalSoftwareNameListEnvelope(BaseModel):
    items: list[InternalSoftwareNameResponse]


class SubmitInternalSoftwareNameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class UploadAppLogRequest(BaseModel):
    softwareName: str = Field(min_length=1, max_length=128)
    contactQq: str = Field(min_length=1, max_length=64)
    logText: str = Field(min_length=1, max_length=5_000_000)


class UploadAppLogResponse(BaseModel):
    message: str
    softwareName: str
    fileName: str


class UploadAppLogEnvelope(BaseModel):
    data: UploadAppLogResponse


class InternalSoftwareNameEnvelope(BaseModel):
    data: InternalSoftwareNameResponse
