"""The sign-in mail leaves from the deployment's own mailbox (#1643).

With no sender of its own, the identity provider sends with ``from_email=""``,
and the engine's email adapter uses the sender it is configured with (Outlook's
``user``, the ``from_email`` of SMTP / SES / SendGrid). A made-up default such
as ``no-reply@abi.local`` was refused by every real provider, and nobody got a
code.
"""

from naas_abi_idp.configuration import IdPConfiguration

ISSUER = "https://api.example.com/idp"


def test_no_sender_by_default():
    assert IdPConfiguration(issuer=ISSUER).from_email == ""


def test_the_environment_still_names_one():
    configuration = IdPConfiguration.from_environment(
        {"ABI_IDP_ISSUER": ISSUER, "ABI_IDP_FROM_EMAIL": "team@example.com"}
    )
    assert configuration.from_email == "team@example.com"


def test_unset_in_the_environment_leaves_it_to_the_engine():
    assert (
        IdPConfiguration.from_environment({"ABI_IDP_ISSUER": ISSUER}).from_email == ""
    )
