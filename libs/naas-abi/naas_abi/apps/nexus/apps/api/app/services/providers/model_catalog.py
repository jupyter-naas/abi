"""Static catalog scanner for ``naas_abi_marketplace.ai.*`` provider modules.

Walks the marketplace AI directory on disk and parses each ``models/*.py`` with
``ast`` to extract canonical id, model id, provider, display name, description,
image, and context window — **without importing** the model file. Importing
would trigger ``ABIModule.get_instance()`` and fail when the owning module is
not loaded (no API key configured), which is exactly the state we want to be
able to describe.

The output is independent of engine state: every marketplace AI module appears
in the catalog regardless of whether it's enabled in ``config.yaml``. Callers
combine the catalog with ``engine.modules`` to mark which entries are actually
configured at runtime.
"""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from naas_abi_core.models.Model import CanonicalModelId, ModelProvider

_MARKETPLACE_AI_PKG = "naas_abi_marketplace.ai"


@dataclass(frozen=True)
class ModelCatalogEntry:
    """A model discovered statically on disk."""

    canonical_id: str
    model_id: str
    provider: str
    module_path: str  # e.g. "naas_abi_marketplace.ai.anthropic"
    provider_id: str  # e.g. "anthropic" (the directory name under ai/)
    file: str
    name: str | None
    description: str | None
    image: str | None
    context_window: int | None


@dataclass(frozen=True)
class ProviderCatalogEntry:
    """A marketplace AI provider module discovered on disk.

    Display metadata (``name`` .. ``datacenters``) mirrors the ``ABIModule``
    class attributes declared in the provider ``__init__.py``. It is read
    statically so providers surface their branding even when not configured.
    """

    provider_id: str  # directory name under naas_abi_marketplace/ai/
    module_path: str  # full python path
    config_keys: tuple[str, ...]  # required config keys (e.g. "openai_api_key")
    name: str | None = None
    description: str | None = None
    logo_url: str | None = None
    tags: tuple[str, ...] = ()
    slug: str | None = None
    privacy_policy_url: str | None = None
    terms_of_service_url: str | None = None
    status_page_url: str | None = None
    headquarters: str | None = None
    datacenters: tuple[str, ...] | None = None


def _marketplace_ai_root() -> Path | None:
    spec = importlib.util.find_spec(_MARKETPLACE_AI_PKG)
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(next(iter(spec.submodule_search_locations)))


def _resolve_name_ref(node: ast.AST) -> str | None:
    """Resolve ``CanonicalModelId.X`` / ``ModelProvider.X`` / string literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        enum_name = node.value.id
        member = node.attr
        if enum_name == "CanonicalModelId":
            try:
                return str(CanonicalModelId[member])
            except KeyError:
                return None
        if enum_name == "ModelProvider":
            try:
                return str(ModelProvider[member])
            except KeyError:
                return None
    return None


def _resolve_literal(
    node: ast.AST,
    constants: dict[str, ast.AST],
    seen: set[int] | None = None,
) -> str | int | None:
    """Resolve a literal or a reference to a module-level constant."""
    if seen is None:
        seen = set()
    if id(node) in seen:
        return None
    seen.add(id(node))

    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, (str, int)) else None
    if isinstance(node, ast.Attribute):
        return _resolve_name_ref(node)
    if isinstance(node, ast.Name) and node.id in constants:
        return _resolve_literal(constants[node.id], constants, seen)
    return None


def _extract_module_constants(tree: ast.Module) -> dict[str, ast.AST]:
    constants: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
            value = node.value
            if value is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value
    return constants


def _extract_class_attributes(
    cls: ast.ClassDef, module_constants: dict[str, ast.AST]
) -> dict[str, ast.AST]:
    attrs: dict[str, ast.AST] = dict(module_constants)
    for node in cls.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
            value = node.value
            if value is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    attrs[target.id] = value
    return attrs


def _extract_kwarg(call: ast.Call, name: str, attrs: dict[str, ast.AST]) -> str | int | None:
    for kw in call.keywords:
        if kw.arg == name:
            return _resolve_literal(kw.value, attrs)
    return None


def _find_chatmodel_call(node: ast.AST) -> ast.Call | None:
    """Find the outermost ``ChatModel(...)`` call in an expression."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("ChatModel", "EmbeddingModel"):
            return node
    return None


def _entry_from_class(
    cls: ast.ClassDef,
    module_constants: dict[str, ast.AST],
    provider_id: str,
    module_path: str,
    file: str,
) -> ModelCatalogEntry | None:
    """Extract metadata from a ``ModelDefinition`` subclass."""
    is_modeldef = any((isinstance(b, ast.Name) and b.id == "ModelDefinition") for b in cls.bases)
    if not is_modeldef:
        return None

    attrs = _extract_class_attributes(cls, module_constants)

    canonical = attrs.get("CANONICAL_ID")
    model_id_node = attrs.get("MODEL_ID")
    provider_node = attrs.get("PROVIDER")
    if canonical is None or model_id_node is None or provider_node is None:
        return None

    canonical_id = _resolve_literal(canonical, attrs)
    model_id = _resolve_literal(model_id_node, attrs)
    provider = _resolve_literal(provider_node, attrs)
    if (
        not isinstance(canonical_id, str)
        or not isinstance(model_id, str)
        or not isinstance(provider, str)
    ):
        return None

    name: str | None = None
    description: str | None = None
    image: str | None = None
    context_window: int | None = None

    # Look for the ChatModel(...) call assigned to the ``model`` attribute.
    for node in cls.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None:
                continue
            call = _find_chatmodel_call(value)
            if call is None:
                continue
            n = _extract_kwarg(call, "name", attrs)
            d = _extract_kwarg(call, "description", attrs)
            i = _extract_kwarg(call, "image", attrs)
            ctx = _extract_kwarg(call, "context_window", attrs)
            if isinstance(n, str):
                name = n
            if isinstance(d, str):
                description = d
            if isinstance(i, str):
                image = i
            if isinstance(ctx, int):
                context_window = ctx
            break

    return ModelCatalogEntry(
        canonical_id=canonical_id,
        model_id=model_id,
        provider=provider,
        module_path=module_path,
        provider_id=provider_id,
        file=file,
        name=name,
        description=description,
        image=image,
        context_window=context_window,
    )


def _entry_from_module_level(
    tree: ast.Module,
    module_constants: dict[str, ast.AST],
    provider_id: str,
    module_path: str,
    file: str,
) -> ModelCatalogEntry | None:
    """Extract metadata from module-level ``model = ChatModel(...)`` form."""
    model_id_node = module_constants.get("MODEL_ID") or module_constants.get("ID")
    provider_node = module_constants.get("PROVIDER")
    if model_id_node is None or provider_node is None:
        return None

    model_id = _resolve_literal(model_id_node, module_constants)
    provider = _resolve_literal(provider_node, module_constants)
    if not isinstance(model_id, str) or not isinstance(provider, str):
        return None

    name_node = module_constants.get("NAME")
    desc_node = module_constants.get("DESCRIPTION")
    image_node = module_constants.get("IMAGE")
    ctx_node = module_constants.get("CONTEXT_WINDOW")

    name = _resolve_literal(name_node, module_constants) if name_node else None
    description = _resolve_literal(desc_node, module_constants) if desc_node else None
    image = _resolve_literal(image_node, module_constants) if image_node else None
    context_window = _resolve_literal(ctx_node, module_constants) if ctx_node else None

    # Walk for a ChatModel(...) call to pick up inline kwargs not promoted to
    # module constants.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("ChatModel", "EmbeddingModel"):
                n = _extract_kwarg(node, "name", module_constants)
                d = _extract_kwarg(node, "description", module_constants)
                i = _extract_kwarg(node, "image", module_constants)
                ctx = _extract_kwarg(node, "context_window", module_constants)
                if name is None and isinstance(n, str):
                    name = n
                if description is None and isinstance(d, str):
                    description = d
                if image is None and isinstance(i, str):
                    image = i
                if context_window is None and isinstance(ctx, int):
                    context_window = ctx
                break

    return ModelCatalogEntry(
        canonical_id=model_id,
        model_id=model_id,
        provider=provider,
        module_path=module_path,
        provider_id=provider_id,
        file=file,
        name=name if isinstance(name, str) else None,
        description=description if isinstance(description, str) else None,
        image=image if isinstance(image, str) else None,
        context_window=context_window if isinstance(context_window, int) else None,
    )


def _parse_model_file(path: Path, provider_id: str, module_path: str) -> ModelCatalogEntry | None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return None

    module_constants = _extract_module_constants(tree)

    # Prefer the ModelDefinition subclass shape when present.
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            entry = _entry_from_class(node, module_constants, provider_id, module_path, str(path))
            if entry is not None:
                return entry

    return _entry_from_module_level(tree, module_constants, provider_id, module_path, str(path))


def _config_keys_for_provider(provider_dir: Path) -> tuple[str, ...]:
    """Extract required-looking config keys from the provider ``__init__.py``.

    Walks the ``Configuration`` class inside ``ABIModule`` and returns the
    names of fields whose name ends with ``_api_key`` / ``_token`` / ``_auth_header``
    or that have no default value. Used purely for display; configured-ness is
    determined by whether the module is in ``engine.modules`` at runtime.
    """
    init = provider_dir / "__init__.py"
    if not init.exists():
        return ()
    try:
        tree = ast.parse(init.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ()

    keys: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Configuration":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    keys.append(item.target.id)
    return tuple(keys)


# ABIModule class attributes carrying provider display/branding metadata.
_PROVIDER_METADATA_FIELDS = (
    "name",
    "description",
    "logo_url",
    "tags",
    "slug",
    "privacy_policy_url",
    "terms_of_service_url",
    "status_page_url",
    "headquarters",
    "datacenters",
)


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(v for v in value if isinstance(v, str))
    return ()


def _module_metadata_for_provider(provider_dir: Path) -> dict[str, object]:
    """Extract ``ABIModule`` display metadata from the provider ``__init__.py``.

    Reads the literal default assigned to each known metadata attribute on the
    ``ABIModule`` class — without importing the module, which would require the
    owning module to be loaded. Non-literal or unparseable values are skipped.
    """
    init = provider_dir / "__init__.py"
    if not init.exists():
        return {}
    try:
        tree = ast.parse(init.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}

    metadata: dict[str, object] = {}
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == "ABIModule"):
            continue
        for item in node.body:
            if not isinstance(item, (ast.Assign, ast.AnnAssign)):
                continue
            if item.value is None:
                continue
            targets = [item.target] if isinstance(item, ast.AnnAssign) else item.targets
            for target in targets:
                if isinstance(target, ast.Name) and target.id in _PROVIDER_METADATA_FIELDS:
                    try:
                        metadata[target.id] = ast.literal_eval(item.value)
                    except (ValueError, TypeError, SyntaxError):
                        pass
        break
    return metadata


@lru_cache(maxsize=1)
def list_catalog_providers() -> tuple[ProviderCatalogEntry, ...]:
    """List every ``naas_abi_marketplace.ai.<x>`` provider module on disk."""
    root = _marketplace_ai_root()
    if root is None:
        return ()

    providers: list[ProviderCatalogEntry] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_") or entry.name.startswith("."):
            continue
        if not (entry / "__init__.py").exists():
            continue
        module_path = f"{_MARKETPLACE_AI_PKG}.{entry.name}"
        config_keys = _config_keys_for_provider(entry)
        meta = _module_metadata_for_provider(entry)
        datacenters = meta.get("datacenters")
        providers.append(
            ProviderCatalogEntry(
                provider_id=entry.name,
                module_path=module_path,
                config_keys=config_keys,
                name=_str_or_none(meta.get("name")),
                description=_str_or_none(meta.get("description")),
                logo_url=_str_or_none(meta.get("logo_url")),
                tags=_str_tuple(meta.get("tags")),
                slug=_str_or_none(meta.get("slug")),
                privacy_policy_url=_str_or_none(meta.get("privacy_policy_url")),
                terms_of_service_url=_str_or_none(meta.get("terms_of_service_url")),
                status_page_url=_str_or_none(meta.get("status_page_url")),
                headquarters=_str_or_none(meta.get("headquarters")),
                datacenters=(_str_tuple(datacenters) if datacenters is not None else None),
            )
        )
    return tuple(providers)


@lru_cache(maxsize=1)
def list_catalog_models() -> tuple[ModelCatalogEntry, ...]:
    """Parse every ``models/*.py`` file under every marketplace AI provider."""
    out: list[ModelCatalogEntry] = []
    for provider in list_catalog_providers():
        provider_dir = Path(_marketplace_ai_root() or "") / provider.provider_id
        models_dir = provider_dir / "models"
        if not models_dir.is_dir():
            continue
        for file in sorted(models_dir.rglob("*.py")):
            if file.name == "__init__.py" or file.name.endswith("_test.py"):
                continue
            entry = _parse_model_file(file, provider.provider_id, provider.module_path)
            if entry is not None:
                out.append(entry)
    return tuple(out)


def list_models_for_catalog_provider(provider_id: str) -> tuple[ModelCatalogEntry, ...]:
    return tuple(m for m in list_catalog_models() if m.provider_id == provider_id)


def find_catalog_model(canonical_or_model_id: str) -> ModelCatalogEntry | None:
    for entry in list_catalog_models():
        if entry.canonical_id == canonical_or_model_id or entry.model_id == canonical_or_model_id:
            return entry
    return None


def _model_module_path(entry: ModelCatalogEntry) -> str | None:
    """Reconstruct the importable module path of a model file.

    e.g. ``naas_abi_marketplace.ai.anthropic.models.claude_sonnet_3_7`` for the
    file ``.../naas_abi_marketplace/ai/anthropic/models/claude_sonnet_3_7.py``.
    Used to match the ``from <...>.models.<x> import model`` import an agent uses
    back to its catalog entry.
    """
    root = _marketplace_ai_root()
    if root is None:
        return None
    try:
        rel = Path(entry.file).resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    parts = rel.with_suffix("").parts
    if not parts:
        return None
    return ".".join((_MARKETPLACE_AI_PKG, *parts))


def find_catalog_model_by_module_path(module_path: str) -> ModelCatalogEntry | None:
    """Find the catalog entry whose model file is importable as ``module_path``."""
    for entry in list_catalog_models():
        if _model_module_path(entry) == module_path:
            return entry
    return None


def resolve_provider_logo_file(provider_id: str, logo_url: str | None) -> Path | None:
    """Resolve a provider's local ``logo_url`` to an on-disk file.

    Returns None for absent values and ``http(s)`` URLs (which are served by the
    remote host directly). Local values are matched against the path shapes used
    across marketplace AI modules — relative to the provider directory, the
    ``ai`` root, or the package parent (e.g.
    ``naas_abi_marketplace/ai/<provider>/assets/...``). Resolution is
    config-independent: it does not require the owning module to be loaded.

    The resolved file is constrained to live under the marketplace tree to
    prevent path traversal via a crafted ``logo_url``.
    """
    if not logo_url or logo_url.startswith(("http://", "https://")):
        return None
    root = _marketplace_ai_root()
    if root is None:
        return None

    provider_dir = root / provider_id
    pkg_parent = root.parent.parent  # dir containing the naas_abi_marketplace pkg
    rel = logo_url.lstrip("/")
    candidates = (
        provider_dir / rel,
        root / rel,
        pkg_parent / rel,
        provider_dir / "assets" / "public" / Path(rel).name,
    )

    boundary = pkg_parent.resolve()
    for cand in candidates:
        try:
            resolved = cand.resolve()
        except OSError:
            continue
        if not resolved.is_file():
            continue
        try:
            resolved.relative_to(boundary)
        except ValueError:
            continue
        return resolved
    return None


def resolve_provider_logo_for_id(provider_id: str) -> Path | None:
    """Resolve the logo file for a catalog provider by its id."""
    for provider in list_catalog_providers():
        if provider.provider_id == provider_id:
            return resolve_provider_logo_file(provider_id, provider.logo_url)
    return None
