# DALI Interface

A common API for different hardware realizations of a DALI interface.

## Supported Hardware
* Lunatone 241 389 23DO
* BEGA 71024
* Serial based SevenLab Hardware

## API

The interface classes implement the following API functions.

### transmit

Transmits a DALI frame on the bus. All 8 bit frames are treated as backward franes.

'''python
    def transmit(
        self, frame: DaliFrame, block: bool = False, is_query: bool = False
    ) -> None:
'''

__Parameters__
* 'frame' (DaliFrame): frame to transmit
* 'block' (bool, optional): wait for the end of transmission. Defaults to False.
* 'is_query' (bool, optional): indicate that this is an query and request a reply frame. Defaults to False.


### get

Get the next DALI frame from the input queue.

'''python
    def get(self, timeout: float | None = None) -> DaliFrame:
'''

__Parameters__
* 'timeout' (float | None, optional): time in seconds before the call returns. Defaults to None (wait until halted).

__Returns__
* 'DaliFrame': time out is indicated in the frame status


### Query_Reply

Transmit a DALI frame that is requesting a reply. Wait for either
the replied data, or indicate a timeout.

'''python
    def query_reply(self, reuquest: DaliFrame) -> DaliFrame:
'''

__Parameters__
* 'reuquest' (DaliFrame): DALI frame to transmit

__Returns__
* 'DaliFrame': the received reply, if no reply was received a frame with DaliStatus:TIMEOUT is returned


#### DaliFrame

Class definition for DALI frames

#### DaliStatus

Class definition for status of DALI frames