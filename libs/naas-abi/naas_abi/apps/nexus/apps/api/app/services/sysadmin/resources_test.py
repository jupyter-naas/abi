import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    PREVIEW_BYTES,
    InvalidResource,
    ResourceEntry,
    paginate,
    text_preview,
)


def _entries(n):
    return [ResourceEntry(str(i), str(i), "item") for i in range(n)]


def test_paginate_walks_a_listing_with_offsets():
    first = paginate("", _entries(5), None, 2)
    second = paginate("", _entries(5), first.next_cursor, 2)
    last = paginate("", _entries(5), second.next_cursor, 2)

    assert [e.id for e in first.entries + second.entries + last.entries] == list("01234")
    assert last.next_cursor is None


@pytest.mark.parametrize("cursor,limit", [("x", 2), ("-1", 2), (None, 0)])
def test_paginate_rejects_bad_cursors_and_limits(cursor, limit):
    with pytest.raises(InvalidResource):
        paginate("", _entries(3), cursor, limit)


def test_text_preview_of_small_text():
    content = text_preview("héllo".encode())

    assert (content.encoding, content.text, content.truncated) == ("text", "héllo", False)
    assert content.size == len("héllo".encode())


def test_text_preview_is_bounded_and_drops_a_cut_character():
    raw = b"a" * (PREVIEW_BYTES - 1) + "é".encode() + b"tail"

    content = text_preview(raw)

    assert content.encoding == "text"
    assert content.truncated is True
    assert content.text == "a" * (PREVIEW_BYTES - 1)
    assert content.size == len(raw)


def test_text_preview_reports_binary_without_a_value():
    content = text_preview(b"\x89PNG\r\n\x1a\n\x00\x00")

    assert (content.encoding, content.text, content.size) == ("binary", None, 10)
    assert text_preview(b"nul\x00inside").encoding == "binary"


def test_text_preview_of_a_head_uses_the_total_size():
    content = text_preview(b"x" * (PREVIEW_BYTES + 1), total=10 * PREVIEW_BYTES)

    assert content.truncated is True
    assert content.size == 10 * PREVIEW_BYTES
    assert len(content.text) == PREVIEW_BYTES
