"""A project's own Abi (a subclass, like Joe): it keeps its identity and model,
takes Abi's sub-agents, and the two never build each other."""

from __future__ import annotations

from types import SimpleNamespace

import naas_abi
import pytest
from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi_core.services.agent.Agent import Agent


def _stub(name: str, **attrs: object) -> type:
    def new(cls: type, **_: object) -> SimpleNamespace:
        return SimpleNamespace(duplicate=lambda **_: SimpleNamespace(name=name))

    return type(name, (Agent,), {"name": name, "New": classmethod(new), **attrs})


@pytest.fixture
def orchestrators() -> SimpleNamespace:
    """Bob fronts its agents and has its own model; Carol is a plain sibling.

    Built here, not at import: the in-process agent index imports every module
    under ``naas_abi.agents`` and would list a module-level class."""

    class Bob(AbiAgent):
        name = "Bob"
        fronts_its_agents = True

        @classmethod
        def get_chat_model_id(cls) -> str:
            return "bob-model"

        @classmethod
        def get_chat_model_provider(cls) -> str | None:
            return None

    class Carol(AbiAgent):
        name = "Carol"

    return SimpleNamespace(
        bob=Bob,
        carol=Carol,
        apps=_stub("Apps"),
        dan=_stub("Dan", delegates_to_abi=True),
    )


def _engine(monkeypatch, *, abi_agents: list, module_agents: list) -> None:
    fake = SimpleNamespace(
        agents=abi_agents,
        engine=SimpleNamespace(modules={"bob": SimpleNamespace(agents=module_agents)}),
    )
    monkeypatch.setattr(
        naas_abi.ABIModule, "get_instance", classmethod(lambda cls: fake)
    )


def test_a_specialization_takes_abis_sub_agents_but_no_orchestrator(
    monkeypatch, orchestrators
) -> None:
    o = orchestrators
    _engine(
        monkeypatch,
        abi_agents=[o.apps, AbiAgent],
        module_agents=[o.bob, o.carol, o.dan],
    )

    agents, state = o.bob.get_agents()

    assert [a.name for a in agents] == ["Apps"]
    assert state.supervisor_agent == "Bob"


def test_abi_does_not_build_its_specializations(monkeypatch, orchestrators) -> None:
    o = orchestrators
    _engine(monkeypatch, abi_agents=[o.apps, AbiAgent], module_agents=[o.bob])

    agents, _ = AbiAgent.get_agents()

    assert [a.name for a in agents] == ["Apps"]


def test_hands_off_to_every_agent_but_orchestrators_and_their_delegators(
    orchestrators,
) -> None:
    o = orchestrators
    assert o.bob.hands_off_to(o.apps) and AbiAgent.hands_off_to(o.apps)
    for orchestrator in (AbiAgent, o.bob, o.carol, o.dan):
        assert not o.bob.hands_off_to(orchestrator)
        assert not AbiAgent.hands_off_to(orchestrator)


def test_fronts_what_it_inherits_and_hands_work_to(orchestrators) -> None:
    o = orchestrators
    assert o.bob.fronts(AbiAgent)
    assert o.bob.fronts(o.apps)
    assert not o.bob.fronts(o.bob)
    # A sibling orchestrator and a supervisor over Abi are not reached through Bob.
    assert not o.bob.fronts(o.carol)
    assert not o.bob.fronts(o.dan)


def test_fronting_is_opt_in(orchestrators) -> None:
    o = orchestrators
    assert AbiAgent.fronts_its_agents is False
    assert not AbiAgent.fronts(o.apps)
    assert not o.carol.fronts(AbiAgent)
    assert not o.carol.fronts(o.apps)


class _Stop(Exception):
    pass


@pytest.mark.parametrize(
    ("which", "model_id", "expected"),
    [
        ("bob", None, ("bob-model", None)),
        ("bob", "picked", ("picked", None)),
        ("abi", None, ("abi-model", "abi-provider")),
    ],
)
def test_new_builds_on_the_class_model(
    monkeypatch, orchestrators, which, model_id, expected
) -> None:
    calls: list[tuple[str, str | None]] = []

    def get_chat_model(model: str, provider: str | None = None) -> None:
        calls.append((model, provider))
        raise _Stop

    fake = SimpleNamespace(
        configuration=SimpleNamespace(
            abi_agent_model="abi-model", abi_agent_provider="abi-provider"
        ),
        engine=SimpleNamespace(
            services=SimpleNamespace(
                model_registry=SimpleNamespace(get_chat_model=get_chat_model)
            )
        ),
    )
    monkeypatch.setattr(
        naas_abi.ABIModule, "get_instance", classmethod(lambda cls: fake)
    )
    agent_cls = orchestrators.bob if which == "bob" else AbiAgent

    with pytest.raises(_Stop):
        agent_cls.New(model_id=model_id)

    assert calls == [expected]
