from rpi_seism_common.websocket_message import BaseModel


class StateOfHealthPayload(BaseModel):
    link_quality: float
    bytes_dropped: int
    checksum_errors: int
    last_seen: float
    connected: bool
