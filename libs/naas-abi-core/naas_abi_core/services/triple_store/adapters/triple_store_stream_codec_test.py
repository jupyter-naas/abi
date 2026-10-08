from naas_abi_core.services.triple_store.adapters.triple_store_stream_codec import (
    decode_header,
    decode_rows,
    decode_triples,
    encode_header,
    row_frames,
    triple_frames,
)
from naas_abi_core.services.triple_store.TripleStorePorts import QueryStream
from rdflib import BNode, Literal, URIRef


def test_select_rows_cross_the_wire_in_bounded_frames():
    rows = [
        {"s": URIRef(f"http://ex/{n}"), "label": Literal(f"multi\nline {n}", lang="en")}
        for n in range(500)
    ]
    rows.append({"s": URIRef("http://ex/unbound")})

    frames = list(row_frames(iter(rows), frame_bytes=4096))

    assert len(frames) > 1 and all(len(frame) < 2 * 4096 for frame in frames)
    assert [row for frame in frames for row in decode_rows(frame)] == rows


def test_triples_keep_blank_nodes_across_frames():
    blank = BNode()
    triples = [(blank, URIRef("http://ex/p"), Literal(n)) for n in range(300)]
    triples.append((URIRef("http://ex/a"), URIRef("http://ex/q"), blank))

    frames = list(triple_frames(iter(triples), frame_bytes=1024))
    bnodes: dict = {}
    decoded = [t for frame in frames for t in decode_triples(frame, bnodes)]

    assert len(frames) > 1 and len(decoded) == len(triples)
    assert len({s for s, _, _ in decoded[:-1]} | {decoded[-1][2]}) == 1


def test_the_header_carries_the_result_type_variables_and_ask_answer():
    select = decode_header(encode_header(QueryStream("SELECT", vars=["s", "o"])))
    ask = decode_header(encode_header(QueryStream("ASK", ask_answer=False)))
    construct = decode_header(encode_header(QueryStream("DESCRIBE")))

    assert (select.result_type, select.vars) == ("SELECT", ["s", "o"])
    assert (ask.result_type, ask.ask_answer) == ("ASK", False)
    assert construct.result_type == "DESCRIBE"
