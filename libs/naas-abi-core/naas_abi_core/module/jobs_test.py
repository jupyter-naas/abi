import pytest
from naas_abi_core.module.jobs import Cron, JobDescriptor, job
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration


class _Module(BaseModule):
    class Configuration(ModuleConfiguration):
        pass

    jobs = (JobDescriptor("explicit"),)

    @job(triggers=(Cron("0 0 3 * * *", time_zone="Europe/Paris"),), max_attempts=3)
    def compact(self, ctx):
        """Compacts every dataset."""
        return "compacted"


def _instance():
    return object.__new__(_Module)


def test_engine_modules_declare_jobs_like_sdk_modules_and_may_be_sync():
    by_name = {j.name: j for j in _Module.jobs}

    assert set(by_name) == {"explicit", "compact"}
    assert by_name["compact"].description == "Compacts every dataset."
    assert by_name["compact"].max_attempts == 3
    assert _instance()._job_handlers["compact"](None) == "compacted"


def test_expose_job_accepts_sync_handlers_and_reports_missing_ones():
    module = _instance()
    assert module.missing_job_handlers() == {"explicit"}

    module.expose_job("explicit", lambda ctx: None)

    assert module.missing_job_handlers() == set()
    with pytest.raises(ValueError, match="already"):
        module.expose_job("explicit", lambda ctx: None)


def test_modules_without_jobs_declare_none():
    class _Plain(BaseModule):
        class Configuration(ModuleConfiguration):
            pass

    assert _Plain.jobs == ()
