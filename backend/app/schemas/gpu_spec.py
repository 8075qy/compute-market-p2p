from pydantic import BaseModel, ConfigDict


class GpuSpecResponse(BaseModel):
    gpu_model: str
    vendor: str
    vram_gb: int
    peak_tflops: float

    model_config = ConfigDict(from_attributes=True)
