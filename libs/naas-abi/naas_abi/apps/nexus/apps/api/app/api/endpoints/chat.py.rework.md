# chat rework

## Goal

Refactor the chats.py to follow the hexagonal architecture. The goal is to isolate:
- FastAPI logic
- Business logic around the chats themselves: users, chat access, security, permissions, etc.
- Data access logic: database interactions

This will make it easier to test, maintain and extend the chat functionality.
