import base64

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.otlp_json import (
    attributes,
    flatten,
    hex_id,
    service_spans,
    to_traces,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    ServiceCount,
    SpanEvent,
    SpanLink,
    TraceRoot,
    summarize,
)


def _trace():
    (trace,) = to_traces(fixtures.otlp_response())
    return trace


def test_attribute_values_of_every_type():
    values = attributes(fixtures.otlp_attributes(s="x", b=True, d=0.5, i=7, a=[1, "y"], m={"k": 2}))

    assert values == {"s": "x", "b": True, "d": 0.5, "i": 7, "a": [1, "y"], "m": {"k": 2}}
    assert flatten(values)["a"] == '[1, "y"]' and flatten(values)["m"] == '{"k": 2}'


def test_spans_are_laid_out_from_the_trace_start():
    trace = _trace()

    assert trace.trace_id == fixtures.OTLP_TRACE
    assert trace.start == "2025-10-02T08:00:00+00:00"
    assert trace.duration_ms == 120.0
    assert [(s.name, s.start_ms, s.duration_ms) for s in trace.spans] == [
        ("GET /api/search", 0.0, 100.0),
        ("document/get", 0.0, 20.0),  # same start as its parent: by depth
        ("flush", 30.0, 90.0),
        ("rank", 40.0, 10.0),
    ]
    assert not trace.truncated


def test_kinds_parents_and_services():
    spans = {s.name: s for s in _trace().spans}

    assert [spans[n].kind for n in ("GET /api/search", "document/get", "rank")] == [
        "server",
        "client",
        "internal",
    ]
    assert spans["GET /api/search"].parent_id is None
    assert spans["document/get"].parent_id == "00f067aa0ba902b7"
    assert spans["flush"].parent_id is None  # its parent is not in the trace
    assert spans["document/get"].service == "zen-engine"
    assert spans["GET /api/search"].resource == {
        "service.name": "nexus-api",
        "deployment.environment": "dev",
    }


def test_error_status_and_error_tag():
    spans = {s.name: s for s in _trace().spans}

    assert (spans["GET /api/search"].status, spans["flush"].status) == ("ok", "unset")
    assert (spans["document/get"].status, spans["document/get"].status_message) == ("error", "boom")
    assert spans["rank"].status == "error"  # error=true attribute
    assert _trace().services == (ServiceCount("zen-engine", 3, 2), ServiceCount("nexus-api", 1, 0))


def test_attributes_events_and_links():
    spans = {s.name: s for s in _trace().spans}

    assert spans["GET /api/search"].attributes == {
        "http.request.method": "GET",
        "http.response.status_code": 200,
        "abi.cached": False,
        "abi.ratio": 0.5,
        "abi.tags": '["a", "b"]',
        "abi.labels": '{"team": "ops"}',
    }
    assert spans["document/get"].events == (SpanEvent("retry", 2.0, {"attempt": 2}),)
    assert spans["document/get"].links == (
        SpanLink("5b8efff798038103d269b633813fc60c", "5fb397be34d26b51"),
    )


def test_summary_of_a_trace():
    summary = summarize(_trace())

    assert summary.root == TraceRoot("nexus-api", "GET /api/search")
    assert (summary.spans, summary.errors, summary.duration_ms) == (4, 2, 120.0)
    assert summary.start == "2025-10-02T08:00:00+00:00"


def test_the_earliest_span_is_the_root_when_every_parent_is_missing():
    response = {
        "result": {
            "resourceSpans": [
                fixtures.otlp_resource(
                    "zen-engine",
                    fixtures.otlp_span("a" * 32, "2" * 16, "later", parent="9" * 16, start_ms=5),
                    fixtures.otlp_span("a" * 32, "1" * 16, "first", parent="8" * 16),
                )
            ]
        }
    }
    (trace,) = to_traces(response)

    assert summarize(trace).root == TraceRoot("zen-engine", "first")


def test_spans_are_deduplicated_across_responses_and_grouped_by_trace():
    other = fixtures.otlp_span("C" * 32, "1" * 16, "other", kind=5)
    second = {"result": {"resourceSpans": [fixtures.otlp_resource("ops", other)]}}

    traces = to_traces([fixtures.otlp_response(), fixtures.otlp_response(), second])

    assert sorted(len(t.spans) for t in traces) == [1, 4]
    assert {t.trace_id for t in traces} == {fixtures.OTLP_TRACE, "c" * 32}  # lowercased


def test_over_the_span_cap_the_rest_is_dropped():
    root = f"{1:016x}"
    spans = [
        fixtures.otlp_span("a" * 32, f"{i + 1:016x}", f"s{i}", parent=root if i else "", start_ms=i)
        for i in range(5001)
    ]
    response = {"result": {"resourceSpans": [fixtures.otlp_resource("zen-engine", *spans)]}}

    (trace,) = to_traces(response)
    (small,) = to_traces(response, max_spans=3)

    assert trace.truncated and len(trace.spans) == 5000
    assert trace.spans[-1].name == "s4999" and trace.duration_ms == 5001.0
    assert [(s.name, s.parent_id) for s in small.spans] == [
        ("s0", None),
        ("s1", root),
        ("s2", root),
    ]
    assert small.truncated and not to_traces(response, max_spans=5001)[0].truncated


def test_ids_from_base64_are_accepted():
    raw = bytes.fromhex(fixtures.OTLP_TRACE)

    assert hex_id(base64.b64encode(raw).decode(), 32) == fixtures.OTLP_TRACE
    assert hex_id(fixtures.OTLP_TRACE.upper(), 32) == fixtures.OTLP_TRACE
    assert hex_id("not an id", 32) == "" and hex_id(None, 16) == ""


def test_service_spans_pair_each_span_with_its_service():
    pairs = service_spans(fixtures.otlp_response())

    assert [service for service, _ in pairs] == ["nexus-api"] + ["zen-engine"] * 3
    assert to_traces({}) == [] and service_spans({}) == []
