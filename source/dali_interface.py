import logging
import queue
import threading
import time

from .frame import DaliFrame
from .status import DaliStatus

logger = logging.getLogger(__name__)


class DaliInterface:
    RECEIVE_TIMEOUT = 1
    SLEEP_FOR_THREAD_END = 0.001

    def __init__(self, max_queue_size: int = 40, start_receive: bool = True) -> None:
        self.queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.last_error = "OK"
        self.keep_running = False
        self.__start_receive()

    def read_data(self) -> None:
        raise NotImplementedError("subclass must implement read_data")

    def read_worker_thread(self):
        logger.debug("read_worker_thread started")
        while self.keep_running:
            self.read_data()
        logger.debug("read_worker_thread terminated")

    def __start_receive(self) -> None:
        if not self.keep_running:
            logger.debug("start receive")
            self.keep_running = True
            self.thread = threading.Thread(target=self.read_worker_thread, args=())
            self.thread.daemon = True
            self.thread.start()
            while not self.queue.empty():
                self.queue.get()

    def get_next(self, timeout=None) -> DaliFrame:
        logger.debug("get next")
        if not self.keep_running:
            logger.error("read thread is not running")
        try:
            rx_frame, self.last_error = self.queue.get(block=True, timeout=timeout)
        except queue.Empty:
            logger.debug("queue is empty, timout occured.")
            return DaliFrame(status=DaliStatus.TIMEOUT)
        if self.rx_frame is None:
            return DaliFrame(status=DaliStatus.GENERAL)
        return rx_frame

    def transmit(self, frame: DaliFrame, block: bool = False, is_query=False) -> None:
        raise NotImplementedError("subclass must implement transmit")

    def query_reply(self, reuquest: DaliFrame) -> DaliFrame:
        raise NotImplementedError("subclass must implement query_reply")

    def close(self) -> None:
        logger.debug("close connection")
        if not self.keep_running:
            logger.debug("read thread is not running")
            return
        self.keep_running = False
        while self.thread.is_alive():
            time.sleep(DaliInterface.SLEEP_FOR_THREAD_END)
        logger.debug("connection closed, thread terminated")
