import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "snapshot", Path(__file__).with_name("build_abi_architecture.py")
)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class ArchitectureSnapshotTest(unittest.TestCase):
    def test_adapters_are_separated_from_service_contracts(self):
        self.assertEqual(
            snapshot.classify(Path("naas_abi_core/services/event/EventService.py"))[2],
            "platform",
        )
        self.assertEqual(
            snapshot.classify(
                Path("naas_abi_core/services/event/adapters/secondary/Redis.py")
            )[2],
            "adapters",
        )
        self.assertEqual(
            snapshot.classify(
                Path("naas_abi_core/services/triple_store/TripleStore.py")
            )[2],
            "knowledge",
        )

    def test_counts_and_edges_ignore_tests_unresolved_and_inferred_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = "naas_abi/agents/ExampleAgent.py"
            service = "naas_abi_core/services/agent/Agent.py"
            for package, name, text in [
                ("naas-abi", agent, "class ExampleAgent:\n    def run(self): pass\n"),
                ("naas-abi-core", service, "def run(): pass\n"),
                (
                    "naas-abi-core",
                    service.replace("Agent.py", "Agent_test.py"),
                    "def test_run(): pass\n",
                ),
            ]:
                f = root / package / name
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(text)
            graph = {
                "nodes": [
                    {"id": "a", "source_file": agent},
                    {"id": "b", "source_file": service},
                ],
                "edges": [
                    {
                        "source": "a",
                        "target": "b",
                        "confidence": "EXTRACTED",
                        "relation": "calls",
                    },
                    {
                        "source": "a",
                        "target": "b",
                        "confidence": "INFERRED",
                        "relation": "calls",
                    },
                    {
                        "source": "a",
                        "target": "external",
                        "confidence": "EXTRACTED",
                        "relation": "imports",
                    },
                    {
                        "source": "a",
                        "target": "a",
                        "confidence": "EXTRACTED",
                        "relation": "calls",
                    },
                ],
            }
            result = snapshot.build(root, graph)
            self.assertEqual(len(result["edges"]), 1)
            self.assertEqual(result["edges"][0]["count"], 1)
            self.assertEqual(sum(c["files"] for c in result["components"]), 2)
            self.assertEqual(sum(c["tests"] for c in result["components"]), 1)
            self.assertEqual(sum(c["functions"] for c in result["components"]), 2)
            self.assertFalse(
                any(
                    str(root) in p
                    for c in result["components"]
                    for p in c["sourcePaths"]
                )
            )


if __name__ == "__main__":
    unittest.main()
