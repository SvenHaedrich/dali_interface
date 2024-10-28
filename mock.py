"""Mock DALI interface for testing."""

import logging
import time

from .dali_interface import DaliFrame, DaliInterface, DaliStatus

logger = logging.getLogger(__name__)


class DaliMock(DaliInterface):
    """Mock class for DALI interface."""

    def __init__(self):
        """Initialize DALI mock interface."""
        super().__init__(start_receive=False)
        logger.debug("initialize mock interface")

    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
        """Mock transmission of DALI frame."""
        print(DaliInterface.build_command_string(frame, False))

    def query_reply(self, request: DaliFrame) -> DaliFrame:
        """Mock DALI frame query."""
        print(DaliInterface.build_command_string(request, False))
        return DaliFrame(
            timestamp=time.time(),
            length=0,
            data=0,
            status=DaliStatus.TIMEOUT,
            message="mock timeout",
        )

    def read_data(self) -> None:
        """Stub implementation."""
        raise NotImplementedError("Mock class has no read implementation")
