from typing import Literal

from rpi_seism_common.websocket_message import WebsocketMessage
from rpi_seism_common.websocket_message.enums import WebsocketMessageTypeEnum

from .state_of_health_payload import StateOfHealthPayload


# For future use
class StateOfHealth(WebsocketMessage):
    type: Literal[WebsocketMessageTypeEnum.STATE_OF_HEALTH] = WebsocketMessageTypeEnum.STATE_OF_HEALTH
    payload: StateOfHealthPayload
