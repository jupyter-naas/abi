"""What a module manifest hashes: the same before and after a catalog's format
existed, so no module comes back for approval on an upgrade."""

from naas_abi_core.services.iam import modules
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.policy import PolicyDocument, Statement

CATALOG = ActionCatalog(
    service="acme_people",
    version=2,
    resource_types=(
        ResourceType("person", module_scope=True, description="A person."),
    ),
    actions=(ActionSpec("GetPerson", "read", ("person",), description="Read one."),),
    module="acme.people",
)
POLICY = PolicyDocument(
    statements=(Statement("Allow", ("triple_store:Query",), ("*",), sid="Read"),)
)
# The catalog as the version before the format wrote it into a manifest.
BEFORE = {
    "service": "acme_people",
    "version": 2,
    "resource_types": [
        {
            "name": "person",
            "id": "opaque",
            "placement": "placed",
            "container": False,
            "personal": False,
            "description": "A person.",
            "module_scope": True,
        }
    ],
    "actions": [
        {
            "name": "GetPerson",
            "level": "read",
            "resource_types": ["person"],
            "creates": False,
            "subjects": [],
            "description": "Read one.",
        }
    ],
    "module": "acme.people",
}
# ``manifest_sha256`` of that manifest, as the version before the format stored it.
SHA_BEFORE = "589f007ff8bb3dcd6f78a2ddd9b4a6534c4d67149e57d2fe8d0e2eec676fa9d9"


def test_a_manifest_with_a_catalog_hashes_as_before_the_format():
    document = modules.manifest_document(POLICY, CATALOG)
    assert document[modules.MANIFEST_CATALOG] == BEFORE
    assert modules.manifest_sha256(document) == SHA_BEFORE
