from __future__ import annotations

from email import message_from_bytes
from pathlib import Path

import pytest
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
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
