# EmailClient

## What it is
An asynchronous client for the `abi.svc.email.v1` service. It sends protobuf request messages over a provided `Transport` and returns protobuf responses.

## Public API
- **Class: `EmailClient`**
  - `__init__(transport: Transport) -> None`
    - Stores a transport used to perform RPC calls.
  - `async send(request: pb.SendRequest) -> pb.SendResponse`
    - Calls service method `"abi.svc.email.v1.send"`.
  - `async list_sent(request: pb.ListSentRequest) -> pb.ListSentResponse`
    - Calls service method `"abi.svc.email.v1.list_sent"`.
  - `async get_sent(request: pb.GetSentRequest) -> pb.GetSentResponse`
    - Calls service method `"abi.svc.email.v1.get_sent"`.
  - `async delete_sent(request: pb.DeleteSentRequest) -> pb.DeleteSentResponse`
    - Calls service method `"abi.svc.email.v1.delete_sent"`.

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_sdk.transport.Transport`: must provide an async method `call(method: str, request, response_type)`.
  - `naas_abi_proto.email.v1.email_pb2` imported as `pb`: provides request/response protobuf message classes used by the methods.

## Usage
```python
import asyncio
from naas_abi_sdk.email import EmailClient
from naas_abi_proto.email.v1 import email_pb2 as pb

async def main(transport):
    client = EmailClient(transport)

    req = pb.SendRequest()  # populate required fields as defined by the proto
    resp = await client.send(req)
    print(resp)

# asyncio.run(main(transport))  # provide a concrete Transport instance
```

## Caveats
- All client methods are **async** and require an event loop.
- Request message fields/validation are defined by the protobuf schema (`email_pb2`), not by this client.
