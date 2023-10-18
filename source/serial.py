import logging
from typing import Tuple, Final
from typeguard import typechecked

import serial  # type: ignore

from .dali_interface import DaliInterface
from .frame import DaliFrame
from .status import DaliStatus

logger = logging.getLogger(__name__)


@typechecked
class DaliSerial(DaliInterface):
    DEFAULT_BAUDRATE: Final[int] = 500000
    # see: https://github.com/SvenHaedrich/dali_usb_lpc1114/blob/main/doc/messages.md
    _MAX_BIT_LENGTH: Final[int] = 32
    _TIMEOUT: Final[int] = 0x81
    _BAD_START_BIT_TIMING: Final[int] = 0x82
    _BAD_DATA_BIT_TIMING: Final[int] = 0x83
    _COLLISION_LOOPBACK: Final[int] = 0x84
    _COLLISION_NO_CHANGE: Final[int] = 0x85
    _COLLISION_WRONG_STATE: Final[int] = 0x86
    _SETTLING_TIME: Final[int] = 0x87
    _SYSTEM_IDLE: Final[int] = 0x90
    _SYSTEM_FAILURE: Final[int] = 0x91
    _SYSTEM_RECOVERED: Final[int] = 0x92
    _COMMAND_NOT_PROCESSED: Final[int] = 0xA0
    _COMMAND_BAD_ARGUMENT: Final[int] = 0xA1
    _QUEUE_IS_FULL: Final[int] = 0xA2
    _COMMAND_BAD: Final[int] = 0xA3
    _BUFFER_OVERFLOW: Final[int] = 0xA4

    def __init__(
        self,
        portname: str,
        baudrate: int = DEFAULT_BAUDRATE,
        transparent: bool = False,
        start_receive: bool = True,
    ) -> None:
        """open serial port for DALI communication

        Args:
            portname (str): path to serial port
            baudrate (int, optional): baudrate. Defaults to DEFAULT_BAUDRATE.
            transparent (bool, optional): print echo to console. Defaults to False.
            start_receive (bool, optional): start a receive thread. Defaults to True.
        """
        logger.debug("open serial port")
        self.port = serial.Serial(port=portname, baudrate=baudrate, timeout=0.2)
        self.port.set_low_latency_mode(True)
        self.transparent = transparent
        super().__init__()

    @staticmethod
    def __get_status_and_last_error(
        length: int, data: int, loopback: bool
    ) -> Tuple[int, str]:
        if 0 <= length <= DaliSerial._MAX_BIT_LENGTH:
            if loopback:
                return DaliStatus.LOOPBACK, "LOOPBACK FRAME"
            else:
                return DaliStatus.FRAME, "NORMAL FRAME"
        elif length < DaliSerial._TIMEOUT:
            return DaliStatus.OK, "OK"
        elif length == DaliSerial._TIMEOUT:
            return DaliStatus.TIMEOUT, "TIMEOUT"
        elif length == DaliSerial._BAD_START_BIT_TIMING:
            bit = data & 0x0FF
            timer_us = (data >> 8) & 0x0FFFFF
            return (
                DaliStatus.TIMING,
                f"ERROR TIMING: START - BIT: {bit} - TIME: {timer_us} USEC",
            )
        elif length == DaliSerial._BAD_DATA_BIT_TIMING:
            bit = data & 0x0FF
            timer_us = (data >> 8) & 0x0FFFFF
            return (
                DaliStatus.TIMING,
                f"ERRROR TIMING: DATA - BIT: {bit} - TIME: {timer_us} USEC",
            )
        elif length in (
            DaliSerial._COLLISION_LOOPBACK,
            DaliSerial._COLLISION_NO_CHANGE,
            DaliSerial._COLLISION_WRONG_STATE,
        ):
            return DaliStatus.TIMING, "ERROR: COLLISION DETECTED"
        elif length == DaliSerial._SYSTEM_FAILURE:
            return DaliStatus.FAILURE, "ERROR: SYSTEM FAILURE"
        elif length == DaliSerial._SYSTEM_RECOVERED:
            return DaliStatus.RECOVER, "SYSTEM RECOVER"
        elif length in (
            DaliSerial._COMMAND_NOT_PROCESSED,
            DaliSerial._COMMAND_BAD_ARGUMENT,
            DaliSerial._QUEUE_IS_FULL,
            DaliSerial._COMMAND_BAD,
        ):
            return DaliStatus.INTERFACE, "ERROR: INTERFACE"
        else:
            return DaliStatus.UNDEFINED, f"ERROR: CODE 0x{length:02X}"

    @staticmethod
    def parse(line: str) -> DaliFrame:
        """parse a string into a DALI frame

        Args:
            line (str): input string, curly braces aorund DALI information required

        Returns:
            DaliFrame: DALI frame
        """
        try:
            start = line.find("{") + 1
            end = line.find("}")
            payload = line[start:end]
            timestamp = int(payload[0:8], 16) / 1000.0
            if payload[8] == ">":
                loopback = True
            else:
                loopback = False
            length = int(payload[9:11], 16)
            data = int(payload[12:20], 16)
            status, message = DaliSerial.__get_status_and_last_error(
                length, data, loopback
            )
            return DaliFrame(
                timestamp=timestamp,
                length=length,
                data=data,
                status=status,
                message=message,
            )
        except ValueError:
            return DaliFrame(
                timestamp=timestamp,
                length=length,
                data=data,
                status=DaliStatus.GENERAL,
                message="value error",
            )

    def read_data(self) -> None:
        line = self.port.readline().decode("utf-8").strip()
        if self.transparent:
            print(line, end="")
        if len(line) > 0:
            logger.debug(f"received line <{line}> from serial")
            self.queue.put(self.parse(line))

    @staticmethod
    def __built_command_string(frame: DaliFrame, is_query: bool) -> str:
        if frame.length == 8:
            return f"Y{frame.data:X}\r"
        else:
            command = "Q" if is_query else "S"
            twice = "+" if frame.send_twice else " "
            return f"{command}{frame.priority} {frame.length:X}{twice}{frame.data:X}\r"

    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
        command_string = DaliSerial.__built_command_string(frame, False)
        self.port.write(command_string.encode("utf-8"))
        if block:
            self.get(DaliInterface.RECEIVE_TIMEOUT)

    def query_reply(self, frame: DaliFrame) -> DaliFrame:
        if not self.keep_running:
            logger.error("read thread is not running")
        logger.debug("flush queue")
        while not self.queue.empty():
            self.queue.get()
        command_string = DaliSerial.__built_command_string(frame, True)
        self.port.write(command_string.encode("utf-8"))
        loopback = self.get(timeout=DaliInterface.RECEIVE_TIMEOUT)
        if (
            loopback.status != DaliStatus.LOOPBACK
            or loopback.data != frame.data
            or loopback.length != frame.length
        ):
            logger.error("unexpected result when reading loopback")
            return loopback
        logger.debug("read backframe")
        return self.get(timeout=DaliInterface.RECEIVE_TIMEOUT)
