import logging

from .dali_interface import DaliInterface
from .frame import DaliFrame

logger = logging.getLogger(__name__)


class DaliMock(DaliInterface):
    def __init__(self):
        super().__init__(start_receive=False)
        logger.debug("initialize mock interface")

    def transmit(
        self, frame: DaliFrame, block: bool = False, is_query: bool = False
    ) -> None:
        command_byte = "Q" if is_query else "S"
        if frame.send_twice:
            command = (
                f"{command_byte}{frame.priority} {frame.length:X}+{frame.data:X}\r"
            )
        else:
            if frame.length == 8:
                command = f"Y{frame.data:X}\r"
            else:
                command = (
                    f"{command_byte}{frame.priority} {frame.length:X} {frame.data:X}\r"
                )
        print(command)
