"""Document domain/protobuf mapping, shared by the two transport adapters."""

from datetime import datetime
from typing import cast

from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    Document,
    DocumentAdapterError,
    DocumentNotFound,
    DocumentStorageError,
    FieldSpec,
    Operator,
    OrderBy,
    Predicate,
    UniqueViolation,
    VersionConflict,
)
from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import (
    decode_data,
    decode_value,
    encode_data,
    encode_value,
)

ERRORS = {
    "DOCUMENT_NOT_FOUND": DocumentNotFound,
    "COLLECTION_NOT_FOUND": CollectionNotFound,
    "VERSION_CONFLICT": VersionConflict,
    "UNIQUE_VIOLATION": UniqueViolation,
    "STORAGE_ERROR": DocumentStorageError,
    "ADAPTER_ERROR": DocumentAdapterError,
    "INVALID_ARGUMENT": ValueError,
}


def encode_spec(spec: CollectionSpec) -> pb.CollectionSpec:
    return pb.CollectionSpec(
        name=spec.name,
        fields=[pb.FieldSpec(**f.model_dump()) for f in spec.fields],
        unique_together=[pb.UniqueGroup(fields=g) for g in spec.unique_together],
    )


def decode_spec(spec: pb.CollectionSpec) -> CollectionSpec:
    return CollectionSpec(
        name=spec.name,
        fields=tuple(
            FieldSpec.model_validate(
                {
                    "name": f.name,
                    "type": f.type,
                    "indexed": f.indexed,
                    "unique": f.unique,
                }
            )
            for f in spec.fields
        ),
        unique_together=tuple(tuple(g.fields) for g in spec.unique_together),
    )


def encode_document(doc: Document) -> pb.Document:
    return pb.Document(
        id=doc.id,
        data=encode_data(doc.data),
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
        version=doc.version,
    )


def decode_document(doc: pb.Document) -> Document:
    return Document(
        doc.id,
        decode_data(doc.data),
        datetime.fromisoformat(doc.created_at),
        datetime.fromisoformat(doc.updated_at),
        doc.version,
    )


def encode_where(where) -> list[pb.Predicate]:
    return [
        pb.Predicate(field=f, operator=o, value=encode_value(v)) for f, o, v in where
    ]


def decode_where(where) -> tuple[Predicate, ...]:
    return tuple(
        (p.field, cast(Operator, p.operator), decode_value(p.value)) for p in where
    )


def decode_order(request) -> OrderBy:
    return (
        cast(OrderBy, (request.order_by.field, request.order_by.direction))
        if request.HasField("order_by")
        else None
    )
