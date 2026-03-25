from typing import Literal

from rpi_seism_common.websocket_message import WebsocketMessage
from rpi_seism_common.websocket_message.enums import WebsocketMessageTypeEnum

from .sample_payload import SamplePayload


class Sample(WebsocketMessage):
    type: Literal[WebsocketMessageTypeEnum.DATA] = WebsocketMessageTypeEnum.DATA
    payload: SamplePayload

    @property
    def to_json(self):
        return self.model_dump_json()
