from naas_abi_core.module.jobs_fallback import JobDescriptor, JobsMixin, job


class _Module(JobsMixin):
    jobs = (JobDescriptor("explicit"),)

    @job(description="Nightly report.")
    def nightly(self, ctx):
        return "done"


def test_declarations_are_kept_without_the_sdk():
    assert [j.name for j in _Module.jobs] == ["explicit", "nightly"]
    module = _Module()
    assert module._job_handlers["nightly"](None) == "done"
    assert module.missing_job_handlers() == {"explicit"}
    module.expose_job("explicit", lambda ctx: None)
    assert module.missing_job_handlers() == set()


def test_subclasses_inherit_decorated_jobs():
    class Child(_Module):
        @job()
        def hourly(self, ctx):
            return None

    assert {j.name for j in Child.jobs} == {"explicit", "nightly", "hourly"}
    assert set(Child()._job_handlers) == {"nightly", "hourly"}


def test_workflows_are_declared_without_the_sdk_and_not_run():
    import pytest
    from naas_abi_core.module.jobs_fallback import Cron, JobsNotHosted
    from naas_abi_core.module.workflows_fallback import workflow

    class Flows(JobsMixin):
        @workflow(triggers=(Cron("0 0 * * * *", input={"filter": "db"}),))
        def report(self, ctx, inp):
            """Builds the report."""
            return {}

    (declared,) = Flows.jobs
    assert declared.kind == "workflow" and declared.description == "Builds the report."
    assert declared.triggers[0].input == {"filter": "db"}
    flows = Flows()
    flows.declare_workflow("workflow.bridged", lambda ctx, inp: None, description="x")
    assert {j.name for j in flows.jobs} == {"report", "workflow.bridged"}
    assert flows.missing_job_handlers() == set()  # the method and the lambda
    with pytest.raises(JobsNotHosted):
        flows.get_workflow("report")
