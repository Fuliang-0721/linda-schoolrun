from pydantic import BaseModel, Field

from app.application.schemas.auth_schemas import AccountResponse


class CreateInternalAccountRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    remark: str = Field(default="", max_length=255)
    testerType: str = Field(default="ordinary", max_length=32)


class UpdateInternalAccountRequest(BaseModel):
    remark: str = Field(default="", max_length=255)
    testerType: str = Field(default="ordinary", max_length=32)
    status: str = Field(default="active", max_length=32)
    banReason: str = Field(default="", max_length=255)
    banDetail: str = Field(default="", max_length=2000)
    password: str = Field(default="", max_length=128)
    resetBoundDevice: bool = False


class BanInternalAccountRequest(BaseModel):
    banReason: str = Field(default="manual", max_length=255)
    banDetail: str = Field(default="", max_length=2000)


class InternalAccountListEnvelope(BaseModel):
    items: list[AccountResponse]


class InternalAccountEnvelope(BaseModel):
    data: AccountResponse
