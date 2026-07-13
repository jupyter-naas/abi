# ABI Mobile iOS - AGENTS.md

> Scope: `libs/naas-abi/naas_abi/apps/mobile_ios/`. A native iOS chat-only client for ABI.

## Purpose

Small SwiftUI iOS app that talks to the ABI Desktop local HTTP API. The first
iteration intentionally contains only chat: conversation list, message history,
streamed assistant replies, and a configurable server URL.

## Architecture

- `ABIChat.xcodeproj/` is the Xcode project.
- `ABIChat/` contains app source.
- No Python imports and no dependency on the ABI engine.
- Network access goes through `ABIClient`.
- UI state and chat orchestration live in `ChatViewModel`.
- User-configurable settings live in `SettingsStore`.

## API Surface

The app targets the desktop backend chat endpoints:

- `GET /api/chats?section=chat`
- `POST /api/chats`
- `GET /api/chats/{id}/messages`
- `POST /api/chats/{id}/messages` as `text/event-stream`
- `POST /api/chats/{id}/abort`

## Run

1. Start ABI Desktop or its backend.
2. Open `ABIChat.xcodeproj` in Xcode.
3. Run the `ABIChat` scheme on an iOS simulator.
4. Use `http://127.0.0.1:55031` for simulator-to-Mac local backend access.

For a physical iPhone, set the server URL to the Mac LAN address and make sure
the backend binds to an address reachable from the phone.

## Tests

There are no automated iOS tests yet. For now, verify by running the simulator
against a live desktop backend and sending a chat message.

