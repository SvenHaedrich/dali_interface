# DALI Interface

A common API for different hardware realizations of a DALI interface.

## Supported Hardware

* Lunatone 241 389 23DO
* Lunatone 241 389 23-30
* BEGA 71024
* Serial based SevenLab Hardware

## API

The interface classes implement the following API functions.

### Transmit

Transmits a DALI frame on the bus. All 8 bit frames are treated as backward frames.

```python
    def transmit(self, frame: DaliFrame, block: bool = False) -> None:
```

**Parameters**

* `frame` (DaliFrame): frame to transmit
* `block` (bool, optional): wait for the end of transmission. Defaults to False.

### Get

Get the next DALI frame from the input queue.

```python
    def get(self, timeout: float | None = None) -> DaliFrame:
```

**Parameters**

* `timeout` (float | None, optional): time in seconds before the call returns. Defaults to None (wait until halted).

**Returns**

* `DaliFrame`: time out is indicated in the frame status

### Query_Reply

Transmit a DALI frame that is requesting a reply. Wait for either
the replied data, or indicate a timeout.

```python
    def query_reply(self, request: DaliFrame) -> DaliFrame:
```

**Parameters**

* `request` (DaliFrame): DALI frame to transmit

**Returns**

* `DaliFrame`: the received reply, if no reply was received a frame with `DaliStatus:TIMEOUT` is returned

### Power

Control a built in power supply. For now, this requires a Lunatone DALI USB 30 mA interface.

```python
    def power(self, power: bool = False) -> None:
```

**Parameters**

* `power` : new power setting: `True` for power on, `False` for power off

#### DaliFrame

Class definition for DALI frames

#### DaliStatus

Class definition for status of DALI frames
