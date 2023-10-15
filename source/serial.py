import logging
from typing import Tuple
from typeguard import typechecked

import serial  # type: ignore

from .dali_interface import DaliInterface
from .frame import DaliFrame
from .status import DaliStatus

logger = logging.getLogger(__name__)


@typechecked
class DaliSerial(DaliInterface):
    DEFAULT_BAUDRATE = 500000

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
    ) -> Tuple[DaliStatus, str]:
        if 0 <= length < 0x21:
            if loopback:
                return DaliStatus.LOOPBACK, "LOOPBACK FRAME"
            else:
                return DaliStatus.FRAME, "NORMAL FRAME"
        elif 0 <= length < 0x81:
            return DaliStatus.OK, "OK"
        elif length == 0x81:
            return DaliStatus.TIMEOUT, "TIMEOUT"
        elif length == 0x82:
            bit = data & 0x0FF
            timer_us = (data >> 8) & 0x0FFFFF
            return (
                DaliStatus.TIMING,
                f"ERROR TIMING: START - BIT: {bit} - TIME: {timer_us} USEC",
            )
        elif length == 0x83:
            bit = data & 0x0FF
            timer_us = (data >> 8) & 0x0FFFFF
            return (
                DaliStatus.TIMING,
                f"ERRROR TIMING: DATA - BIT: {bit} - TIME: {timer_us} USEC",
            )
        elif length in (0x84, 0x85, 0x86):
            return DaliStatus.TIMING, "ERROR: COLLISION DETECTED"
        elif length == 0x91:
            return DaliStatus.FAILURE, "ERROR: SYSTEM FAILURE"
        elif length == 0x92:
            return DaliStatus.RECOVER, "SYSTEM RECOVER"
        elif length in (0xA0, 0xA1, 0xA2, 0xA3):
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

    def transmit(self, frame: DaliFrame, block: bool = False, is_query=False) -> None:
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
        self.port.write(command.encode("utf-8"))
        logger.debug(f"write <{command.strip()}>")
        if block:
            self.get_next(DaliInterface.RECEIVE_TIMEOUT)

    def query_reply(self, frame: DaliFrame) -> None:
        if not self.keep_running:
            logger.error("read thread is not running")
        logger.debug("flush queue")
        while not self.queue.empty():
            self.queue.get()
        self.transmit(frame, False, True)
        logger.debug("read loopback")
        self.get(timeout=DaliInterface.RECEIVE_TIMEOUT)
        if (
            not self.rx_frame
            or self.rx_frame.status.status != DaliStatus.LOOPBACK
            or self.rx_frame.data != frame.data
            or self.rx_frame.length != frame.length
        ):
            logger.error("unexpected result when reading loopback")
            return
        logger.debug("read backframe")
        self.get_next(timeout=DaliInterface.RECEIVE_TIMEOUT)
