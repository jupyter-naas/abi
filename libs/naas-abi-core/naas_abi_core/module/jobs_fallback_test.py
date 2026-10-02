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
