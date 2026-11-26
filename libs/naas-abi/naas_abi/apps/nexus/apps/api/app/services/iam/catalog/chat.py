"""Chat conversations: personal, so a member reaches their own. And the chat models a
workspace uses (``model/<canonical id>``): where its offer names them
(``OfferModels``), no role's, the level policies grant the type and the offer bounds
it (``iam/workspace_models``)."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("conversation", id="path", personal=True),
    rtype("model", policy_only=True),
)

ACTIONS = (
    action("ListConversations", "list", "conversation", feature="chat"),
    action("GetConversation", "read", "conversation", feature="chat"),
    action("CreateConversation", "write", "conversation", feature="chat"),
    # Complete or stream a turn: it stores both messages.
    action("SendMessage", "write", "conversation", feature="chat"),
    # Rename, pin, archive, the metadata a client attaches to a message and the
    # owner's like or dislike of an answer.
    action("UpdateConversation", "write", "conversation", feature="chat"),
    action("DeleteConversation", "write", "conversation", feature="chat"),
    # Upload or pick a file into the conversation's index.
    action("IngestConversationFile", "write", "conversation", feature="chat"),
    action("ExportConversation", "read", "conversation", feature="chat"),
    action("GetIngestionJob", "read", "conversation", feature="chat"),
    # Chat with a model in the workspace: its offer names which (``*``: every model the
    # person's model set allows), with the model an agent of another is switched to.
    action("UseModel", "write", "model", feature="chat"),
)
