from jtest import wait_for_idle
import logging
import subprocess


def run(cmd):
    logging.debug(f"running command: {cmd}")
    p = subprocess.run(cmd.split())
    if p.returncode != 0:
        raise Exception(f"Command failed: {cmd}")


def test_deploy_prom(k8s_model):
    run(f"juju switch {k8s_model}")
    run("juju deploy prometheus-k8s prometheus")
    wait_for_idle("prometheus", status="active")


def test_deploy_agent(machine_model):
    run(f"juju switch {machine_model}")
    run("juju deploy grafana-agent")
    run("juju deploy zookeeper")
    run("juju relate zookeeper grafana-agent")
    wait_for_idle("grafana-agent", status="blocked", timeout=600, wait_for_units=1)


def test_relate(controllers, k8s_model, machine_model):
    run(f"juju switch {controllers['k8s']}:{k8s_model}")
    run("juju offer prometheus:receive-remote-write prometheus")
    run(f"juju switch {controllers['machine']}:{machine_model}")
    run(f"juju consume {controllers['k8s']}:{k8s_model}.prometheus")
    run("juju relate grafana-agent prometheus")
    wait_for_idle("grafana-agent", status="active")
