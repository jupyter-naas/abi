from __future__ import annotations

from email import message_from_bytes
from pathlib import Path

import pytest
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
from naas_abi_core.services.email.EmailPorts import SentEmailNotFound
from naas_abi_core.services.email.tests.email__secondary_adapter__generic_test import (
    GenericEmailSecondaryAdapterTest,
)


class TestFilesystemAdapter(GenericEmailSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return FilesystemAdapter

    def test_send_writes_eml_file(self, tmp_path: Path) -> None:
        adapter = FilesystemAdapter(directory=str(tmp_path))

        adapter.send(
            to_email="alice@example.com",
            subject="Hello",
            text_body="Hello world",
            from_email="noreply@example.com",
            from_name="NEXUS",
            reply_to="support@example.com",
        )

        files = list(tmp_path.glob("*.eml"))
        assert len(files) == 1
        msg = message_from_bytes(files[0].read_bytes())
        assert msg["To"] == "alice@example.com"
        assert msg["Subject"] == "Hello"
        assert msg["From"] == "NEXUS <noreply@example.com>"
        assert msg["Reply-To"] == "support@example.com"

    def test_send_creates_directory_if_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "does" / "not" / "exist"
        adapter = FilesystemAdapter(directory=str(target))

        adapter.send(
            to_email="bob@example.com",
            subject="Hi",
            text_body="Body",
            from_email="noreply@example.com",
        )

        assert target.is_dir()
        assert len(list(target.glob("*.eml"))) == 1

    def test_send_includes_html_alternative(self, tmp_path: Path) -> None:
        adapter = FilesystemAdapter(directory=str(tmp_path))

        adapter.send(
            to_email="alice@example.com",
            subject="Hello",
            text_body="plain",
            html_body="<p>html</p>",
            from_email="noreply@example.com",
        )

        msg = message_from_bytes(next(tmp_path.glob("*.eml")).read_bytes())
        assert msg.is_multipart()
        subtypes = {part.get_content_subtype() for part in msg.walk() if not part.is_multipart()}
        assert "plain" in subtypes
        assert "html" in subtypes


def _send(adapter: FilesystemAdapter, subject: str, to: str = "alice@example.com") -> str:
    return adapter.send(
        to_email=to, subject=subject, text_body=f"body of {subject}", from_email="noreply@example.com"
    )


class TestFilesystemAdapterKeptMail:
    def test_send_returns_the_id_of_the_kept_copy(self, tmp_path: Path) -> None:
        adapter = FilesystemAdapter(directory=str(tmp_path))

        message_id = _send(adapter, "Hello")

        assert (tmp_path / f"{message_id}.eml").is_file()

    def test_lists_newest_first_and_pages_with_before(self, tmp_path: Path) -> None:
        adapter = FilesystemAdapter(directory=str(tmp_path))
        ids = [_send(adapter, f"s{i}") for i in range(3)]

        first = adapter.list_sent(limit=2)
        rest = adapter.list_sent(limit=2, before=first[-1].message_id)

        assert [m.message_id for m in first + rest] == list(reversed(ids))
        assert (first[0].subject, first[0].to, first[0].sender) == (
            "s2",
            "alice@example.com",
            "noreply@example.com",
        )
        assert first[0].size == (tmp_path / f"{ids[2]}.eml").stat().st_size
        assert first[0].sent_at.endswith("+00:00")

    def test_listing_carries_a_one_line_snippet_of_the_body(
        self, tmp_path: Path
    ) -> None:
        from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
            SNIPPET_CHARS,
        )

        adapter = FilesystemAdapter(directory=str(tmp_path))
        adapter.send(
            to_email="a@example.com",
            subject="text",
            text_body="Hello Alice,\n\n  the report   is ready. " + "x" * 400,
            from_email="n@example.com",
        )
        adapter.send(
            to_email="a@example.com",
            subject="html",
            text_body="",
            html_body="<p>Hi <b>Bob</b>,</p><p>see&nbsp;you</p>",
            from_email="n@example.com",
        )

        html, text = adapter.list_sent()

        assert text.snippet.startswith("Hello Alice, the report is ready. xxx")
        assert len(text.snippet) == SNIPPET_CHARS
        assert html.snippet == "Hi Bob, see you"
        assert adapter.get_sent(text.message_id).summary.snippet == text.snippet

    def test_a_message_too_large_to_parse_has_no_snippet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import naas_abi_core.services.email.adapters.secondary.FilesystemAdapter as module

        monkeypatch.setattr(module, "SNIPPET_MAX_BYTES", 100)
        adapter = FilesystemAdapter(directory=str(tmp_path))
        _send(adapter, "big")

        (listed,) = adapter.list_sent()

        assert listed.snippet == "" and listed.subject == "big"

    def test_get_and_delete_a_kept_message(self, tmp_path: Path) -> None:
        adapter = FilesystemAdapter(directory=str(tmp_path))
        message_id = _send(adapter, "Hello")

        sent = adapter.get_sent(message_id)
        adapter.delete_sent(message_id)

        assert message_from_bytes(sent.raw)["Subject"] == "Hello"
        assert sent.summary.message_id == message_id
        assert adapter.list_sent() == []
        with pytest.raises(SentEmailNotFound):
            adapter.get_sent(message_id)

    @pytest.mark.parametrize("bad", ["../secret", "nope", "1-" + "0" * 31, ""])
    def test_unknown_or_malformed_ids_are_not_found(self, tmp_path: Path, bad: str) -> None:
        adapter = FilesystemAdapter(directory=str(tmp_path))
        (tmp_path.parent / "secret.eml").write_bytes(b"Subject: no\n\n")

        with pytest.raises(SentEmailNotFound):
            adapter.get_sent(bad)
        with pytest.raises(SentEmailNotFound):
            adapter.delete_sent(bad)

    def test_listing_an_empty_or_missing_directory(self, tmp_path: Path) -> None:
        assert FilesystemAdapter(directory=str(tmp_path / "missing")).list_sent() == []
