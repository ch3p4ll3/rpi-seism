from pydantic import BaseModel


class Spi(BaseModel):
    rst_pin: int
    cs_pin: int
    cs_dac_pin: int
    drdy_pin: int
