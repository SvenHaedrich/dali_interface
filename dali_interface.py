"""Abstract implementation of the DALI interface class."""

import logging
import queue
import threading
import time
from enum import IntEnum
from typing import NamedTuple

from typeguard import typechecked

logger = logging.getLogger(__name__)


class DaliStatus(IntEnum):
    """Status for frames and events."""

    OK = 0
    LOOPBACK = 1
    FRAME = 2
    TIMEOUT = 3
    TIMING = 4
    INTERFACE = 5
    FAILURE = 6
    RECOVER = 7
    GENERAL = 8
    UNDEFINED = 9


class DaliFrame(NamedTuple):
    """DALI frame object."""

    timestamp: float = 0
    length: int = 0
    data: int = 0
    priority: int = 2
    send_twice: bool = False
    status: int = DaliStatus.OK
    message: str = "OK"


@typechecked
class DaliInterface:
    """Abstract DALI interface class."""

    RECEIVE_TIMEOUT = 1
    SLEEP_FOR_THREAD_END = 0.001

    def __init__(self, max_queue_size: int = 40, start_receive: bool = True) -> None:
        """Initialize DALI interface.

        Args:
            max_queue_size (int, optional): Length of input queue for frames read from DALI bus.
                Defaults to 40.
            start_receive (bool, optional): Start a thread that reads DAL frames from the bus
                and transfers them into the input queue.
                Defaults to True.
        """
        self.queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.keep_running = False
        if start_receive:
            self.__start_receive()

    def __enter__(self):
        """Access object via context manager"""
        return self

    def __exit__(self, exc_type, exc_val, traceback):
        """Close object via context manager"""
        self.close()

    def power(self, power: bool = False) -> None:
        """Stub for controlling a built-in power supply."""
        raise RuntimeError("subclass must implement power")

    def read_data(self) -> None:
        """Stub for reading data needs to be overwritten by an implementation."""
        raise NotImplementedError("subclass must implement read_data")

    def flush_queue(self) -> None:
        """Flush the queue with DALI frames."""
        while not self.queue.empty():
            self.queue.get()

    def __read_worker_thread(self):
        """The read thread which is executed to read DALI frames from the interface."""
        logger.debug("read_worker_thread started")
        while self.keep_running:
            self.read_data()
        logger.debug("read_worker_thread terminated")

    def __start_receive(self) -> None:
        """Start the receive thread which fille the queue with DALI frames."""
        if not self.keep_running:
            logger.debug("start receive")
            self.keep_running = True
            self.thread = threading.Thread(target=self.__read_worker_thread, args=())
            self.thread.daemon = True
            self.thread.start()
            self.flush_queue()

    def get(self, timeout: float | None = None) -> DaliFrame:
        """Get the next DALI frame from the interface. Function blocks until a frame
            is received or timeout occurs.

        Args:
            timeout (float | None, optional): time in seconds before the call returns.
            Defaults to None (never timer out).

        Returns:
            DaliFrame: time out is indicated in the frame status.
        """
        logger.debug("get")
        if not self.keep_running:
            raise Exception("read thread is not running")
        try:
            rx_frame = self.queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return DaliFrame(
                status=DaliStatus.TIMEOUT, message="queue is empty, timeout from get"
            )
        if rx_frame is None:
            return DaliFrame(
                status=DaliStatus.GENERAL, message="received None from queue"
            )
        logger.debug(f"return {rx_frame.message} - {rx_frame.length} - {rx_frame.data}")
        return rx_frame

    @staticmethod
    def build_command_string(frame: DaliFrame, is_query: bool) -> str:
        """Build a command string for a frame to send via serial connector."""
        if frame.length == 8:
            return f"Y{frame.data:X}\r"
        command = "Q" if is_query else "S"
        twice = "+" if frame.send_twice else " "
        return f"{command}{frame.priority} {frame.length:X}{twice}{frame.data:X}\r"

    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
        """Transmit a DALI frame. All 8 bit frames are treated as backward frames.

        Args:
            frame (DaliFrame): frame to transmit
            block (bool, optional): wait for the end of transmission.
                Defaults to False.
        """
        raise NotImplementedError("subclass must implement transmit")

    def query_reply(self, request: DaliFrame) -> DaliFrame:
        """Transmit a DALI frame that is requesting a reply. Wait for either
            the replied data, or indicate a timeout.

        Args:
            request (DaliFrame): frame to transmit

        Returns:
            DaliFrame: the received reply, if no reply was received a
                frame with DaliStatus:TIMEOUT is returned
        """
        raise NotImplementedError("subclass must implement query_reply")

    def close(self) -> None:
        """Close the connection."""
        logger.debug("tear down connection")
        if not self.keep_running:
            logger.debug("read thread is not running")
            return
        self.keep_running = False
        while self.thread.is_alive():
            time.sleep(DaliInterface.SLEEP_FOR_THREAD_END)
        logger.debug("connection closed, thread terminated")
