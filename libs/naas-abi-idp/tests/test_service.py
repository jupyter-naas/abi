import pytest

from naas_abi_idp.ports import (
    Conflict,
    InvalidArgument,
    InvalidCode,
    NotFound,
    RateLimited,
)


def test_a_user_is_registered_with_just_an_email(service):
    user = service.create_user("Alice@Example.com")
    assert user.email == "alice@example.com"
    assert user.name == "Alice"
    assert user.id.startswith("u_")
    assert service.find_user("alice@EXAMPLE.com").id == user.id
    with pytest.raises(Conflict):
        service.create_user("alice@example.com")
    with pytest.raises(InvalidArgument):
        service.create_user("not an email")


def test_the_groups_claim_lists_group_names(service):
    group = service.create_group("Data readers")
    user = service.create_user("bob@example.com", groups=["Data readers"])
    assert user.groups == [group.id]
    assert service.group_names(user) == ["Data readers"]
    service.remove_member(group.id, user.id)
    assert service.group_names(service.get_user(user.id)) == []
    service.add_member("Data readers", user.id)
    service.delete_group(group.id)
    assert service.get_user(user.id).groups == []
    with pytest.raises(NotFound):
        service.add_member("Nope", user.id)


def test_a_code_is_emailed_and_opens_once(service, mailer):
    user = service.create_user("alice@example.com")
    assert service.request_code("alice@example.com", "10.0.0.1")
    code = mailer.last_code("alice@example.com")
    assert len(code) == 6
    assert mailer.sent[-1].from_email == service.configuration.from_email
    assert service.verify_code("alice@example.com", code, "10.0.0.1").id == user.id
    with pytest.raises(InvalidCode):  # spent
        service.verify_code("alice@example.com", code, "10.0.0.1")


def test_an_unknown_address_gets_no_mail_and_the_same_answer(service, mailer):
    assert service.request_code("nobody@example.com", None) is False
    assert mailer.sent == []
    with pytest.raises(InvalidCode):
        service.verify_code("nobody@example.com", "123456", None)


def test_sign_up_registers_an_address_when_it_is_on(service, mailer):
    service.configuration.signup_enabled = True
    assert service.request_code("new@example.com", None)
    user = service.verify_code(
        "new@example.com", mailer.last_code("new@example.com"), None
    )
    assert user.email == "new@example.com"


def test_a_disabled_user_gets_no_code(service, mailer):
    user = service.create_user("alice@example.com")
    service.set_disabled(user.id, True)
    assert service.request_code("alice@example.com", None) is False
    assert mailer.sent == []


def test_a_code_expires(service, mailer, clock):
    service.create_user("alice@example.com")
    service.request_code("alice@example.com", None)
    code = mailer.last_code("alice@example.com")
    clock.advance(service.configuration.code_ttl_seconds + 1)
    with pytest.raises(InvalidCode):
        service.verify_code("alice@example.com", code, None)


def wrong(service, email, ip=None):
    with pytest.raises(InvalidCode):
        service.verify_code(email, "000000", ip)


def test_wrong_guesses_count_against_every_active_code(service, mailer):
    """Bug (e): asking for a fresh code must not renew the budget of guesses."""
    service.create_user("alice@example.com")
    config = service.configuration
    service.request_code("alice@example.com", None)
    first = mailer.last_code("alice@example.com")
    for _ in range(config.max_attempts - 1):
        wrong(service, "alice@example.com")
    service.request_code("alice@example.com", None)  # a second active code
    second = mailer.last_code("alice@example.com")
    wrong(service, "alice@example.com")  # the last guess of the budget
    # Both codes are void now, and the address is locked for the window.
    for code in (first, second):
        with pytest.raises(RateLimited):
            service.verify_code("alice@example.com", code, None)


def test_the_budget_is_spent_before_a_guess_is_judged(service, mailer):
    service.create_user("alice@example.com")
    service.request_code("alice@example.com", None)
    code = mailer.last_code("alice@example.com")
    for _ in range(service.configuration.max_attempts):
        wrong(service, "alice@example.com")
    with pytest.raises(RateLimited):  # even the right code, once the budget is gone
        service.verify_code("alice@example.com", code, None)


def test_the_lock_ends_with_the_window(service, mailer, clock):
    service.create_user("alice@example.com")
    for _ in range(service.configuration.max_attempts):
        wrong(service, "alice@example.com")
    clock.advance(service.configuration.rate_limit_window_seconds + 1)
    service.request_code("alice@example.com", None)
    code = mailer.last_code("alice@example.com")
    assert service.verify_code("alice@example.com", code, None)


def test_a_success_clears_the_failures(service, mailer):
    service.create_user("alice@example.com")
    service.request_code("alice@example.com", None)
    code = mailer.last_code("alice@example.com")
    for _ in range(service.configuration.max_attempts - 1):
        wrong(service, "alice@example.com")
    service.verify_code("alice@example.com", code, None)
    service.request_code("alice@example.com", None)
    for _ in range(service.configuration.max_attempts - 1):
        wrong(service, "alice@example.com")


def test_codes_per_address_are_limited(service):
    service.create_user("alice@example.com")
    for _ in range(service.configuration.rate_limit_email_sends):
        service.request_code("alice@example.com", None)
    with pytest.raises(RateLimited):
        service.request_code("alice@example.com", None)


def test_attempts_per_client_address_are_limited(service):
    for i in range(service.configuration.rate_limit_ip_attempts):
        with pytest.raises(InvalidCode):
            service.verify_code(f"nobody{i}@example.com", "123456", "10.0.0.9")
    with pytest.raises(RateLimited):
        service.verify_code("other@example.com", "123456", "10.0.0.9")
    # Another address is unaffected.
    with pytest.raises(InvalidCode):
        service.verify_code("other@example.com", "123456", "10.0.0.10")


def test_only_the_latest_codes_stay_active(service, mailer):
    service.create_user("alice@example.com")
    service.configuration.rate_limit_email_sends = 50
    service.configuration.max_active_codes = 2
    codes = []
    for _ in range(3):
        service.request_code("alice@example.com", None)
        codes.append(mailer.last_code("alice@example.com"))
    if codes[0] not in codes[1:]:
        with pytest.raises(InvalidCode):
            service.verify_code("alice@example.com", codes[0], None)
    assert service.verify_code("alice@example.com", codes[1], None)


def test_a_failed_mail_leaves_no_code_behind(service, mailer):
    service.create_user("alice@example.com")
    mailer.fail = True
    with pytest.raises(RuntimeError):
        service.request_code("alice@example.com", None)
    mailer.fail = False
    assert mailer.sent == []


def test_password_sign_in_is_off_unless_enabled(service):
    user = service.create_user("alice@example.com", password="correct horse battery")
    with pytest.raises(InvalidCode):
        service.verify_password("alice@example.com", "correct horse battery", None)
    service.configuration.password_login_enabled = True
    assert (
        service.verify_password("alice@example.com", "correct horse battery", None).id
        == user.id
    )
    with pytest.raises(InvalidCode):
        service.verify_password("alice@example.com", "wrong password!!", None)
    with pytest.raises(InvalidCode):
        service.verify_password("nobody@example.com", "correct horse battery", None)
    with pytest.raises(InvalidArgument):
        service.create_user("bob@example.com", password="short")


def test_the_password_is_never_shown_or_stored_in_clear(service):
    user = service.create_user("alice@example.com", password="correct horse battery")
    assert "password_hash" not in user.public()
    assert user.public()["has_password"] is True
    assert "correct horse battery" not in repr(service.store.get("users", user.id))


def test_sessions_end_and_follow_the_user(service):
    user = service.create_user("alice@example.com")
    cookie, _ = service.create_session(user, ["otp"])
    found = service.get_session(cookie)
    assert found is not None and found[1].id == user.id and found[0].amr == ("otp",)
    service.set_disabled(user.id, True)
    assert service.get_session(cookie) is None


def test_a_session_expires(service, clock):
    user = service.create_user("alice@example.com")
    cookie, _ = service.create_session(user, ["otp"])
    clock.advance(service.configuration.session_hours * 3600 + 1)
    assert service.get_session(cookie) is None


def test_the_signing_key_rotates_and_the_old_one_stays_published(service, clock):
    first = service.keys.active()
    clock.advance(service.configuration.key_rotation_days * 86400 + 1)
    second = service.keys.active()
    assert second.kid != first.kid
    kids = [k["kid"] for k in service.keys.jwks()["keys"]]
    assert kids == [second.kid, first.kid]
    clock.advance(25 * 3600)
    assert [k["kid"] for k in service.keys.jwks()["keys"]] == [second.kid]


def test_no_private_key_is_in_the_documents_or_the_jwks(service):
    service.keys.active()
    jwks = service.keys.jwks()
    assert all("d" not in k for k in jwks["keys"])
    page = service.store.find("keys")
    assert all("d" not in d.data["public"] for d in page.items)
    assert "idp/code-key" not in str(page.items)


def test_a_client_secret_is_shown_once_and_stored_hashed(service):
    client, secret = service.create_client("ci", scopes=["jobs"])
    assert secret and client.check_client_secret(secret)
    assert secret not in repr(service.store.get("clients", client.client_id))
    assert not client.check_client_secret("wrong")
    assert "secret_hash" not in client.public()
    with pytest.raises(InvalidArgument):
        service.create_client("x", grant_types=["authorization_code"])
    with pytest.raises(InvalidArgument):
        service.create_client("x", grant_types=["implicit"])


def test_the_configuration_seeds_clients_and_follows_changes(service, configuration):
    abi = service.get_client("abi")
    assert abi.source == "config" and abi.check_client_secret("abi-secret-abi-secret")
    configuration.clients[0].secret = "rotated-secret-rotated"
    service.seed_clients(configuration.clients)
    abi = service.get_client("abi")
    assert abi.check_client_secret("rotated-secret-rotated")
    assert not abi.check_client_secret("abi-secret-abi-secret")
    assert service.get_client("public-app").secret_hash is None


def test_purge_removes_what_expired(service, clock, mailer):
    service.create_user("alice@example.com")
    service.request_code("alice@example.com", "10.0.0.1")
    service.save_auth_request({"client_id": "abi"})
    clock.advance(24 * 3600)
    assert service.purge_expired() >= 3
