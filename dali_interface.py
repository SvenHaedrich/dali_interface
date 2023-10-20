import logging
import queue
import threading
import time
from typeguard import typechecked

from .frame import DaliFrame
from .status import DaliStatus

logger = logging.getLogger(__name__)


@typechecked
class DaliInterface:
    RECEIVE_TIMEOUT = 1
    SLEEP_FOR_THREAD_END = 0.001

    def __init__(self, max_queue_size: int = 40, start_receive: bool = True) -> None:
        """initialize DALI interfcae

        Args:
            max_queue_size (int, optional): _description_. Defaults to 40.
            start_receive (bool, optional): _description_. Defaults to True.
        """
        self.queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.keep_running = False
        if start_receive:
            self.__start_receive()

    def read_data(self) -> None:
        raise NotImplementedError("subclass must implement read_data")

    def flush_queue(self) -> None:
        while not self.queue.empty():
            self.queue.get()

    def __read_worker_thread(self):
        logger.debug("read_worker_thread started")
        while self.keep_running:
            self.read_data()
        logger.debug("read_worker_thread terminated")

    def __start_receive(self) -> None:
        if not self.keep_running:
            logger.debug("start receive")
            self.keep_running = True
            self.thread = threading.Thread(target=self.__read_worker_thread, args=())
            self.thread.daemon = True
            self.thread.start()
            self.flush_queue()

    def get(self, timeout: float | None = None) -> DaliFrame:
        """get the next DALI frame from the interface. Function blocks until a frame
            is received or timeout occurs

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

    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
        """transmit a DALI frame. All 8 bit frames are treated as backward franes.

        Args:
            frame (DaliFrame): frame to transmit
            block (bool, optional): wait for the end of transmission.
                Defaults to False.
        """
        raise NotImplementedError("subclass must implement transmit")

    def query_reply(self, request: DaliFrame) -> DaliFrame:
        """transmit a DALI frame that is requesting a reply. Wait for either
            the replied data, or indicate a timeout.

        Args:
            request (DaliFrame): frame to transmit

        Returns:
            DaliFrame: the received reply, if no reply was received a
                frame with DaliStatus:TIMEOUT is returned
        """
        raise NotImplementedError("subclass must implement query_reply")

    def close(self) -> None:
        """close the connection"""
        logger.debug("tear down connection")
        if not self.keep_running:
            logger.debug("read thread is not running")
            return
        self.keep_running = False
        while self.thread.is_alive():
            time.sleep(DaliInterface.SLEEP_FOR_THREAD_END)
        logger.debug("connection closed, thread terminated")
