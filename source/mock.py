import logging

from .dali_interface import DaliInterface
from .frame import DaliFrame

logger = logging.getLogger(__name__)


class DaliMock(DaliInterface):
    def __init__(self):
        super().__init__()
        logger.debug("initialize mock interface")

    def transmit(self, frame: DaliFrame, block: bool = False, is_query=False):
        twice = "T" if frame.send_twice else "S"
        logger.info(
            f"{twice}{frame.priority} length:{frame.length:X} data:{frame.data:X}"
        )
