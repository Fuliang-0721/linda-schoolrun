from pydantic import BaseModel


class AccessStatusResponse(BaseModel):
    allowed: bool
    serviceEnabled: bool
    scope: str
    message: str
    channel: str = ""
    updatedAt: int = 0


class AccessStatusEnvelope(BaseModel):
    data: AccessStatusResponse


class AccessPolicyResponse(BaseModel):
    serviceEnabled: bool
    message: str = ""
    scope: str = "all"
    updatedAt: int = 0


class AccessPolicyEnvelope(BaseModel):
    data: AccessPolicyResponse


class AccessPolicyRequest(BaseModel):
    serviceEnabled: bool
    message: str = ""
    scope: str = "all"
