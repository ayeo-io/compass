"""Start-up for the acceptance suite: the system, the driver factory and one DSL per scenario.

The driver is chosen once, when the run starts: `--driver api|cli`, or
`ACCEPTANCE_DRIVER` when the option is not given, or `api`. The `driver`
fixture imports the chosen driver's module. The import is inside the
fixture, not at the top of this file, on purpose: while a driver does not
exist yet, each scenario is an error at setup and pytest still writes its
report, where an import here would stop collection with exit 4 and no
report.

When the run starts, before any worker, this file makes the run id the
alias helper reads (ACCEPTANCE_RUN_ID), and picks the store every worker of
the run shares: `TODO_DATA_DIR` when it is set, so several runs can share one
store, or else a new folder, made once for the run. Nothing is cleared after
a scenario.
"""
from __future__ import annotations

import importlib
import os
import tempfile
import uuid

import pytest

from tests.acceptance.drivers import DRIVERS
from tests.acceptance.dsl import Dsl
from tests.acceptance.system import RunningSystem


def pytest_addoption(parser):
    parser.addoption("--driver", default=None,
                     help=f"the driver the specifications run through: {', '.join(DRIVERS)} "
                          "(default: $ACCEPTANCE_DRIVER, else api)")


def _chosen(config):
    return config.getoption("--driver") or os.environ.get("ACCEPTANCE_DRIVER") or "api"


def pytest_configure(config):
    name = _chosen(config)
    if name not in DRIVERS:
        raise pytest.UsageError(f"no driver {name!r}: choose one of {', '.join(DRIVERS)}")
    # An xdist worker has `workerinput`; it inherits what the run set here.
    if not hasattr(config, "workerinput"):
        os.environ["ACCEPTANCE_RUN_ID"] = uuid.uuid4().hex[:8]
        if not os.environ.get("TODO_DATA_DIR"):
            os.environ["TODO_DATA_DIR"] = tempfile.mkdtemp(prefix="todo-data-")


def pytest_report_header(config):
    return [f"acceptance driver: {_chosen(config)}",
            f"todo store: {os.environ['TODO_DATA_DIR']}"]


@pytest.fixture(scope="session")
def system():
    running = RunningSystem(os.environ["TODO_DATA_DIR"])
    yield running
    running.stop()


@pytest.fixture
def driver(request, system):
    module = importlib.import_module(f"tests.acceptance.drivers.{_chosen(request.config)}")
    return module.Driver(system)


@pytest.fixture
def dsl(driver):
    return Dsl(driver)
