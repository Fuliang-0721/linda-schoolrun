from pydantic import BaseModel, Field


class AppVersionResponse(BaseModel):
    """客户端版本检查结果。"""

    update: bool
    channel: str
    packageName: str
    # 有更新时为本条发布的 versionCode；无更新时为服务端该渠道最新 versionCode
    versionCode: int = 0
    versionName: str = ""
    minSupportedVersionCode: int = 0
    force: bool = False
    rolloutPercent: int = 100
    sizeBytes: int = 0
    sha256: str = ""
    downloadUrl: str = ""
    mirrorUrls: list[str] = Field(default_factory=list)
    changelog: str = ""
    releaseNotesUrl: str = ""
    abi: str = ""
    publishedAt: int = 0


class AppVersionEnvelope(BaseModel):
    data: AppVersionResponse


class CreateAppReleaseRequest(BaseModel):
    packageName: str = Field(min_length=1, max_length=128)
    channel: str = Field(default="stable", max_length=32)
    versionCode: int = Field(gt=0)
    versionName: str = Field(default="", max_length=64)
    minSupportedVersionCode: int = Field(default=0, ge=0)
    force: bool = False
    rolloutPercent: int = Field(default=100, ge=0, le=100)
    sizeBytes: int = Field(default=0, ge=0)
    sha256: str = Field(default="", max_length=64)
    downloadUrl: str = Field(default="", max_length=512)
    mirrorUrls: list[str] = Field(default_factory=list)
    changelog: str = Field(default="", max_length=20_000)
    releaseNotesUrl: str = Field(default="", max_length=512)
    abi: str = Field(default="arm64-v8a", max_length=32)
    status: str = Field(default="draft", pattern="^(draft|published|revoked)$")
    # 定向发布：只对这些 installId 下发（留空=按渠道下发）
    targetInstallIds: list[str] = Field(default_factory=list)


class UpdateAppReleaseRequest(BaseModel):
    versionName: str | None = Field(default=None, max_length=64)
    minSupportedVersionCode: int | None = Field(default=None, ge=0)
    force: bool | None = None
    rolloutPercent: int | None = Field(default=None, ge=0, le=100)
    sizeBytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, max_length=64)
    downloadUrl: str | None = Field(default=None, max_length=512)
    mirrorUrls: list[str] | None = None
    changelog: str | None = Field(default=None, max_length=20_000)
    releaseNotesUrl: str | None = Field(default=None, max_length=512)
    abi: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, pattern="^(draft|published|revoked)$")
    targetInstallIds: list[str] | None = None


class AppReleaseResponse(BaseModel):
    id: str
    packageName: str
    channel: str
    versionCode: int
    versionName: str
    minSupportedVersionCode: int
    force: bool
    rolloutPercent: int
    sizeBytes: int
    sha256: str
    downloadUrl: str
    mirrorUrls: list[str]
    changelog: str
    releaseNotesUrl: str
    abi: str
    status: str
    targetInstallIds: list[str]
    publishedAt: int
    createdAt: int
    updatedAt: int


class AppReleaseEnvelope(BaseModel):
    data: AppReleaseResponse


class AppReleaseListEnvelope(BaseModel):
    items: list[AppReleaseResponse]


class AppReleaseHistoryItem(BaseModel):
    versionCode: int
    versionName: str
    channel: str
    publishedAt: int
    changelog: str


class AppReleaseHistoryEnvelope(BaseModel):
    items: list[AppReleaseHistoryItem]


class UploadedBundleResponse(BaseModel):
    fileName: str
    sizeBytes: int
    sha256: str
    downloadUrl: str


class UploadedBundleEnvelope(BaseModel):
    data: UploadedBundleResponse
