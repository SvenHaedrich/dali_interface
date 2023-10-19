import logging

from .dali_interface import DaliInterface
from .frame import DaliFrame

logger = logging.getLogger(__name__)


class DaliMock(DaliInterface):
    def __init__(self):
        super().__init__(start_receive=False)
        logger.debug("initialize mock interface")

    @staticmethod
    def __built_command_string(frame: DaliFrame, is_query: bool) -> str:
        if frame.length == 8:
            return f"Y{frame.data:X}\r"
        else:
            command = "Q" if is_query else "S"
            twice = "+" if frame.send_twice else " "
            return f"{command}{frame.priority} {frame.length:X}{twice}{frame.data:X}\r"

    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
        print(DaliMock.__built_command_string(frame, False))
