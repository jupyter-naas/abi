from datetime import date

from naas_abi_core.services.dataset.adapters.dataset_stream_codec import (
    decode_header,
    decode_rows,
    encode_header,
    row_frames,
)


def test_rows_cross_the_wire_in_bounded_frames():
    rows = [{"id": n, "name": f"row {n}", "payload": {"n": n}} for n in range(3000)]
    rows.append({"id": None, "name": "unbound", "payload": None})

    frames = list(row_frames(iter(rows), frame_bytes=8192))

    assert len(frames) > 1 and all(len(frame) < 2 * 8192 for frame in frames)
    decoded = [row for frame in frames for row in decode_rows(frame)]
    assert decoded[:2] == [
        {"id": 0, "name": "row 0", "payload": {"n": 0}},
        {"id": 1, "name": "row 1", "payload": {"n": 1}},
    ]
    assert type(decoded[1]["id"]) is int
    assert decoded[-1] == {"id": None, "name": "unbound", "payload": None}
    assert len(decoded) == 3001


def test_frames_keep_integers_exact_and_carry_dates():
    rows = [{"id": 2**60 + 1, "when": date(2026, 10, 4)}]

    decoded = [row for frame in row_frames(iter(rows)) for row in decode_rows(frame)]

    assert decoded == [{"id": 2**60 + 1, "when": "2026-10-04"}]


def test_the_header_carries_the_columns():
    assert decode_header(encode_header(["id", "name"])) == ["id", "name"]
