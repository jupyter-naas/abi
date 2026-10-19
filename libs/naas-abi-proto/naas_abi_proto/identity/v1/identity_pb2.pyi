from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Provider(_message.Message):
    __slots__ = ("name", "issuer", "client_id", "display_name", "scopes", "groups_claim", "provisioning")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ISSUER_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    GROUPS_CLAIM_FIELD_NUMBER: _ClassVar[int]
    PROVISIONING_FIELD_NUMBER: _ClassVar[int]
    name: str
    issuer: str
    client_id: str
    display_name: str
    scopes: _containers.RepeatedScalarFieldContainer[str]
    groups_claim: str
    provisioning: str
    def __init__(self, name: _Optional[str] = ..., issuer: _Optional[str] = ..., client_id: _Optional[str] = ..., display_name: _Optional[str] = ..., scopes: _Optional[_Iterable[str]] = ..., groups_claim: _Optional[str] = ..., provisioning: _Optional[str] = ...) -> None: ...

class VerifiedToken(_message.Message):
    __slots__ = ("provider", "issuer", "subject", "audience", "issued_at", "expires_at", "email", "email_verified", "display_name", "groups", "nonce", "session_id", "claims_json")
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    ISSUER_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    ISSUED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    EMAIL_VERIFIED_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    GROUPS_FIELD_NUMBER: _ClassVar[int]
    NONCE_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CLAIMS_JSON_FIELD_NUMBER: _ClassVar[int]
    provider: str
    issuer: str
    subject: str
    audience: _containers.RepeatedScalarFieldContainer[str]
    issued_at: int
    expires_at: int
    email: str
    email_verified: bool
    display_name: str
    groups: _containers.RepeatedScalarFieldContainer[str]
    nonce: str
    session_id: str
    claims_json: str
    def __init__(self, provider: _Optional[str] = ..., issuer: _Optional[str] = ..., subject: _Optional[str] = ..., audience: _Optional[_Iterable[str]] = ..., issued_at: _Optional[int] = ..., expires_at: _Optional[int] = ..., email: _Optional[str] = ..., email_verified: bool = ..., display_name: _Optional[str] = ..., groups: _Optional[_Iterable[str]] = ..., nonce: _Optional[str] = ..., session_id: _Optional[str] = ..., claims_json: _Optional[str] = ...) -> None: ...

class AuthenticatedUser(_message.Message):
    __slots__ = ("principal_id", "token", "group_ids")
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    GROUP_IDS_FIELD_NUMBER: _ClassVar[int]
    principal_id: str
    token: VerifiedToken
    group_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, principal_id: _Optional[str] = ..., token: _Optional[_Union[VerifiedToken, _Mapping]] = ..., group_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class TokenSet(_message.Message):
    __slots__ = ("id_token", "access_token", "refresh_token", "expires_in", "token_type", "scope")
    ID_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_IN_FIELD_NUMBER: _ClassVar[int]
    TOKEN_TYPE_FIELD_NUMBER: _ClassVar[int]
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    id_token: str
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    scope: str
    def __init__(self, id_token: _Optional[str] = ..., access_token: _Optional[str] = ..., refresh_token: _Optional[str] = ..., expires_in: _Optional[int] = ..., token_type: _Optional[str] = ..., scope: _Optional[str] = ...) -> None: ...

class SignIn(_message.Message):
    __slots__ = ("user", "tokens", "refresh_at")
    USER_FIELD_NUMBER: _ClassVar[int]
    TOKENS_FIELD_NUMBER: _ClassVar[int]
    REFRESH_AT_FIELD_NUMBER: _ClassVar[int]
    user: AuthenticatedUser
    tokens: TokenSet
    refresh_at: int
    def __init__(self, user: _Optional[_Union[AuthenticatedUser, _Mapping]] = ..., tokens: _Optional[_Union[TokenSet, _Mapping]] = ..., refresh_at: _Optional[int] = ...) -> None: ...

class ListProvidersRequest(_message.Message):
    __slots__ = ("context",)
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ...) -> None: ...

class ListProvidersResponse(_message.Message):
    __slots__ = ("error", "providers", "default_provider")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PROVIDERS_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    providers: _containers.RepeatedCompositeFieldContainer[Provider]
    default_provider: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., providers: _Optional[_Iterable[_Union[Provider, _Mapping]]] = ..., default_provider: _Optional[str] = ...) -> None: ...

class GetProviderRequest(_message.Message):
    __slots__ = ("context", "name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...

class GetProviderResponse(_message.Message):
    __slots__ = ("error", "provider")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    provider: Provider
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., provider: _Optional[_Union[Provider, _Mapping]] = ...) -> None: ...

class VerifyTokenRequest(_message.Message):
    __slots__ = ("context", "token", "nonce")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    NONCE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    token: str
    nonce: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., token: _Optional[str] = ..., nonce: _Optional[str] = ...) -> None: ...

class VerifyTokenResponse(_message.Message):
    __slots__ = ("error", "token")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    token: VerifiedToken
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., token: _Optional[_Union[VerifiedToken, _Mapping]] = ...) -> None: ...

class AuthenticateRequest(_message.Message):
    __slots__ = ("context", "token", "nonce")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    NONCE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    token: str
    nonce: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., token: _Optional[str] = ..., nonce: _Optional[str] = ...) -> None: ...

class AuthenticateResponse(_message.Message):
    __slots__ = ("error", "user")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    user: AuthenticatedUser
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., user: _Optional[_Union[AuthenticatedUser, _Mapping]] = ...) -> None: ...

class AuthorizationUrlRequest(_message.Message):
    __slots__ = ("context", "provider", "redirect_uri", "state", "nonce", "code_challenge", "login_hint", "prompt")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    REDIRECT_URI_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    NONCE_FIELD_NUMBER: _ClassVar[int]
    CODE_CHALLENGE_FIELD_NUMBER: _ClassVar[int]
    LOGIN_HINT_FIELD_NUMBER: _ClassVar[int]
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    redirect_uri: str
    state: str
    nonce: str
    code_challenge: str
    login_hint: str
    prompt: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., redirect_uri: _Optional[str] = ..., state: _Optional[str] = ..., nonce: _Optional[str] = ..., code_challenge: _Optional[str] = ..., login_hint: _Optional[str] = ..., prompt: _Optional[str] = ...) -> None: ...

class AuthorizationUrlResponse(_message.Message):
    __slots__ = ("error", "url")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    url: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., url: _Optional[str] = ...) -> None: ...

class ExchangeCodeRequest(_message.Message):
    __slots__ = ("context", "provider", "code", "code_verifier", "redirect_uri", "nonce")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    CODE_VERIFIER_FIELD_NUMBER: _ClassVar[int]
    REDIRECT_URI_FIELD_NUMBER: _ClassVar[int]
    NONCE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    code: str
    code_verifier: str
    redirect_uri: str
    nonce: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., code: _Optional[str] = ..., code_verifier: _Optional[str] = ..., redirect_uri: _Optional[str] = ..., nonce: _Optional[str] = ...) -> None: ...

class ExchangeCodeResponse(_message.Message):
    __slots__ = ("error", "sign_in")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    SIGN_IN_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    sign_in: SignIn
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., sign_in: _Optional[_Union[SignIn, _Mapping]] = ...) -> None: ...

class RefreshRequest(_message.Message):
    __slots__ = ("context", "provider", "refresh_token", "principal_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    PRINCIPAL_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    refresh_token: str
    principal_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., refresh_token: _Optional[str] = ..., principal_id: _Optional[str] = ...) -> None: ...

class RefreshResponse(_message.Message):
    __slots__ = ("error", "sign_in")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    SIGN_IN_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    sign_in: SignIn
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., sign_in: _Optional[_Union[SignIn, _Mapping]] = ...) -> None: ...

class RevokeRequest(_message.Message):
    __slots__ = ("context", "provider", "refresh_token")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    refresh_token: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., refresh_token: _Optional[str] = ...) -> None: ...

class RevokeResponse(_message.Message):
    __slots__ = ("error", "revoked")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REVOKED_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    revoked: bool
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., revoked: bool = ...) -> None: ...

class EndSessionUrlRequest(_message.Message):
    __slots__ = ("context", "provider", "id_token_hint", "post_logout_redirect_uri", "state")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    ID_TOKEN_HINT_FIELD_NUMBER: _ClassVar[int]
    POST_LOGOUT_REDIRECT_URI_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    id_token_hint: str
    post_logout_redirect_uri: str
    state: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., id_token_hint: _Optional[str] = ..., post_logout_redirect_uri: _Optional[str] = ..., state: _Optional[str] = ...) -> None: ...

class EndSessionUrlResponse(_message.Message):
    __slots__ = ("error", "url")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    url: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., url: _Optional[str] = ...) -> None: ...

class ProvisionedUser(_message.Message):
    __slots__ = ("provider", "email", "subject", "name", "created", "disabled")
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    DISABLED_FIELD_NUMBER: _ClassVar[int]
    provider: str
    email: str
    subject: str
    name: str
    created: bool
    disabled: bool
    def __init__(self, provider: _Optional[str] = ..., email: _Optional[str] = ..., subject: _Optional[str] = ..., name: _Optional[str] = ..., created: bool = ..., disabled: bool = ...) -> None: ...

class ProvisionUserRequest(_message.Message):
    __slots__ = ("context", "provider", "email", "name")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    email: str
    name: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class ProvisionUserResponse(_message.Message):
    __slots__ = ("error", "user")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    user: ProvisionedUser
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., user: _Optional[_Union[ProvisionedUser, _Mapping]] = ...) -> None: ...

class FindProvisionedUserRequest(_message.Message):
    __slots__ = ("context", "provider", "email")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PROVIDER_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    provider: str
    email: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., provider: _Optional[str] = ..., email: _Optional[str] = ...) -> None: ...

class FindProvisionedUserResponse(_message.Message):
    __slots__ = ("error", "user")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    user: ProvisionedUser
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., user: _Optional[_Union[ProvisionedUser, _Mapping]] = ...) -> None: ...
