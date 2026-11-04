import importlib
from pathlib import Path

import naas_abi_proto


def test_all_request_response_pairs_roundtrip():
    root = Path(naas_abi_proto.__file__).parent
    count = 0
    for file in root.glob("*/v1/*_pb2.py"):
        module = importlib.import_module(
            "naas_abi_proto." + ".".join(file.relative_to(root).with_suffix("").parts)
        )
        for name in module.DESCRIPTOR.message_types_by_name:
            if name.endswith("Request"):
                request = getattr(module, name)()
                request.context.trace_id = "trace"
                decoded = type(request).FromString(request.SerializeToString())
                assert decoded.context.trace_id == "trace"
                response = getattr(module, name.removesuffix("Request") + "Response")()
                assert response.DESCRIPTOR.fields_by_name["error"]
                count += 1
    assert count >= 100


def test_calls_and_placements_carry_container_names():
    from naas_abi_proto.common.v1 import common_pb2
    from naas_abi_proto.iam.v1 import iam_pb2

    def numbers(message):
        return {f.name: f.number for f in message.DESCRIPTOR.fields}

    # SDK 0.2's workspace_id keeps its number so an engine can refuse it.
    assert numbers(common_pb2.CallContext)["container"] == 6
    assert numbers(common_pb2.CallContext)["workspace_id"] == 4
    assert numbers(iam_pb2.Placement) == {"service": 1, "id_key": 2, "container": 5}
    assert numbers(iam_pb2.AuthorizeDeclaredRequest)["container"] == 6
    assert "workspace_id" not in numbers(iam_pb2.AuthorizeDeclaredRequest)
    # The field once named container keeps its number as id_prefix.
    resource_type = numbers(iam_pb2.ResourceType)
    assert (resource_type["id_prefix"], resource_type["container"]) == (4, 9)
    assert resource_type["platform_companions"] == 10
    assert numbers(iam_pb2.ActionSpec)["deletes"] == 8
    assert "org" not in numbers(iam_pb2.Principal)
    assert "org" not in numbers(iam_pb2.CreateGroupRequest)
    for name in ("Scope", "PutScopeRequest", "DeleteScopeRequest"):
        assert name not in iam_pb2.DESCRIPTOR.message_types_by_name
    for name in ("RegisterContainer", "DeleteContainer", "GetContainer"):
        assert f"{name}Request" in iam_pb2.DESCRIPTOR.message_types_by_name
