from naas_abi_proto.common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AgentDescriptor(_message.Message):
    __slots__ = ("name", "description", "contract_major", "capabilities")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_MAJOR_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    contract_major: int
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., contract_major: _Optional[int] = ..., capabilities: _Optional[_Iterable[str]] = ...) -> None: ...

class Dependency(_message.Message):
    __slots__ = ("module_id", "contract_major")
    MODULE_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_MAJOR_FIELD_NUMBER: _ClassVar[int]
    module_id: str
    contract_major: int
    def __init__(self, module_id: _Optional[str] = ..., contract_major: _Optional[int] = ...) -> None: ...

class ModuleDescriptor(_message.Message):
    __slots__ = ("module_id", "package_version", "contract_major", "dependencies", "agents")
    MODULE_ID_FIELD_NUMBER: _ClassVar[int]
    PACKAGE_VERSION_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_MAJOR_FIELD_NUMBER: _ClassVar[int]
    DEPENDENCIES_FIELD_NUMBER: _ClassVar[int]
    AGENTS_FIELD_NUMBER: _ClassVar[int]
    module_id: str
    package_version: str
    contract_major: int
    dependencies: _containers.RepeatedCompositeFieldContainer[Dependency]
    agents: _containers.RepeatedCompositeFieldContainer[AgentDescriptor]
    def __init__(self, module_id: _Optional[str] = ..., package_version: _Optional[str] = ..., contract_major: _Optional[int] = ..., dependencies: _Optional[_Iterable[_Union[Dependency, _Mapping]]] = ..., agents: _Optional[_Iterable[_Union[AgentDescriptor, _Mapping]]] = ...) -> None: ...

class Instance(_message.Message):
    __slots__ = ("descriptor", "instance_id", "status", "expires_at")
    DESCRIPTOR_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    descriptor: ModuleDescriptor
    instance_id: str
    status: str
    expires_at: float
    def __init__(self, descriptor: _Optional[_Union[ModuleDescriptor, _Mapping]] = ..., instance_id: _Optional[str] = ..., status: _Optional[str] = ..., expires_at: _Optional[float] = ...) -> None: ...

class RegisterRequest(_message.Message):
    __slots__ = ("context", "descriptor", "instance_id", "lease_token")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTOR_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    descriptor: ModuleDescriptor
    instance_id: str
    lease_token: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., descriptor: _Optional[_Union[ModuleDescriptor, _Mapping]] = ..., instance_id: _Optional[str] = ..., lease_token: _Optional[str] = ...) -> None: ...

class RegisterResponse(_message.Message):
    __slots__ = ("error", "instance", "lease_seconds")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    LEASE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    instance: Instance
    lease_seconds: float
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., instance: _Optional[_Union[Instance, _Mapping]] = ..., lease_seconds: _Optional[float] = ...) -> None: ...

class RenewRequest(_message.Message):
    __slots__ = ("context", "instance_id", "lease_token", "initialized", "draining")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    INITIALIZED_FIELD_NUMBER: _ClassVar[int]
    DRAINING_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    instance_id: str
    lease_token: str
    initialized: bool
    draining: bool
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., instance_id: _Optional[str] = ..., lease_token: _Optional[str] = ..., initialized: bool = ..., draining: bool = ...) -> None: ...

class RenewResponse(_message.Message):
    __slots__ = ("error", "instance", "lease_seconds")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    LEASE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    instance: Instance
    lease_seconds: float
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., instance: _Optional[_Union[Instance, _Mapping]] = ..., lease_seconds: _Optional[float] = ...) -> None: ...

class UnregisterRequest(_message.Message):
    __slots__ = ("context", "instance_id", "lease_token")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    instance_id: str
    lease_token: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., instance_id: _Optional[str] = ..., lease_token: _Optional[str] = ...) -> None: ...

class UnregisterResponse(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ...) -> None: ...

class GetModuleRequest(_message.Message):
    __slots__ = ("context", "module_id", "contract_major")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    MODULE_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_MAJOR_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    module_id: str
    contract_major: int
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., module_id: _Optional[str] = ..., contract_major: _Optional[int] = ...) -> None: ...

class GetModuleResponse(_message.Message):
    __slots__ = ("error", "instances")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    instances: _containers.RepeatedCompositeFieldContainer[Instance]
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., instances: _Optional[_Iterable[_Union[Instance, _Mapping]]] = ...) -> None: ...

class ListModulesRequest(_message.Message):
    __slots__ = ("context", "limit", "after_instance_id")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    AFTER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    context: _common_pb2.CallContext
    limit: int
    after_instance_id: str
    def __init__(self, context: _Optional[_Union[_common_pb2.CallContext, _Mapping]] = ..., limit: _Optional[int] = ..., after_instance_id: _Optional[str] = ...) -> None: ...

class ListModulesResponse(_message.Message):
    __slots__ = ("error", "instances", "next_after_instance_id")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    NEXT_AFTER_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    error: _common_pb2.CallError
    instances: _containers.RepeatedCompositeFieldContainer[Instance]
    next_after_instance_id: str
    def __init__(self, error: _Optional[_Union[_common_pb2.CallError, _Mapping]] = ..., instances: _Optional[_Iterable[_Union[Instance, _Mapping]]] = ..., next_after_instance_id: _Optional[str] = ...) -> None: ...

class RegistryRecord(_message.Message):
    __slots__ = ("instance", "owner", "lease_hash", "initialized", "draining")
    INSTANCE_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    LEASE_HASH_FIELD_NUMBER: _ClassVar[int]
    INITIALIZED_FIELD_NUMBER: _ClassVar[int]
    DRAINING_FIELD_NUMBER: _ClassVar[int]
    instance: Instance
    owner: str
    lease_hash: str
    initialized: bool
    draining: bool
    def __init__(self, instance: _Optional[_Union[Instance, _Mapping]] = ..., owner: _Optional[str] = ..., lease_hash: _Optional[str] = ..., initialized: bool = ..., draining: bool = ...) -> None: ...

class RegistryState(_message.Message):
    __slots__ = ("records",)
    RECORDS_FIELD_NUMBER: _ClassVar[int]
    records: _containers.RepeatedCompositeFieldContainer[RegistryRecord]
    def __init__(self, records: _Optional[_Iterable[_Union[RegistryRecord, _Mapping]]] = ...) -> None: ...
