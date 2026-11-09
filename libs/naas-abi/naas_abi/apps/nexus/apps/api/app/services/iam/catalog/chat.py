"""Chat conversations: personal, so a member reaches their own."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("conversation", id="path", personal=True),)

ACTIONS = (
    action("ListConversations", "list", "conversation", feature="chat"),
    action("GetConversation", "read", "conversation", feature="chat"),
    action("CreateConversation", "write", "conversation", feature="chat"),
    # Complete or stream a turn: it stores both messages.
    action("SendMessage", "write", "conversation", feature="chat"),
    # Rename, pin, archive, and the metadata a client attaches to a message.
    action("UpdateConversation", "write", "conversation", feature="chat"),
    action("DeleteConversation", "write", "conversation", feature="chat"),
    # Upload or pick a file into the conversation's index.
    action("IngestConversationFile", "write", "conversation", feature="chat"),
    action("ExportConversation", "read", "conversation", feature="chat"),
    action("GetIngestionJob", "read", "conversation", feature="chat"),
)
