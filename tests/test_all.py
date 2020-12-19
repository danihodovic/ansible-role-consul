import json
import re

import pytest


def test_containers_running(host):
    assert host.docker("consul")
    assert host.docker("registrator")


def test_resolves_dns_on_host(host):
    result = host.run("curl http://echo.service.consul:13000 -s")
    assert result.stdout == "hello\n"


def test_resolves_dns_within_container(host):
    result = host.run(
        (
            "docker run --dns 172.17.0.1 curlimages/curl "
            "http://echo.service.consul:13000"
        )
    )
    assert result.stdout == "hello\n"


def test_registers_health_checks(host):
    if host.backend.get_hostname() != "consul1":
        pytest.skip()

    result = host.run("curl echo.service.consul:8500/v1/health/checks/echo -s")
    health_checks = json.loads(result.stdout)
    assert len(health_checks) == 1
    health_check = health_checks[0]
    assert health_check["Status"] == "passing"


def test_cluster_health(host):
    if host.backend.get_hostname() != "consul1":
        pytest.skip()

    result = host.run("curl consul.service.consul:8500/v1/health/state/any -s")
    health_checks = json.loads(result.stdout)
    total = 0
    for check in health_checks:
        if check["CheckID"] != "serfHealth":
            continue
        assert check["Status"] == "passing"
        total += 1
    assert total == 5


def test_consul_metrics(host):
    result = host.run("curl localhost:9107/metrics")
    # pylint: disable=line-too-long
    matches = re.findall(
        r'consul_health_node_status{check="serfHealth",node=".*",status="passing"} 1',
        result.stdout,
    )
    assert len(matches) == 5


def test_consul_node_meta(host):
    if host.backend.get_hostname() != "consul1":
        pytest.skip()

    result = host.run("curl http://localhost:8500/v1/catalog/nodes -s")
    data = json.loads(result.stdout)
    slavens_node = next((v for v in data if v["Node"] == "slaven_bilic_big_sam"), None)
    assert slavens_node
    assert slavens_node["Datacenter"] == "my_dc"
    assert slavens_node["Meta"]["hello"] == "world"

    joses_node = next((v for v in data if v["Node"] == "jose_mourinho"), None)
    assert joses_node
    assert joses_node["Meta"]["denis"] == "supak"
