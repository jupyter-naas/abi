import pytest

from naas_abi_sdk.redaction import REDACTED, scrub_secrets


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("Authorization: Bearer abc.def-ghi", "Authorization: Bearer "),
        ("401 for bearer eyJhbGciOi", "401 for bearer "),
        ("bad key sk-or-v1-0123456789abcdef0123456789abcdef", "bad key "),
        ("key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv rejected", "key "),
        ("token sk-proj-AbCdEfGhIjKlMnOpQrStUvWx", "token "),
        ("git: ghp_0123456789abcdefghijABCDEFGHIJ", "git: "),
        ("pat github_pat_11ABCDEFG0123456789_abcdefghij", "pat "),
        ("aws AKIAIOSFODNN7EXAMPLE denied", "aws "),
        ("slack xoxb-1234567890-abcdefghij", "slack "),
        ("google AIzaSyA-0123456789abcdefghijklmnopqrstu", "google "),
        ("stripe sk_live_0123456789abcdef", "stripe "),
        ("https://api.x.io/v1?key=abc123&page=2", "https://api.x.io/v1?key="),
        ("api_key=s3cr3t", "api_key="),
        ('{"api_key": "s3cr3t", "n": 1}', '{"api_key": "'),
        ("password: hunter2", "password: "),
        ("client_secret=abc&grant_type=x", "client_secret="),
        ("X-Amz-Signature=deadbeef01", "X-Amz-Signature="),
        ("postgresql://abi:hunter2@db:5432/abi", "postgresql://"),
        ("Authorization: Basic dXNlcjpwYXNz", "Authorization: Basic "),
        (
            "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhYmkifQ.c2lnbmF0dXJl",
            "jwt ",
        ),
    ],
)
def test_secrets_are_redacted_and_the_rest_kept(text, kept):
    scrubbed = scrub_secrets(text)

    assert REDACTED in scrubbed
    assert scrubbed.startswith(kept)
    for secret in (
        "abc.def-ghi",
        "0123456789abcdef0123456789abcdef",
        "AbCdEfGhIjKlMnOpQrStUv",
        "0123456789abcdefghijABCDEFGHIJ",
        "IOSFODNN7EXAMPLE",
        "1234567890-abcdefghij",
        "abc123",
        "s3cr3t",
        "hunter2",
        "deadbeef01",
        "dXNlcjpwYXNz",
        "c2lnbmF0dXJl",
    ):
        assert secret not in scrubbed


def test_the_rest_of_a_message_stays_readable():
    assert scrub_secrets("GET https://h/x?page=2&key=abc failed (401)") == (
        f"GET https://h/x?page=2&key={REDACTED} failed (401)"
    )
    assert scrub_secrets("postgresql://abi:hunter2@db:5432/abi") == (
        f"postgresql://{REDACTED}@db:5432/abi"
    )
    assert (
        scrub_secrets("authorization=abc123; next") == f"authorization={REDACTED}; next"
    )
    assert (
        scrub_secrets("Authorization: Token abc") == f"Authorization: Token {REDACTED}"
    )


@pytest.mark.parametrize(
    "text",
    [
        "KeyError: 'name'",
        "missing key error in mapping",
        "https://api.naas.ai/workspace/123?page=2",
        "ssh://git@github.com/org/repo",
        "trace 4bf92f3577b34da6a3ce929d0e0e4736 span 00f067aa0ba902b7",
        "sha256 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "the token expired, ask for a new one",
        "Task skipped: no secret configured",
        "",
    ],
)
def test_ordinary_text_is_left_alone(text):
    assert scrub_secrets(text) == text
