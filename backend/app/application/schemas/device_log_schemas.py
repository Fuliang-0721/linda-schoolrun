from pydantic import BaseModel, Field


class UploadDeviceLogRequest(BaseModel):
    installId: str = Field(pattern=r"^[a-f0-9]{32}$")
    token: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)
    versionName: str = Field(default="", max_length=32)
    versionCode: int = Field(default=0, ge=0)
    deviceModel: str = Field(default="", max_length=96)
    androidSdk: int = Field(default=0, ge=0)
    # manual=用户在设置里主动上传；crash=崩溃后自动上传；startup=启动自检
    reason: str = Field(default="manual", max_length=32)
    logText: str = Field(min_length=1, max_length=600_000)


class UploadDeviceLogResponse(BaseModel):
    id: str
    sizeBytes: int
    message: str


class UploadDeviceLogEnvelope(BaseModel):
    data: UploadDeviceLogResponse


class DeviceLogSummaryResponse(BaseModel):
    id: str
    installId: str
    versionName: str
    versionCode: int
    deviceModel: str
    androidSdk: int
    reason: str
    sizeBytes: int
    createdAt: int


class DeviceLogDetailResponse(DeviceLogSummaryResponse):
    logText: str


class DeviceLogListEnvelope(BaseModel):
    page: int
    pageSize: int
    total: int
    totalPages: int
    items: list[DeviceLogSummaryResponse]


class DeviceLogDetailEnvelope(BaseModel):
    data: DeviceLogDetailResponse
