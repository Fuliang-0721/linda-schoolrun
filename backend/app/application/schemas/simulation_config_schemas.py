from pydantic import BaseModel, Field


class SaveSharedSimulationConfigRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    mode: str = Field(default="speed", max_length=32)
    speed: float = 0.0
    cadence: float = 0.0
    loopCount: int = Field(default=1, ge=1)
    dynamicIntensityEnabled: bool = False
    intensityVariationRange: float = Field(default=0.0, ge=0)
    intensityVariationFrequency: float = 0.0
    naturalPathVariationEnabled: bool = False
    pathVariationAmplitude: float = Field(default=0.0, ge=0)
    naturalAltitudeVariationEnabled: bool = False
    altitudeBaseMeters: float = Field(default=55.0, ge=0)
    altitudeVariationRange: float = Field(default=0.0, ge=0)
    altitudeVariationHeightCentimeters: float = Field(default=0.0, ge=0)
    altitudeVariationProbability: float = Field(default=0.0, ge=0, le=1)
    linkRatioNumerator: float = Field(default=1.0, gt=0)
    stepsPerMeter: float = Field(default=1.0, gt=0)
    uploaderTester: bool = False


class SharedSimulationConfigResponse(BaseModel):
    id: str
    name: str
    mode: str
    speed: float
    cadence: float
    loopCount: int
    dynamicIntensityEnabled: bool
    intensityVariationRange: float
    intensityVariationFrequency: float
    naturalPathVariationEnabled: bool
    pathVariationAmplitude: float
    naturalAltitudeVariationEnabled: bool
    altitudeBaseMeters: float
    altitudeVariationRange: float
    altitudeVariationHeightCentimeters: float
    altitudeVariationProbability: float
    linkRatioNumerator: float
    stepsPerMeter: float
    authorName: str = ""
    uploaderTester: bool = False
    createdAt: int
    updatedAt: int


class SharedSimulationConfigListEnvelope(BaseModel):
    items: list[SharedSimulationConfigResponse]


class SharedSimulationConfigEnvelope(BaseModel):
    data: SharedSimulationConfigResponse
