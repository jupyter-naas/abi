import io
import os

from naas_abi_core.utils import Logger


def test_reconfigure_leaves_variables_out_of_tracebacks(monkeypatch):
    err = io.StringIO()
    monkeypatch.setattr(Logger.sys, "stderr", err)
    Logger.reconfigure("INFO")
    try:
        prompt = "a confidential prompt"
        try:
            raise ValueError(len(prompt))
        except ValueError:
            Logger.logger.exception("the call failed")
    finally:
        monkeypatch.undo()
        Logger.reconfigure(os.environ.get("LOG_LEVEL", "WARNING"))

    assert "the call failed" in err.getvalue()
    assert "ValueError" in err.getvalue()
    assert "confidential" not in err.getvalue()
