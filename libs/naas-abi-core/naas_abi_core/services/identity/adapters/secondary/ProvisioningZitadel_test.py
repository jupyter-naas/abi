"""ProvisioningZitadel's state changes, on a recorded admin API: what each user
state needs to be deactivated or reactivated. The rest of the adapter runs against
the pinned Zitadel binary (``tests/zitadel_provisioning_test.py``)."""

from __future__ import annotations

from typing import Any

import pytest

from naas_abi_core.services.identity.adapters.secondary.ProvisioningZitadel import (
    INACTIVE,
    INITIAL,
    LOCKED,
    ProvisioningZitadel,
)

ACTIVE = "USER_STATE_ACTIVE"


class Recorded:
    """Zitadel's admin API for one user in ``state``: GET answers it, the state
    calls change it, and every call is kept."""

    def __init__(self, state: str) -> None:
        self.state = state
        self.calls: list[str] = []

    def request(self, method: str, path: str, **_: Any) -> tuple[int, Any, dict]:
        self.calls.append(f"{method} {path}")
        if method == "GET":
            user = {
                "userId": "u-1",
                "state": self.state,
                "human": {"email": {"email": "a@example.com"}, "profile": {}},
            }
            return 200, {"user": user}, {}
        step = path.rsplit("/", 1)[-1]
        if step == "unlock" and self.state == LOCKED:
            self.state = ACTIVE
        elif step == "deactivate" and self.state == ACTIVE:
            self.state = INACTIVE
        elif step == "reactivate" and self.state == INACTIVE:
            self.state = ACTIVE
        elif step == "lock" and self.state in (ACTIVE, INITIAL):
            self.state = LOCKED
        else:  # as Zitadel answers a change the state does not allow
            return 400, {"message": f"cannot {step} a user in {self.state}"}, {}
        return 200, {}, {}


def _steps(http: Recorded) -> list[str]:
    return [c.rsplit("/", 1)[-1] for c in http.calls if c.startswith("POST")]


@pytest.mark.parametrize(
    ("state", "disabled", "steps", "after"),
    [
        (LOCKED, False, ["unlock"], ACTIVE),
        (LOCKED, True, ["unlock", "deactivate"], INACTIVE),
        (INACTIVE, False, ["reactivate"], ACTIVE),
        (ACTIVE, True, ["deactivate"], INACTIVE),
        (ACTIVE, False, [], ACTIVE),
        (INACTIVE, True, [], INACTIVE),
        # Never set up (made elsewhere): Zitadel refuses /deactivate ("can only be
        # deleted"), so it is locked; reactivating unlocks it, and Zitadel makes it
        # active (as the pinned binary does).
        (INITIAL, True, ["lock"], LOCKED),
    ],
)
def test_each_state_is_changed_the_way_zitadel_takes_it(state, disabled, steps, after):
    http = Recorded(state)
    user = ProvisioningZitadel("zitadel", http).update_user("u-1", disabled=disabled)  # type: ignore[arg-type]
    assert _steps(http) == steps
    assert http.state == after
    assert user is not None and user.disabled is (after != ACTIVE)
