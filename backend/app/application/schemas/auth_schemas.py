from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    id: str
    username: str
    clientVariant: str = ""
    remark: str = ""
    testerType: str = ""
    testerTypeLabel: str = "未分类账号"
    status: str
    banReason: str = ""
    banDetail: str = ""
    bannedAt: int = 0
    boundDeviceId: str = ""
    boundDeviceName: str = ""
    failedDeviceAttempts: int = 0
    lastLoginAt: int = 0
    createdAt: int
    updatedAt: int


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    deviceId: str = Field(min_length=1, max_length=255)
    deviceName: str = Field(default="", max_length=255)
    appVariant: str = Field(default="internal", max_length=32)


class AuthLoginResponse(BaseModel):
    token: str
    account: AccountResponse


class AuthMeResponse(BaseModel):
    authenticated: bool
    account: AccountResponse | None = None


class AuthAlertResponse(BaseModel):
    id: str
    message: str
    ipAddress: str
    deviceId: str
    deviceName: str
    createdAt: int


class AuthAlertListResponse(BaseModel):
    items: list[AuthAlertResponse]


class AuthDeviceResponse(BaseModel):
    deviceId: str
    clientVariant: str = ""
    deviceName: str = ""
    status: str
    banReason: str = ""
    banDetail: str = ""
    bannedUntil: int = 0
    wrongPasswordCount: int = 0
    wrongPasswordBanCount: int = 0
    wrongDeviceAttemptCount: int = 0
    lastIp: str = ""
    lastAttemptAt: int = 0
    createdAt: int
    updatedAt: int


class UpdateAuthDeviceRequest(BaseModel):
    deviceName: str = Field(default="", max_length=255)
    status: str = Field(default="active", max_length=32)
    banReason: str = Field(default="", max_length=64)
    banDetail: str = Field(default="", max_length=5000)
    bannedUntil: int = 0
    resetCounters: bool = False


class AuthDeviceListEnvelope(BaseModel):
    items: list[AuthDeviceResponse]


class AuthDeviceEnvelope(BaseModel):
    data: AuthDeviceResponse
