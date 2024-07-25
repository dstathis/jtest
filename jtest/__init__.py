import json
import logging
import pytest
import random
import string
import subprocess
import time


class JujuStatus:
    def __init__(self):
        status = json.loads(run("juju status --format json").stdout)
        self._model = status["model"]
        self._machines = status["machines"]
        self._apps = status["applications"]
        self._storage = status["storage"]
        self._controller = status["controller"]

    def apps(self):
        return [app for app in self._apps]

    def unit_objects(self, app_name):
        app = self._apps[app_name]
        if not "subordinate-to" in app:
            return app["units"].values()
        unit_objects = []
        principals = app["subordinate-to"]
        for principal in principals:
            units = self._apps[principal]["units"]
            for unit in units:
                if "subordinates" in units[unit]:
                    for sub in units[unit]["subordinates"]:
                        if sub.startswith(app_name):
                            unit_objects.append(units[unit]["subordinates"][sub])
        return unit_objects


def run(cmd):
    logging.debug(f"running command: {cmd}")
    p = subprocess.run(cmd.split(), capture_output=True)
    if p.returncode != 0:
        raise Exception(f"Command failed: {cmd}")
    return p


def random_model_name():
    return f'jtest-{"".join(random.choices(string.ascii_lowercase, k=10))}'


@pytest.fixture(scope="session")
def controllers():
    """Find and return a machine and k8s cloud. If there is more than one cloud of a given type,
    pick an arbitrary cloud to return."""

    ret = {"machine": None, "k8s": None}
    controllers = json.loads(run("juju controllers --format json").stdout)["controllers"]
    clouds = json.loads(run("juju clouds --format json").stdout)
    for controller in controllers:
        cloud = controllers[controller]["cloud"]
        if clouds[cloud]["type"] == "k8s":
            ret["k8s"] = controller
        else:
            ret["machine"] = controller
        if ret["machine"] is not None and ret["k8s"] is not None:
            break
    return ret


@pytest.fixture(scope="session")
def machine_model(controllers):
    model_name = random_model_name()
    run(f"juju switch {controllers['machine']}")
    run(f"juju add-model {model_name}")
    yield model_name
    run(f"juju destroy-model --no-prompt --destroy-storage --force --no-wait {controllers['machine']}:{model_name}")


@pytest.fixture(scope="session")
def k8s_model(controllers):
    model_name = random_model_name()
    run(f"juju switch {controllers['k8s']}")
    run(f"juju add-model {model_name}")
    yield model_name
    run(f"juju destroy-model --no-prompt --destroy-storage --force --no-wait {controllers['k8s']}:{model_name}")


def wait_for_idle(app_name, status=None, timeout=300, prewait=0, wait_for_units=0):
    """Wait for all units of the application to be idle.

    Args:
        app_name: Name of the application.
        status: If provided, also wait for this status.
        timeout: Timeout in seconds.
        prewait: Wait this many seconds before checking anything.
        wait_for_units: Wait for at least this many units to exist.
    """
    time.sleep(prewait)
    start_time = time.time()
    logging.debug(f"Starting wait_for_idle at time: {start_time}")
    while time.time() < start_time + timeout:
        js = JujuStatus()
        numunits = len(js.unit_objects(app_name))
        logging.debug(f"number of units of app {app_name}: {numunits}")
        if numunits >= wait_for_units:
            for unit in js.unit_objects(app_name):
                unit_good = False
                workload_good = True if not status else False
                logging.debug(f"agent status: {unit['juju-status']['current']}")
                if unit["juju-status"]["current"] == "idle":
                    unit_good = True
                logging.debug(f"workload status: {unit['workload-status']['current']}")
                if unit["workload-status"]["current"] == status:
                    workload_good = True
                if not (unit_good and workload_good):
                    break
            else:
                return
        time.sleep(10)
    logging.debug(f"wait_for_idle timeout at time: {time.time()}")
    raise Exception("Timeout reached waiting for idle.")
