from enum import IntEnum


# 0  Single-ended input  8 channel, 1 Differential input  4 channel
class ScanMode(IntEnum):
    SingleMode = 0
    DifferentialMode = 1
