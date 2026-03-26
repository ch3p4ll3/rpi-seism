from rpi_seism_common.websocket_message import BaseModel


class SamplePayload(BaseModel):
    channel: str
    timestamp: str
    fs: float
    data: list[float]
