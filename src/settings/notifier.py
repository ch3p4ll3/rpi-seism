from pydantic import BaseModel, AnyUrl


class Notifier(BaseModel):
    url: AnyUrl
    enabled: bool = True
