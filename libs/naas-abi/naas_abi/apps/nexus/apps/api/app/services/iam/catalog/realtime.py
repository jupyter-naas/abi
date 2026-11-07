"""Presence and broadcast of a workspace, and speech (voice input and read-aloud)."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("presence", id="singleton"),
    rtype("speech", id="singleton"),
)

ACTIONS = (
    action("GetPresence", "read", "presence"),
    # What a client sends into the workspace's room: typing, cursors, messages.
    action("Broadcast", "write", "presence"),
    action("Transcribe", "read", "speech", feature="chat"),
    action("Speak", "read", "speech", feature="chat"),
)
