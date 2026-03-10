from pydantic import BaseModel


class Station(BaseModel):
    """
    Pydantic model representing a seismic station. This class defines the structure of a station's
    configuration.
    """
    network: str
    station: str
    latitude: float
    longitude: float
    elevation: float
