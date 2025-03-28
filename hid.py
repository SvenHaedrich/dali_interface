"""Specific implementation of the DALI interface for Lunatone USB HID device."""

import errno
import logging
import struct
import time
from typing import Final

import usb
from typeguard import typechecked

from .dali_interface import DaliFrame, DaliInterface, DaliStatus

logger = logging.getLogger(__name__)


@typechecked
class DaliUsb(DaliInterface):  # pylint: disable=too-many-instance-attributes
    """Class for USB connected DALI interface."""

    _USB_VENDOR: Final[int] = 0x17B5
    _USB_PRODUCT: Final[int] = 0x0020

    _USB_CMD_INIT: Final[int] = 0x01
    _USB_CMD_BOOTLOADER: Final[int] = 0x02
    _USB_CMD_SEND: Final[int] = 0x12
    _USB_CMD_SEND_ANSWER: Final[int] = 0x15
    _USB_CMD_SET_IO_PINS: Final[int] = 0x20
    _USB_CMD_READ_IO_PINS: Final[int] = 0x21
    _USB_CMD_IDENTIFY: Final[int] = 0x22
    _USB_CMD_POWER: Final[int] = 0x40

    _USB_CTRL_DAPC: Final[int] = 0x04
    _USB_CTRL_DEV_TYPE: Final[int] = 0x80
    _USB_CTRL_SET_DTR: Final[int] = 0x10
    _USB_CTRL_TWICE: Final[int] = 0x20
    _USB_CTRL_ID: Final[int] = 0x40

    _USB_WRITE_TYPE_NO: Final[int] = 0x01
    _USB_WRITE_TYPE_8BIT: Final[int] = 0x02
    _USB_WRITE_TYPE_16BIT: Final[int] = 0x03
    _USB_WRITE_TYPE_25BIT: Final[int] = 0x04
    _USB_WRITE_TYPE_DSI: Final[int] = 0x05
    _USB_WRITE_TYPE_24BIT: Final[int] = 0x06
    _USB_WRITE_TYPE_STATUS: Final[int] = 0x07
    _USB_WRITE_TYPE_17BIT: Final[int] = 0x08

    _USB_READ_MODE_INFO: Final[int] = 0x01
    _USB_READ_MODE_OBSERVE: Final[int] = 0x11
    _USB_READ_MODE_RESPONSE: Final[int] = 0x12

    _USB_READ_TYPE_NO_FRAME: Final[int] = 0x71
    _USB_READ_TYPE_8BIT: Final[int] = 0x72
    _USB_READ_TYPE_16BIT: Final[int] = 0x73
    _USB_READ_TYPE_25BIT: Final[int] = 0x74
    _USB_READ_TYPE_DSI: Final[int] = 0x75
    _USB_READ_TYPE_24BIT: Final[int] = 0x76
    _USB_READ_TYPE_INFO: Final[int] = 0x77
    _USB_READ_TYPE_17BIT: Final[int] = 0x78
    _USB_READ_TYPE_32BIT: Final[int] = 0x7E

    _USB_STATUS_CHECKSUM: Final[int] = 0x01
    _USB_STATUS_SHORTED: Final[int] = 0x02
    _USB_STATUS_FRAME_ERROR: Final[int] = 0x03
    _USB_STATUS_OK: Final[int] = 0x04
    _USB_STATUS_DSI: Final[int] = 0x05
    _USB_STATUS_DALI: Final[int] = 0x06

    _USB_POWER_OFF: Final[int] = 0x00
    _USB_POWER_ON: Final[int] = 0x01

    def __init__(
        self,
        vendor: int = _USB_VENDOR,
        product: int = _USB_PRODUCT,
        start_receive: bool = True,
    ) -> None:
        """Initialise DALI USB interface."""
        # lookup devices by _USB_VENDOR and _USB_PRODUCT
        self.interface = 0
        self.send_sequence_number = 1
        self.receive_sequence_number = 0
        self.last_transmit: int | None = None

        logger.debug("try to discover DALI interfaces")
        devices = list(usb.core.find(find_all=True, idVendor=vendor, idProduct=product))

        # if not found
        if devices:
            logger.info(f"DALI interfaces found: {devices}")
        else:
            raise usb.core.USBError("DALI interface not found")

        # use first useable device on list
        i = 0
        while devices[i]:
            self.device = devices[i]
            i = i + 1
            self.device.reset()

            # detach kernel driver if necessary
            if self.device.is_kernel_driver_active(self.interface) is True:
                self.device.detach_kernel_driver(self.interface)

            self.device.set_configuration()
            usb.util.claim_interface(self.device, self.interface)
            cfg = self.device.get_active_configuration()
            interface = cfg[(0, 0)]  # type: ignore

            # get read and write endpoints
            self.ep_write = usb.util.find_descriptor(
                interface,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_OUT,
            )
            self.ep_read = usb.util.find_descriptor(
                interface,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
                == usb.util.ENDPOINT_IN,
            )
            if not self.ep_read or not self.ep_write:
                logger.info(
                    f"could not determine read or write endpoint on {self.device}"
                )
                continue

            logger.debug(
                f"usb descriptor string[2]: {usb.util.get_string(self.device, 2)}"
            )
            self.integrated_power_supply = (
                usb.util.get_string(self.device, 2) == "DALI USB with PS"
            )
            if self.integrated_power_supply:
                logger.debug("device has integrated power supply")

            # read pending messages and discard
            super().__init__(start_receive=start_receive)
            try:
                while True:
                    self.ep_read.read(self.ep_read.wMaxPacketSize, timeout=10)  # type: ignore
                    logger.info("DALI interface - disregard pending messages")
            except Exception:
                pass
            return
        # cleanup
        self.device = None
        self.ep_read = None
        self.ep_write = None
        raise usb.core.USBError("No suitable USB device found!")

    def power(self, power: bool = False) -> None:
        """Control a built-in power supply, requires a Lunatone DALI USB 30 mA interface"""
        logger.debug("control optional power supply")
        if not self.integrated_power_supply:
            raise RuntimeError("usb device must implement power")
        command = self._USB_CMD_POWER
        buffer = struct.pack(
            "BB" + (64 - 2) * "x",
            command,
            self._USB_POWER_ON if power else self._USB_POWER_OFF,
        )
        bytes_written = self.ep_write.write(buffer)  # type: ignore
        if bytes_written != 64:
            raise Exception("written {bytes_written} bytes, expected 64.")

    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
        """Transmit a DALI frame via USB interface."""
        command = self._USB_CMD_SEND
        self.send_sequence_number = (self.send_sequence_number + 1) & 0xFF
        sequence = self.send_sequence_number
        control = self._USB_CTRL_TWICE if frame.send_twice else 0
        if frame.length == 24:
            ext = (frame.data >> 16) & 0xFF
            address_byte = (frame.data >> 8) & 0xFF
            opcode_byte = frame.data & 0xFF
            write_type = self._USB_WRITE_TYPE_24BIT
        elif frame.length == 16:
            ext = 0x00
            address_byte = (frame.data >> 8) & 0xFF
            opcode_byte = frame.data & 0xFF
            write_type = self._USB_WRITE_TYPE_16BIT
        elif frame.length == 8:
            ext = 0x00
            address_byte = 0x00
            opcode_byte = frame.data & 0xFF
            write_type = self._USB_WRITE_TYPE_8BIT
            logger.debug(f"time is now: {time.time()}")
        else:
            raise Exception(
                f"DALI frames for the USB device can be 8,16 or 24 bit long. This frame is {frame.length} bit long."
            )

        logger.debug(
            f"DALI>OUT: CMD=0x{command:02X} SEQ=0x{sequence:02X} TYC=0x{write_type:02X} "
            f"EXT=0x{ext:02X} ADR=0x{address_byte:02X} OCB=0x{opcode_byte:02X}"
        )
        buffer = struct.pack(
            "BBBBxBBB" + (64 - 8) * "x",
            command,
            sequence,
            control,
            write_type,
            ext,
            address_byte,
            opcode_byte,
        )
        bytes_written = self.ep_write.write(buffer)  # type: ignore
        if bytes_written != 64:
            raise Exception("written {bytes_written} bytes, expected 64.")
        self.last_transmit = frame.data

        if block:
            if not self.keep_running:
                raise Exception("receive must be active for blocking call to transmit.")
            while True:
                self.get()
                if self.receive_sequence_number >= self.send_sequence_number:
                    return

    def close(self) -> None:
        """Close the connection to USB DALI interface."""
        super().close()
        usb.util.dispose_resources(self.device)

    def read_data(self) -> None:  # pylint: disable=too-many-branches
        """Read frame or event from USB DALI interface-"""
        try:
            usb_data = self.ep_read.read(self.ep_read.wMaxPacketSize, timeout=100)
            if usb_data:
                read_type = usb_data[1]
                self.receive_sequence_number = usb_data[8]
                logger.debug(
                    f"DALI[IN]: SN=0x{usb_data[8]:02X} TY=0x{usb_data[1]:02X} "
                    f"EC=0x{usb_data[3]:02X} AD=0x{usb_data[4]:02X} OC=0x{usb_data[5]:02X}"
                )
                if read_type == self._USB_READ_TYPE_8BIT:
                    status = DaliStatus.FRAME
                    length = 8
                    dali_data = usb_data[5]
                elif read_type == self._USB_READ_TYPE_16BIT:
                    status = DaliStatus.FRAME
                    length = 16
                    dali_data = usb_data[5] + (usb_data[4] << 8)
                elif read_type == self._USB_READ_TYPE_24BIT:
                    status = DaliStatus.FRAME
                    length = 24
                    dali_data = usb_data[5] + (usb_data[4] << 8) + (usb_data[3] << 16)
                elif read_type == self._USB_READ_TYPE_32BIT:
                    status = DaliStatus.FRAME
                    length = 32
                    dali_data = (
                        usb_data[5]
                        + (usb_data[4] << 8)
                        + (usb_data[3] << 16)
                        + (usb_data[2] << 24)
                    )
                elif read_type == self._USB_READ_TYPE_NO_FRAME:
                    status = DaliStatus.TIMEOUT
                    length = 0
                    dali_data = 0
                elif read_type == self._USB_READ_TYPE_INFO:
                    length = 0
                    dali_data = 0
                    if usb_data[5] == self._USB_STATUS_OK:
                        status = DaliStatus.OK
                    elif usb_data[5] == self._USB_STATUS_FRAME_ERROR:
                        status = DaliStatus.TIMING
                    else:
                        status = DaliStatus.GENERAL
                else:
                    return
                self.queue.put(
                    DaliFrame(
                        timestamp=time.time(),
                        length=length,
                        data=dali_data,
                        status=status,
                    )
                )
        except usb.USBError as e:
            if e.errno not in (errno.ETIMEDOUT, errno.ENODEV):
                raise e

    def query_reply(self, request: DaliFrame) -> DaliFrame:
        """Send DALI frame and request a reply frame."""
        self.flush_queue()
        self.transmit(request, True)
        logger.debug("read backframe")
        return self.get(timeout=DaliInterface.RECEIVE_TIMEOUT)
