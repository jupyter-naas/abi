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
