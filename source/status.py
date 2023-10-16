from typing import Final


class DaliStatus:
    OK: Final[int] = 0
    LOOPBACK: Final[int] = 1
    FRAME: Final[int] = 2
    TIMEOUT: Final[int] = 3
    TIMING: Final[int] = 4
    INTERFACE: Final[int] = 5
    FAILURE: Final[int] = 6
    RECOVER: Final[int] = 7
    GENERAL: Final[int] = 8
    UNDEFINED: Final[int] = 9
