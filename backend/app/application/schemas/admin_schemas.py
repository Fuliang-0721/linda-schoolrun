from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AdminSessionResponse(BaseModel):
    authenticated: bool
    username: str | None = None


class ActionMessageResponse(BaseModel):
    message: str
