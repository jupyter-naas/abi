"""Pipeline/spec → SPARQL compiler (AUDIT §7b.3).

Pure function: ``compile_list(spec, ctx) -> CompiledQuery``. Lowers a ``ListSpec`` into a
single portable SPARQL 1.1 query (Jena + Oxigraph) plus the cached COUNT query. No I/O.

Hard rules carried from §7a / §7b.3:
  * One row per ``?root``.
  * **Requiredness by usage, not a blanket OPTIONAL.** A to-one column referenced by a
    *positive, conjunctive* value filter is emitted as a **required** join (so the filter
    prunes ``?root``); a projection-only or negatively-filtered column is ``OPTIONAL``.
  * A to-many / inline-source filter is **existential** (``FILTER EXISTS``); ``not`` →
    ``FILTER NOT EXISTS``; ``or`` of branches → ``FILTER(EXISTS{} || EXISTS{})``.

List mode supports dimension columns (property/node) and **measure** columns (aggregate →
per-``?root`` ``GROUP BY`` subqueries joined on ``?root``). Aggregate/pivot mode groups the
fact by dimension tuples. To-many ``collapse``, the keyset cursor, and the jena-text search
seam land in later steps.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.query__schema import (
    AggregateSource,
    AggregateSpec,
    ClassAnchor,
    Column,
    ColumnMeta,
    CompileContext,
    CompiledQuery,
    Dimension,
    FilterColumnTarget,
    FilterCondition,
    FilterGroup,
    FilterNode,
    FilterNot,
    FilterSourceTarget,
    Hop,
    InstancesAnchor,
    ListSpec,
    Measure,
    NodeSource,
    PropertySource,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import (
    sparql_iri,
    sparql_string_literal,
    sparql_typed_literal,
)

# Operators whose truth requires the value to exist — a conjunctive use of one of these
# on a single-valued column lets us emit a pruning required join.
_POSITIVE_OPS = frozenset(
    {"eq", "contains", "startsWith", "endsWith", "lt", "lte", "gt", "gte", "between", "in", "is"}
)


# ── Literals ──────────────────────────────────────────────────────────────────


def _lit(value: object, datatype: str) -> str:
    if datatype == "string":
        return sparql_string_literal(str(value))
    if datatype == "iri":
        return sparql_iri(str(value))
    return sparql_typed_literal(value, datatype)


def _infer_datatype(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _path_term(hop: Hop) -> str:
    """The predicate term for a hop, applying a transitive quantifier if present."""
    iri = sparql_iri(hop.predicate)
    if hop.quantifier == "plus":
        return f"{iri}+"
    if hop.quantifier == "star":
        return f"{iri}*"
    return iri


def _lower_path(path: tuple[Hop, ...], start_var: str, prefix: str) -> tuple[list[str], str]:
    """Walk ``path`` from ``start_var`` into triple patterns; return (triples, end_var).

    An empty path returns ``([], start_var)`` — the node itself.
    """
    cur = start_var
    triples: list[str] = []
    for i, hop in enumerate(path):
        nxt = f"?{prefix}_{i}"
        term = _path_term(hop)
        if hop.direction == "in":
            triples.append(f"{nxt} {term} {cur} .")
        else:
            triples.append(f"{cur} {term} {nxt} .")
        if hop.target_class_uris:
            tvar = f"?{prefix}_{i}_t"
            values = " ".join(sparql_iri(u) for u in hop.target_class_uris)
            triples.append(f"{nxt} a {tvar} . VALUES {tvar} {{ {values} }}")
        cur = nxt
    return triples, cur


# ── Cardinality ───────────────────────────────────────────────────────────────


def _is_single_valued(source: object, ctx: CompileContext) -> bool:
    """True iff every step of the source's path (and its predicate) is known functional.

    Unknown ⇒ False (treat as to-many: safe — never emits a row-multiplying required join).
    """
    if isinstance(source, AggregateSource):
        return False
    path = getattr(source, "path", ())
    if any(h.predicate not in ctx.single_valued_predicates for h in path):
        return False
    if isinstance(source, PropertySource):
        return source.predicate in ctx.single_valued_predicates
    if isinstance(source, NodeSource):
        return True  # all hops single-valued and the node itself is one entity
    return False


# ── Column binding ────────────────────────────────────────────────────────────


def _bind_column(col: Column, var: str, ctx: CompileContext) -> str:
    """The triple pattern(s) that bind ``var`` to the column's value (no OPTIONAL wrapper)."""
    src = col.source
    if isinstance(src, PropertySource):
        triples, end = _lower_path(src.path, "?root", col.id)
        triples.append(f"{end} {sparql_iri(src.predicate)} {var} .")
        return " ".join(triples)
    if isinstance(src, NodeSource):
        triples, end = _lower_path(src.path, "?root", col.id)
        if src.show == "uri":
            triples.append(f"BIND({end} AS {var})")
        else:
            triples.append(
                f"OPTIONAL {{ {end} <http://www.w3.org/2000/01/rdf-schema#label> ?{col.id}_lbl . }} "
                f"BIND(COALESCE(?{col.id}_lbl, STR({end})) AS {var})"
            )
        return " ".join(triples)
    raise GraphQuerySpecError(f"aggregate/measure columns not yet supported: {col.id!r}")


def _column_role(col: Column) -> str:
    if isinstance(col.source, NodeSource):
        return "node"
    if isinstance(col.source, AggregateSource):
        return "measure"
    return "dimension"


# ── Value expressions (filter on a bound var) ─────────────────────────────────


def _value_expr(var: str, datatype: str, operator: str, value: object) -> str:
    if operator in ("contains", "startsWith", "endsWith", "notContains"):
        term = sparql_string_literal(str(value).lower())
        body = f"LCASE(STR({var}))"
        if operator == "contains":
            return f"CONTAINS({body}, {term})"
        if operator == "notContains":
            return f"!CONTAINS({body}, {term})"
        if operator == "startsWith":
            return f"STRSTARTS({body}, {term})"
        return f"STRENDS({body}, {term})"
    if operator == "isEmpty":
        return f"!BOUND({var})"
    if operator == "isNotEmpty":
        return f"BOUND({var})"
    if operator in ("in", "notIn"):
        items = ", ".join(_lit(v, datatype) for v in (value or ()))
        keyword = "IN" if operator == "in" else "NOT IN"
        return f"{var} {keyword} ({items})"
    if operator == "between":
        lo, hi = value  # type: ignore[misc]
        return f"({var} >= {_lit(lo, datatype)} && {var} <= {_lit(hi, datatype)})"
    sym = {
        "eq": "=", "neq": "!=", "is": "=", "isNot": "!=",
        "lt": "<", "lte": "<=", "gt": ">", "gte": ">=",
    }.get(operator)
    if sym is None:
        raise GraphQuerySpecError(f"unsupported operator: {operator!r}")
    lit_datatype = "iri" if operator in ("is", "isNot") else datatype
    return f"{var} {sym} {_lit(value, lit_datatype)}"


def _branch_block(source: object, operator: str, value: object, prefix: str, root_var: str = "?root") -> str:
    """An EXISTS body: lower the source path from ``root_var`` and constrain the reached node."""
    path = getattr(source, "path", ())
    triples, end = _lower_path(path, root_var, prefix)
    if operator == "hasRelation":
        # Existence of the path is the whole constraint.
        return " ".join(triples)
    if isinstance(source, NodeSource):
        # Constrain the reached node by its display value (label, else STR(uri)) so it matches
        # the facet values the UI offers. Covers in / notIn / is / isNot on related entities.
        dv = f"?{prefix}_dv"
        triples.append(
            f"OPTIONAL {{ {end} <http://www.w3.org/2000/01/rdf-schema#label> ?{prefix}_lbl . }} "
            f"BIND(COALESCE(?{prefix}_lbl, STR({end})) AS {dv})"
        )
        op = {"is": "eq", "isNot": "neq"}.get(operator, operator)
        triples.append(f"FILTER({_value_expr(dv, 'string', op, value)})")
        return " ".join(triples)
    if isinstance(source, PropertySource):
        pred = sparql_iri(source.predicate)
        if operator == "eq":
            triples.append(f"{end} {pred} {_lit(value, _infer_datatype(value))} .")
        else:
            vbind = f"?{prefix}_v"
            triples.append(f"{end} {pred} {vbind} .")
            triples.append(f"FILTER({_value_expr(vbind, _infer_datatype(value), operator, value)})")
        return " ".join(triples)
    raise GraphQuerySpecError("unsupported branch source")


# ── Aggregates / measures ─────────────────────────────────────────────────────

# Measures that mean "0 over an empty group"; min/max/avg are NULL over an empty group.
_ZERO_FILL_FNS = frozenset({"count", "countDistinct", "sum"})


def _agg_expr(fn: str, target: str, of_kind: str | None) -> str:
    if fn == "count":
        return f"COUNT({target})" if of_kind == "property" else f"COUNT(DISTINCT {target})"
    if fn == "countDistinct":
        return f"COUNT(DISTINCT {target})"
    fns = {"sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX"}
    if fn in fns:
        return f"{fns[fn]}({target})"
    raise GraphQuerySpecError(f"unsupported aggregate fn: {fn!r}")


def _agg_subquery(col_id: str, start_var: str, triples: list[str], agg: str, zero_fill: bool) -> list[str]:
    """A correlated ``OPTIONAL { SELECT start_var (agg AS …) … GROUP BY start_var }``.

    The sub-SELECT inherits the outer query's FROM dataset (the union of the spec's graphs),
    so its patterns need no ``GRAPH`` wrapper.

    ``zero_fill`` wraps the result in ``COALESCE(…, 0)`` (count/sum) so a row with no reached
    nodes still shows 0; otherwise (min/max/avg/concat) a vacuous group yields NULL.
    """
    inner = " ".join(triples)
    if zero_fill:
        raw = f"?raw_{col_id}"
        subq = f"OPTIONAL {{ SELECT {start_var} ({agg} AS {raw}) WHERE {{ {inner} }} GROUP BY {start_var} }}"
        return [subq, f"BIND(COALESCE({raw}, 0) AS ?col_{col_id})"]
    subq = f"OPTIONAL {{ SELECT {start_var} ({agg} AS ?col_{col_id}) WHERE {{ {inner} }} GROUP BY {start_var} }}"
    return [subq]


def _measure_fragment(col: Column, start_var: str = "?root") -> list[str]:
    """A list-mode measure: a per-``start_var`` GROUP BY subquery joined back on it.

    A measure FILTER (HAVING) on the coalesced ``?col_<id>`` holds for *every* operator
    (``> 0``, ``= 0``, ``between``…); the count query reuses the same subquery + outer FILTER,
    so page rows and total never diverge.
    """
    src = col.source
    assert isinstance(src, AggregateSource)
    triples, end = _lower_path(src.path, start_var, col.id)
    if src.of_kind == "property":
        vbind = f"?{col.id}_v"
        triples.append(f"{end} {sparql_iri(src.of_predicate or '')} {vbind} .")
        target = vbind
    else:
        if src.fn in ("sum", "avg", "min", "max"):
            raise GraphQuerySpecError(f"measure {col.id!r}: {src.fn} needs a property target")
        target = end
    agg = _agg_expr(src.fn, target, src.of_kind)
    return _agg_subquery(col.id, start_var, triples, agg, src.fn in _ZERO_FILL_FNS)


# How a to-many dimension collapses to one cell (keeps one row per root). `first` → MIN
# (deterministic + portable, not the non-deterministic SAMPLE); `concat` is order-unstable
# across engines (review portability §6) — never feed it into a snapshot hash.
def _collapse_agg(collapse: str, target: str) -> str:
    if collapse == "concat":
        return f"GROUP_CONCAT(DISTINCT STR({target}); SEPARATOR=\", \")"
    if collapse == "count":
        return f"COUNT(DISTINCT {target})"
    if collapse in ("min", "first"):
        return f"MIN({target})"
    if collapse == "max":
        return f"MAX({target})"
    raise GraphQuerySpecError(f"unknown collapse: {collapse!r}")


def _collapse_fragment(
    col: Column, start_var: str = "?root", collapse_override: str | None = None
) -> list[str]:
    """A property/node column over a to-many path, collapsed to one cell per row."""
    src = col.source
    collapse = collapse_override or getattr(src, "collapse", None)
    assert collapse is not None
    triples, end = _lower_path(getattr(src, "path", ()), start_var, col.id)
    if isinstance(src, PropertySource):
        vbind = f"?{col.id}_v"
        triples.append(f"{end} {sparql_iri(src.predicate)} {vbind} .")
        target = vbind
    elif isinstance(src, NodeSource):
        if src.show == "uri":
            target = end
        else:
            lbl = f"?{col.id}_lbl"
            triples.append(
                f"OPTIONAL {{ {end} <http://www.w3.org/2000/01/rdf-schema#label> {lbl} . }} "
                f"BIND(COALESCE({lbl}, STR({end})) AS ?{col.id}_v)"
            )
            target = f"?{col.id}_v"
    else:  # pragma: no cover - guarded earlier
        raise GraphQuerySpecError(f"cannot collapse column {col.id!r}")
    agg = _collapse_agg(collapse, target)
    return _agg_subquery(col.id, start_var, triples, agg, collapse == "count")


def _is_aggregated(source: object) -> bool:
    """True for columns bound via a GROUP BY subquery: measures and collapsed to-many columns."""
    return isinstance(source, AggregateSource) or getattr(source, "collapse", None) is not None


# ── Filter tree lowering ──────────────────────────────────────────────────────


class _FilterEmitter:
    """Lowers the boolean tree to WHERE lines, tracking branch ids + referenced columns."""

    def __init__(self, columns_by_id: dict[str, Column], var_for_column: dict[str, str], ctx: CompileContext):
        self._cols = columns_by_id
        self._vars = var_for_column
        self._ctx = ctx
        self._branch = 0
        self.referenced_columns: set[str] = set()

    def _next_prefix(self) -> str:
        prefix = f"b{self._branch}"
        self._branch += 1
        return prefix

    def _leaf(self, cond: FilterCondition) -> tuple[str, str]:
        """Return ('expr', sparql) for a value test, or ('exists', block) for a branch."""
        target = cond.target
        if isinstance(target, FilterColumnTarget):
            col = self._cols[target.column_id]
            self.referenced_columns.add(col.id)
            # A measure / collapsed column is filtered as a HAVING-equivalent on ?col_<id>.
            if _is_aggregated(col.source):
                return "expr", _value_expr(self._vars[col.id], col.datatype, cond.operator, cond.value)
            # Presence checks read the projected display var directly.
            if cond.operator in ("isEmpty", "isNotEmpty"):
                return "expr", _value_expr(self._vars[col.id], col.datatype, cond.operator, cond.value)
            # Related-entity (node) columns must constrain the REACHED node, not the projected
            # label var — otherwise the value never binds and the filter matches every row.
            if isinstance(col.source, NodeSource):
                return "exists", _branch_block(col.source, cond.operator, cond.value, self._next_prefix())
            if _is_single_valued(col.source, self._ctx):
                return "expr", _value_expr(self._vars[col.id], col.datatype, cond.operator, cond.value)
            # to-many property column → existential over its own path
            return "exists", _branch_block(col.source, cond.operator, cond.value, self._next_prefix())
        if isinstance(target, FilterSourceTarget):
            return "exists", _branch_block(target.source, cond.operator, cond.value, self._next_prefix())
        raise GraphQuerySpecError("unknown filter target")

    def as_expr(self, node: FilterNode) -> str:
        """A SPARQL boolean expression usable inside FILTER(...) (for or/nested contexts)."""
        if isinstance(node, FilterCondition):
            kind, body = self._leaf(node)
            return body if kind == "expr" else f"EXISTS {{ {body} }}"
        if isinstance(node, FilterGroup):
            joiner = " && " if node.op == "and" else " || "
            return "(" + joiner.join(self.as_expr(c) for c in node.children) + ")"
        if isinstance(node, FilterNot):
            child = node.child
            if isinstance(child, FilterCondition):
                kind, body = self._leaf(child)
                return f"NOT EXISTS {{ {body} }}" if kind == "exists" else f"!({body})"
            return f"!({self.as_expr(child)})"
        raise GraphQuerySpecError("unknown filter node")

    def emit_top(self, node: FilterNode) -> list[str]:
        """Top-level WHERE lines (prefers FILTER (NOT) EXISTS over !EXISTS for clarity)."""
        if isinstance(node, FilterCondition):
            kind, body = self._leaf(node)
            return [f"FILTER({body})"] if kind == "expr" else [f"FILTER EXISTS {{ {body} }}"]
        if isinstance(node, FilterGroup):
            if node.op == "and":
                lines: list[str] = []
                for child in node.children:
                    lines.extend(self.emit_top(child))
                return lines
            return [f"FILTER({self.as_expr(node)})"]
        if isinstance(node, FilterNot):
            child = node.child
            if isinstance(child, FilterCondition):
                kind, body = self._leaf(child)
                if kind == "exists":
                    return [f"FILTER NOT EXISTS {{ {body} }}"]
                return [f"FILTER(!({body}))"]
            return [f"FILTER(!({self.as_expr(child)}))"]
        raise GraphQuerySpecError("unknown filter node")


# ── Anchor ────────────────────────────────────────────────────────────────────


def _anchor_lines(root: object, row_var: str = "?root", cls_var: str = "?cls") -> list[str]:
    if isinstance(root, InstancesAnchor):
        values = " ".join(sparql_iri(u) for u in root.instance_uris)
        return [f"VALUES {row_var} {{ {values} }}"]
    assert isinstance(root, ClassAnchor)
    values = " ".join(sparql_iri(u) for u in root.class_uris)
    return [f"VALUES {cls_var} {{ {values} }}", f"{row_var} a {cls_var} ."]


# ── Validation / classification ───────────────────────────────────────────────


def _validate(spec: ListSpec, columns_by_id: dict[str, Column], ctx: CompileContext) -> None:
    if len(spec.columns) > ctx.max_columns:
        raise GraphQuerySpecError(f"too many columns ({len(spec.columns)} > {ctx.max_columns})")
    for col in spec.columns:
        for hop in getattr(col.source, "path", ()):
            if len(getattr(col.source, "path", ())) > ctx.max_hops:
                raise GraphQuerySpecError(f"path too long on column {col.id!r}")
            _ = hop
    for sk in spec.sort:
        if sk.column_id not in columns_by_id:
            raise GraphQuerySpecError(f"sort references unknown column {sk.column_id!r}")
    _validate_filter_refs(spec.filters, columns_by_id)


def _validate_filter_refs(node: FilterNode | None, columns_by_id: dict[str, Column]) -> None:
    if node is None:
        return
    if isinstance(node, FilterCondition):
        if isinstance(node.target, FilterColumnTarget) and node.target.column_id not in columns_by_id:
            raise GraphQuerySpecError(f"filter references unknown column {node.target.column_id!r}")
    elif isinstance(node, FilterGroup):
        for c in node.children:
            _validate_filter_refs(c, columns_by_id)
    elif isinstance(node, FilterNot):
        _validate_filter_refs(node.child, columns_by_id)


def _conjunctive_positive_columns(
    node: FilterNode | None, columns_by_id: dict[str, Column], ctx: CompileContext, conjunctive: bool = True
) -> set[str]:
    """Columns whose value is required for a row to match (positive op, single-valued,
    in a purely-conjunctive non-negated context) → eligible for a pruning required join."""
    out: set[str] = set()
    if node is None:
        return out
    if isinstance(node, FilterCondition):
        if (
            conjunctive
            and isinstance(node.target, FilterColumnTarget)
            and node.operator in _POSITIVE_OPS
        ):
            col = columns_by_id[node.target.column_id]
            if not _is_aggregated(col.source) and _is_single_valued(col.source, ctx):
                out.add(col.id)
    elif isinstance(node, FilterGroup):
        child_conj = conjunctive and node.op == "and"
        for c in node.children:
            out |= _conjunctive_positive_columns(c, columns_by_id, ctx, child_conj)
    elif isinstance(node, FilterNot):
        out |= _conjunctive_positive_columns(node.child, columns_by_id, ctx, False)
    return out


# ── Assembly ──────────────────────────────────────────────────────────────────


def _from_clause(spec: object) -> str:
    """SPARQL dataset clause: one ``FROM <g>`` per spec graph. The query's default graph becomes
    the RDF-merge (union) of those graphs, so plain patterns join ACROSS named graphs while the
    scope stays exactly the workspace graphs the spec selected. Sub-SELECTs inherit this dataset.
    """
    return "".join(f"FROM {sparql_iri(g)}\n" for g in spec.graph_uris)


# Datatypes with a total order usable for a stable keyset comparison.
_ORDERED_DATATYPES = frozenset({"string", "number", "date", "iri", "boolean"})


def _keyset_eligible(spec: ListSpec, columns_by_id: dict[str, Column], ctx: CompileContext) -> bool:
    """Keyset needs every sort key to be a non-null, single-valued, totally-ordered column.

    A measure / collapsed / nullable / unknown-cardinality sort key falls back to OFFSET
    (AUDIT §7b.3). No sort key ⇒ keyset on ``?root`` alone, always eligible.
    """
    for sk in spec.sort:
        col = columns_by_id[sk.column_id]
        if _is_aggregated(col.source):
            return False
        if col.datatype not in _ORDERED_DATATYPES:
            return False
        if not _is_single_valued(col.source, ctx):
            return False
    return True


def _and(terms: list[str]) -> str:
    return terms[0] if len(terms) == 1 else "(" + " && ".join(terms) + ")"


def _keyset_after_filter(spec: ListSpec, var_for_column: dict[str, str], columns_by_id: dict[str, Column], after: tuple) -> str:
    """The lexicographic "strictly after the cursor" filter for ORDER BY <keys>, ?root."""
    *vals, root = after
    clauses: list[str] = []
    eqs: list[str] = []
    for i, sk in enumerate(spec.sort):
        var = var_for_column[sk.column_id]
        lit = _lit(vals[i], columns_by_id[sk.column_id].datatype)
        cmp = "<" if sk.direction == "desc" else ">"
        clauses.append(_and(eqs + [f"{var} {cmp} {lit}"]))
        eqs = eqs + [f"{var} = {lit}"]
    clauses.append(_and(eqs + [f"STR(?root) > {sparql_string_literal(str(root))}"]))
    return f"FILTER( {' || '.join(clauses)} )"


def compile_list(spec: ListSpec, ctx: CompileContext, page: object | None = None) -> CompiledQuery:
    columns_by_id = {c.id: c for c in spec.columns}
    _validate(spec, columns_by_id, ctx)

    required_ids = _conjunctive_positive_columns(spec.filters, columns_by_id, ctx)
    keyset_ok = _keyset_eligible(spec, columns_by_id, ctx)
    # Keyset sort keys must be NON-null at query time → emit them as required joins.
    keyset_sort_ids = {sk.column_id for sk in spec.sort} if keyset_ok else set()
    forced_required = required_ids | keyset_sort_ids
    from_clause = _from_clause(spec)
    limit = page.limit if page is not None else ctx.page_limit

    var_for_column: dict[str, str] = {}
    metas: list[ColumnMeta] = []
    col_lines: dict[str, list[str]] = {}  # the WHERE line(s) that bind each column
    required_prop: list[str] = []  # required property/node joins (filter-pruning)
    optional_prop: list[str] = []  # OPTIONAL projections
    measure_lines: list[str] = []  # measure subqueries (+ COALESCE BIND)
    select_vars = ["?root"]

    for col in spec.columns:
        var = f"?col_{col.id}"
        var_for_column[col.id] = var
        metas.append(ColumnMeta(id=col.id, label=col.label or col.id, datatype=col.datatype, role=_column_role(col)))
        if col.visible:
            select_vars.append(var)
        explicit_collapse = getattr(col.source, "collapse", None)
        # A to-many (or unknown-cardinality) dimension MUST collapse to one cell, or it would
        # multiply rows and break the one-row-per-root rule. Default to `concat` when the spec
        # didn't pick a collapse and the path isn't provably single-valued.
        needs_default_collapse = (
            not isinstance(col.source, AggregateSource)
            and explicit_collapse is None
            and not _is_single_valued(col.source, ctx)
            and len(getattr(col.source, "path", ())) > 0
        )
        if isinstance(col.source, AggregateSource):
            lines = _measure_fragment(col, "?root")
            col_lines[col.id] = lines
            measure_lines.extend(lines)
        elif explicit_collapse is not None:
            lines = _collapse_fragment(col, "?root")
            col_lines[col.id] = lines
            measure_lines.extend(lines)
        elif needs_default_collapse:
            lines = _collapse_fragment(col, "?root", collapse_override="concat")
            col_lines[col.id] = lines
            measure_lines.extend(lines)
        else:
            body = _bind_column(col, var, ctx)
            if col.id in forced_required:
                col_lines[col.id] = [body]
                required_prop.append(body)
            else:
                opt = f"OPTIONAL {{ {body} }}"
                col_lines[col.id] = [opt]
                optional_prop.append(opt)

    emitter = _FilterEmitter(columns_by_id, var_for_column, ctx)
    filter_lines = emitter.emit_top(spec.filters) if spec.filters is not None else []

    order_terms = [
        f"{'DESC' if sk.direction == 'desc' else 'ASC'}({var_for_column[sk.column_id]})"
        for sk in spec.sort
    ] + ["?root"]

    anchor = _anchor_lines(spec.root)

    # Pagination: keyset "after cursor" filter when eligible + a cursor is supplied;
    # otherwise OFFSET. A first page (no cursor / offset 0) emits neither — so the SQL is
    # identical regardless of mode.
    after_lines: list[str] = []
    tail = f"LIMIT {limit}"
    if page is not None and getattr(page, "after", None) is not None and keyset_ok:
        after_lines = [_keyset_after_filter(spec, var_for_column, columns_by_id, page.after)]
    elif not keyset_ok and page is not None and getattr(page, "offset", 0):
        tail = f"LIMIT {limit} OFFSET {int(page.offset)}"

    page_inner = "\n    ".join(anchor + required_prop + optional_prop + measure_lines + filter_lines + after_lines)
    page_sparql = (
        f"SELECT {' '.join(select_vars)}\n"
        f"{from_clause}"
        f"WHERE {{\n    {page_inner}\n}}\n"
        f"ORDER BY {' '.join(order_terms)} {tail}"
    )

    # Count query: keep only bindings any filter references; drop projection-only ones.
    count_binding_lines: list[str] = []
    for col in spec.columns:
        if col.id in emitter.referenced_columns:
            count_binding_lines.extend(col_lines[col.id])
    count_inner = "\n    ".join(anchor + count_binding_lines + filter_lines)
    count_sparql = (
        f"SELECT (COUNT(DISTINCT ?root) AS ?total)\n"
        f"{from_clause}"
        f"WHERE {{\n    {count_inner}\n}}"
    )

    return CompiledQuery(
        sparql=page_sparql,
        count_sparql=count_sparql,
        columns=tuple(metas),
        var_for_column=var_for_column,
        uses_offset_fallback=not keyset_ok,
        order_columns=tuple(sk.column_id for sk in spec.sort),
    )


# ── Aggregate / pivot mode ────────────────────────────────────────────────────


def _dimension_fragment(dim: Dimension) -> str:
    """One group-by dimension: lower its path from ``?fact`` and bind ``?dim_<id>``.

    The whole hop is ``OPTIONAL`` so a fact lacking the relation still contributes a row
    under a NULL group (and ``COUNT(DISTINCT ?fact)`` stays complete) — the §7b.3 / review
    B3 correction to the original §7a-B sketch.
    """
    triples, end = _lower_path(dim.path, "?fact", dim.id)
    dvar = f"?dim_{dim.id}"
    if dim.show_kind == "property":
        triples.append(f"{end} {sparql_iri(dim.show_predicate or '')} {dvar} .")
    elif dim.show_kind == "node-label":
        triples.append(f"{end} <http://www.w3.org/2000/01/rdf-schema#label> {dvar} .")
    elif dim.show_kind == "node-uri":
        triples.append(f"BIND(STR({end}) AS {dvar})")
    else:
        raise GraphQuerySpecError(f"unknown dimension show: {dim.show_kind!r}")
    return f"OPTIONAL {{ {' '.join(triples)} }}"


def _aggregate_measure(measure: Measure) -> tuple[str, list[str]]:
    """The SELECT aggregate expr for a measure over the fact set, + any WHERE triples it needs."""
    if not measure.path and measure.of_kind in (None, "node"):
        if measure.fn in ("count", "countDistinct"):
            return "COUNT(DISTINCT ?fact)", []
        raise GraphQuerySpecError(f"measure {measure.id!r}: {measure.fn} needs a property/path target")
    triples, end = _lower_path(measure.path, "?fact", measure.id)
    if measure.of_kind == "property":
        vbind = f"?m_{measure.id}_v"
        triples.append(f"{end} {sparql_iri(measure.of_predicate or '')} {vbind} .")
        target = vbind
    else:
        if measure.fn in ("sum", "avg", "min", "max"):
            raise GraphQuerySpecError(f"measure {measure.id!r}: {measure.fn} needs a property target")
        target = end
    agg = _agg_expr(measure.fn, target, measure.of_kind)
    return agg, [f"OPTIONAL {{ {' '.join(triples)} }}"]


def _flatten_and(node: FilterNode) -> list[FilterCondition] | None:
    """A flat list of leaf conditions iff ``node`` is a (nested) pure AND of conditions."""
    if isinstance(node, FilterCondition):
        return [node]
    if isinstance(node, FilterGroup) and node.op == "and":
        out: list[FilterCondition] = []
        for child in node.children:
            sub = _flatten_and(child)
            if sub is None:
                return None
            out.extend(sub)
        return out
    return None


def compile_aggregate(spec: AggregateSpec, ctx: CompileContext, page: object | None = None) -> CompiledQuery:
    if not spec.group_by:
        raise GraphQuerySpecError("aggregate mode requires at least one group-by dimension")
    if not spec.measures:
        raise GraphQuerySpecError("aggregate mode requires at least one measure")
    if len(spec.group_by) + len(spec.measures) > ctx.max_columns:
        raise GraphQuerySpecError("too many columns")

    from_clause = _from_clause(spec)
    var_for_column: dict[str, str] = {}
    metas: list[ColumnMeta] = []
    where_lines = _anchor_lines(spec.fact, "?fact")
    select_parts: list[str] = []
    group_keys: list[str] = []
    dim_ids: set[str] = set()
    measure_agg: dict[str, str] = {}

    for dim in spec.group_by:
        dvar = f"?dim_{dim.id}"
        var_for_column[dim.id] = dvar
        dim_ids.add(dim.id)
        group_keys.append(dvar)
        select_parts.append(dvar)
        metas.append(ColumnMeta(id=dim.id, label=dim.label or dim.id, datatype="string", role="dimension"))
        where_lines.append(_dimension_fragment(dim))

    for measure in spec.measures:
        mvar = f"?m_{measure.id}"
        var_for_column[measure.id] = mvar
        agg, extra = _aggregate_measure(measure)
        measure_agg[measure.id] = agg
        select_parts.append(f"({agg} AS {mvar})")
        metas.append(ColumnMeta(id=measure.id, label=measure.label or measure.id, datatype="number", role="measure"))
        where_lines.extend(extra)

    # Filters (v1): a conjunction of conditions. Dimension/fact conditions → WHERE; measure
    # conditions → HAVING. Anything more complex (OR/NOT mixing the two) is rejected for now.
    having_exprs: list[str] = []
    if spec.filters is not None:
        conds = _flatten_and(spec.filters)
        if conds is None:
            raise GraphQuerySpecError("aggregate filters support only a conjunction (AND) of conditions in v1")
        branch_n = 0
        for cond in conds:
            target = cond.target
            if isinstance(target, FilterSourceTarget):
                where_lines.append(f"FILTER EXISTS {{ {_branch_block(target.source, cond.operator, cond.value, f'b{branch_n}', '?fact')} }}")
                branch_n += 1
            elif isinstance(target, FilterColumnTarget) and target.column_id in dim_ids:
                where_lines.append(f"FILTER({_value_expr(var_for_column[target.column_id], 'string', cond.operator, cond.value)})")
            elif isinstance(target, FilterColumnTarget) and target.column_id in measure_agg:
                having_exprs.append(_value_expr(measure_agg[target.column_id], "number", cond.operator, cond.value))
            else:
                raise GraphQuerySpecError(f"aggregate filter references unknown column {getattr(target, 'column_id', '?')!r}")

    sorted_vars = [var_for_column[sk.column_id] for sk in spec.sort if sk.column_id in var_for_column]
    order_terms = [
        f"{'DESC' if sk.direction == 'desc' else 'ASC'}({var_for_column[sk.column_id]})"
        for sk in spec.sort
        if sk.column_id in var_for_column
    ] + [gk for gk in group_keys if gk not in sorted_vars]

    having_clause = f" HAVING({' && '.join(having_exprs)})" if having_exprs else ""
    limit = page.limit if page is not None else ctx.page_limit
    tail = f"LIMIT {limit}"
    if page is not None and getattr(page, "offset", 0):
        tail = f"LIMIT {limit} OFFSET {int(page.offset)}"

    inner = "\n    ".join(where_lines)
    page_sparql = (
        f"SELECT {' '.join(select_parts)}\n"
        f"{from_clause}"
        f"WHERE {{\n    {inner}\n}}\n"
        f"GROUP BY {' '.join(group_keys)}{having_clause} ORDER BY {' '.join(order_terms)} {tail}"
    )

    # Count = number of distinct group tuples = COUNT(*) over the grouped subquery. The subquery
    # inherits the outer FROM dataset, so it carries no GRAPH wrapper.
    sub = (
        f"SELECT {' '.join(group_keys)} WHERE {{ "
        f"{' '.join(where_lines)} }} GROUP BY {' '.join(group_keys)}{having_clause}"
    )
    count_sparql = f"SELECT (COUNT(*) AS ?total)\n{from_clause}WHERE {{ {sub} }}"

    return CompiledQuery(
        sparql=page_sparql,
        count_sparql=count_sparql,
        columns=tuple(metas),
        var_for_column=var_for_column,
        uses_offset_fallback=True,  # aggregate pages are always OFFSET-based
    )


def _strip_column_filter(node: FilterNode | None, column_id: str) -> FilterNode | None:
    """Remove conditions targeting ``column_id`` (Excel facet semantics: a column's dropdown
    sees the distribution unconstrained by its *own* filter)."""
    if node is None:
        return None
    if isinstance(node, FilterCondition):
        if isinstance(node.target, FilterColumnTarget) and node.target.column_id == column_id:
            return None
        return node
    if isinstance(node, FilterGroup):
        kept = [c for c in (_strip_column_filter(ch, column_id) for ch in node.children) if c is not None]
        if not kept:
            return None
        return kept[0] if len(kept) == 1 else FilterGroup(node.op, tuple(kept))
    if isinstance(node, FilterNot):
        child = _strip_column_filter(node.child, column_id)
        return FilterNot(child) if child is not None else None
    return node  # pragma: no cover


def compile_facet(spec: ListSpec, ctx: CompileContext, *, target_column_id: str, search: str = "", limit: int = 50) -> str:
    """Distinct values + per-value root counts for one column, under all OTHER columns' filters.

    The target column's own filter is stripped. Returns one SPARQL query: ``?v`` is the
    column's value, ``?cnt`` the number of distinct roots having it. ``LIMIT limit+1`` lets
    the caller detect truncation.
    """
    columns_by_id = {c.id: c for c in spec.columns}
    if target_column_id not in columns_by_id:
        raise GraphQuerySpecError(f"facet column {target_column_id!r} not in spec")
    col = columns_by_id[target_column_id]
    if isinstance(col.source, AggregateSource):
        raise GraphQuerySpecError("cannot facet a measure column")

    from_clause = _from_clause(spec)
    anchor = _anchor_lines(spec.root)

    src = col.source
    triples, end = _lower_path(getattr(src, "path", ()), "?root", "fv")
    if isinstance(src, PropertySource):
        triples.append(f"{end} {sparql_iri(src.predicate)} ?v .")
    elif isinstance(src, NodeSource):
        if src.show == "uri":
            triples.append(f"BIND({end} AS ?v)")
        else:
            triples.append(
                f"OPTIONAL {{ {end} <http://www.w3.org/2000/01/rdf-schema#label> ?vlbl . }} "
                f"BIND(COALESCE(?vlbl, STR({end})) AS ?v)"
            )

    # Other-column filters are emitted with an empty-cardinality context so they lower to
    # self-contained EXISTS branches (no reliance on projected ?col_<id> vars, which the
    # facet query doesn't bind).
    surviving = _strip_column_filter(spec.filters, target_column_id)
    facet_ctx = CompileContext(fts_backend=ctx.fts_backend)
    emitter = _FilterEmitter(columns_by_id, {c.id: f"?col_{c.id}" for c in spec.columns}, facet_ctx)
    filter_lines = emitter.emit_top(surviving) if surviving is not None else []

    search_lines: list[str] = []
    if search.strip():
        term = sparql_string_literal(search.strip().lower())
        search_lines = [f"FILTER(CONTAINS(LCASE(STR(?v)), {term}))"]

    inner = "\n    ".join(anchor + triples + filter_lines + search_lines)
    return (
        f"SELECT ?v (COUNT(DISTINCT ?root) AS ?cnt)\n"
        f"{from_clause}"
        f"WHERE {{\n    {inner}\n}}\n"
        f"GROUP BY ?v ORDER BY DESC(?cnt) ?v LIMIT {int(limit) + 1}"
    )


def compile_query(spec: object, ctx: CompileContext, page: object | None = None) -> CompiledQuery:
    """Dispatch on spec mode."""
    if isinstance(spec, ListSpec):
        return compile_list(spec, ctx, page)
    if isinstance(spec, AggregateSpec):
        return compile_aggregate(spec, ctx, page)
    raise GraphQuerySpecError(f"unsupported spec type: {type(spec).__name__}")
