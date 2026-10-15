"""The offline examples run as written, so they cannot drift from the public API."""

import runpy
from pathlib import Path

import pytest

from llmwarden.observe.memory import default_sink

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(autouse=True)
def _clean():
    default_sink.clear()
    yield
    default_sink.clear()


def test_cost_report_example_runs(capsys):
    runpy.run_path(str(EXAMPLES / "05_cost_report.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "acme" in out and "globex" in out and "planner" in out and "writer" in out
    assert "demo-key" not in out


def test_testing_your_app_example_runs(capsys):
    runpy.run_path(str(EXAMPLES / "06_testing_your_app.py"), run_name="__main__")
    assert "both tests passed" in capsys.readouterr().out


def test_hosted_app_example_refuses_localhost(capsys):
    runpy.run_path(str(EXAMPLES / "04_hosted_app_custom_endpoint.py"), run_name="__main__")
    assert "cannot be used here" in capsys.readouterr().out
