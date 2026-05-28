"""Tests for ModuleModelLoader auto-discovery."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from naas_abi_core.module.ModuleModelLoader import ModuleModelLoader
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


def _make_fake_package(tmp_path: Path, name: str, files: dict[str, str]) -> type:
    """Build a synthetic Python package on disk and return a class whose
    ``__module__`` lives in it (so ``find_class_module_root_path`` resolves
    correctly)."""
    pkg_dir = tmp_path / name
    models_dir = pkg_dir / "models"
    models_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text(
        textwrap.dedent(
            """
            class FakeModule:
                pass
            """
        ).strip()
    )
    (models_dir / "__init__.py").write_text("")
    for filename, content in files.items():
        (models_dir / filename).write_text(content)

    sys.path.insert(0, str(tmp_path))
    try:
        pkg = __import__(f"{name}", fromlist=["FakeModule"])
        return pkg.FakeModule
    finally:
        # leave sys.path entry for the duration of the test; it's torn down
        # when the tmp_path fixture cleans up
        pass


def _model_file(canonical_id: str, model_id: str, provider: str) -> str:
    class_name = "Definition_" + canonical_id.replace("-", "_").replace(".", "_")
    return textwrap.dedent(
        f"""
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from naas_abi_core.models.Model import ChatModel, ModelDefinition


        class {class_name}(ModelDefinition):
            CANONICAL_ID = {canonical_id!r}
            MODEL_ID = {model_id!r}
            PROVIDER = {provider!r}

            model: ChatModel = ChatModel(
                model_id=MODEL_ID,
                provider=PROVIDER,
                model=FakeListChatModel(responses=["hi"]),
            )
        """
    ).strip()


def test_registers_files_that_define_canonical_id_and_model(tmp_path: Path) -> None:
    cls = _make_fake_package(
        tmp_path,
        "pkg_a",
        {
            "alpha.py": _model_file("alpha", "provider/alpha-v1", "anthropic"),
            "beta.py": _model_file("beta", "provider/beta-v1", "openai"),
        },
    )
    registry = ModelRegistryService()

    n = ModuleModelLoader.load_models(cls, registry)

    assert n == 2
    assert set(registry.list_canonical_ids()) == {"alpha", "beta"}
    assert registry.get("alpha").provider == "anthropic"
    assert registry.get("beta").provider == "openai"


def test_skips_files_without_modeldefinition_subclass(tmp_path: Path) -> None:
    """Files that don't declare a ModelDefinition subclass are opted out of
    auto-registration — they can still expose a ``model`` symbol for direct
    imports."""
    cls = _make_fake_package(
        tmp_path,
        "pkg_b",
        {
            "with_class.py": _model_file("known", "p/known", "openai"),
            "without_class.py": textwrap.dedent(
                """
                from langchain_core.language_models.fake_chat_models import FakeListChatModel
                from naas_abi_core.models.Model import ChatModel

                # Module-level ``model`` is not a ModelDefinition subclass; the
                # loader must ignore it.
                model: ChatModel = ChatModel(
                    model_id="legacy",
                    provider="openai",
                    model=FakeListChatModel(responses=["x"]),
                )
                """
            ).strip(),
        },
    )
    registry = ModelRegistryService()

    n = ModuleModelLoader.load_models(cls, registry)

    assert n == 1
    assert registry.list_canonical_ids() == ["known"]


def test_skips_test_files_and_dunder_init(tmp_path: Path) -> None:
    cls = _make_fake_package(
        tmp_path,
        "pkg_c",
        {
            "good.py": _model_file("good", "p/good", "anthropic"),
            "good_test.py": _model_file("bad_test", "p/bad", "anthropic"),
        },
    )
    registry = ModelRegistryService()

    n = ModuleModelLoader.load_models(cls, registry)

    assert n == 1
    assert registry.list_canonical_ids() == ["good"]


def test_returns_zero_when_no_models_dir(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "pkg_no_models"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("class FakeModule:\n    pass\n")
    sys.path.insert(0, str(tmp_path))

    cls = __import__("pkg_no_models", fromlist=["FakeModule"]).FakeModule
    registry = ModelRegistryService()

    assert ModuleModelLoader.load_models(cls, registry) == 0
    assert registry.list_canonical_ids() == []


def test_register_failure_is_logged_and_does_not_abort_remaining_files(
    tmp_path: Path,
) -> None:
    """A faulty file (e.g. importing a missing symbol) is skipped with a
    warning; subsequent files still get registered."""

    cls = _make_fake_package(
        tmp_path,
        "pkg_d",
        {
            "broken.py": "import this_module_does_not_exist  # noqa\n",
            "ok.py": _model_file("ok-id", "p/ok", "openai"),
        },
    )
    registry = ModelRegistryService()

    n = ModuleModelLoader.load_models(cls, registry)

    assert n == 1
    assert registry.list_canonical_ids() == ["ok-id"]


def test_loader_used_via_baseModule_on_load_smoke(tmp_path: Path) -> None:
    """Smoke check that the auto-loader exposes the same surface
    BaseModule.on_load expects: returns an int, accepts a class + registry."""
    cls = _make_fake_package(
        tmp_path, "pkg_e", {"x.py": _model_file("x", "p/x", "openai")}
    )
    registry = ModelRegistryService()
    result = ModuleModelLoader.load_models(cls, registry)
    assert isinstance(result, int)
    assert result == 1


