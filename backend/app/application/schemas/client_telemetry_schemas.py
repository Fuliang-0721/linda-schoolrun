from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClientIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installId: str = Field(pattern=r"^[a-f0-9]{32}$")
    token: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)


class ActualLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float = Field(gt=0, le=10000)
    capturedAt: int = Field(gt=0)


class ClientTelemetryRequest(ClientIdentity):
    sequence: int = Field(ge=1, le=2**53)
    versionName: str = Field(min_length=1, max_length=32)
    versionCode: int = Field(ge=1, le=2147483647)
    deviceModel: str = Field(max_length=96)
    androidSdk: int = Field(ge=28, le=100)
    launches: int = Field(ge=0, le=2**53)
    simulationCount: int = Field(ge=0, le=2**53)
    simulationSeconds: int = Field(ge=0, le=2**53)
    locationStatus: Literal["disabled", "permission_denied", "mock_active", "unavailable", "available"]
    location: ActualLocation | None = None

    @model_validator(mode="after")
    def check_location(self):
        if (self.locationStatus == "available") != (self.location is not None):
            raise ValueError("available requires a location; all other statuses forbid coordinates")
        return self
