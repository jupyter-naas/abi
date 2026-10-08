from naas_abi_core.proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EmailAttachment(_message.Message):
    __slots__ = ("filename", "content", "mime_type", "content_id", "is_inline")
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_ID_FIELD_NUMBER: _ClassVar[int]
    IS_INLINE_FIELD_NUMBER: _ClassVar[int]
    filename: str
    content: bytes
    mime_type: str
    content_id: str
    is_inline: bool
    def __init__(self, filename: _Optional[str] = ..., content: _Optional[bytes] = ..., mime_type: _Optional[str] = ..., content_id: _Optional[str] = ..., is_inline: _Optional[bool] = ...) -> None: ...

class SendRequest(_message.Message):
    __slots__ = ("context", "to_email", "subject", "text_body", "html_body", "from_email", "from_name", "reply_to", "attachments", "to_emails", "cc_emails")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    TO_EMAIL_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    TEXT_BODY_FIELD_NUMBER: _ClassVar[int]
    HTML_BODY_FIELD_NUMBER: _ClassVar[int]
    FROM_EMAIL_FIELD_NUMBER: _ClassVar[int]
    FROM_NAME_FIELD_NUMBER: _ClassVar[int]
    REPLY_TO_FIELD_NUMBER: _ClassVar[int]
    ATTACHMENTS_FIELD_NUMBER: _ClassVar[int]
    TO_EMAILS_FIELD_NUMBER: _ClassVar[int]
    CC_EMAILS_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    to_email: str
    subject: str
    text_body: str
    html_body: str
    from_email: str
    from_name: str
    reply_to: str
    attachments: _containers.RepeatedCompositeFieldContainer[EmailAttachment]
    to_emails: _containers.RepeatedScalarFieldContainer[str]
    cc_emails: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., to_email: _Optional[str] = ..., subject: _Optional[str] = ..., text_body: _Optional[str] = ..., html_body: _Optional[str] = ..., from_email: _Optional[str] = ..., from_name: _Optional[str] = ..., reply_to: _Optional[str] = ..., attachments: _Optional[_Iterable[_Union[EmailAttachment, _Mapping]]] = ..., to_emails: _Optional[_Iterable[str]] = ..., cc_emails: _Optional[_Iterable[str]] = ...) -> None: ...

class SendResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...
