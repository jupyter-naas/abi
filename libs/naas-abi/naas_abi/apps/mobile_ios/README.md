# ABI Chat for iOS

Native SwiftUI iOS client for the ABI Desktop chat API.

Target: iOS 16+ with Xcode 15 or newer.

## What is included

- Chat list for `section=chat`
- New chat creation
- Message history
- Server-sent event streaming for assistant replies
- Abort generation
- Configurable backend URL stored on device

## Run locally

Start the desktop backend:

```bash
uv run python libs/naas-abi/naas_abi/apps/desktop/run.py
```

Then open:

```bash
open libs/naas-abi/naas_abi/apps/mobile_ios/ABIChat.xcodeproj
```

For the iOS simulator, keep the server URL as:

```text
http://127.0.0.1:55031
```

For a physical iPhone, use your Mac's LAN IP address and run the ABI backend on
a reachable host/port.

## Backend contract

The app talks to the existing ABI Desktop endpoints:

- `GET /api/chats?section=chat`
- `POST /api/chats`
- `GET /api/chats/{id}/messages`
- `POST /api/chats/{id}/messages`
- `POST /api/chats/{id}/abort`

`POST /messages` is consumed as `text/event-stream`; cumulative `text` and
`complete` events update the visible assistant draft, and `end` finalizes it.
