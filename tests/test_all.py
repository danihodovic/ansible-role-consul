# pylint: disable=invalid-name,redefined-outer-name
import json
import re

import pytest
import requests
from testinfra.host import Host


@pytest.fixture(scope="session")
def target_host(request):
    def fn(host, sudo=True):
        return Host.get_host(
            f"ansible://{host}?ansible_inventory={request.config.option.ansible_inventory}",
            sudo=sudo,
        )

    return fn


def test_containers_running(host):
    with host.sudo():
        assert host.docker("consul").is_running


def test_resolves_dns_on_host(host):
    url = "http://echo.service.consul:13000"
    res = host.ansible("uri", f"url={url} return_content=true", check=False)
    assert res["content"] == "hello\n"


def test_resolves_dns_within_container(host):
    with host.sudo():
        result = host.run(
            (
                "docker run --net=container:consul curlimages/curl "
                "http://echo.service.consul:13000"
            )
        )
        assert result.stdout == "hello\n"


def test_cluster_health(host):
    if host.backend.get_hostname() != "consul1":
        pytest.skip()

    url = "http://consul.service.consul:8500/v1/health/state/any"
    res = host.ansible("uri", f"url={url} return_content=true", check=False)

    total = 0
    for check in res["json"]:
        if check["CheckID"] != "serfHealth":
            continue
        assert check["Status"] == "passing"
        total += 1
    assert total == 5


def test_consul_metrics(host):
    res = host.ansible(
        "uri", "url=http://localhost:9107/metrics return_content=true", check=False
    )
    # pylint: disable=line-too-long
    matches = re.findall(
        r'consul_health_node_status{check="serfHealth",node=".*",status="passing"} 1',
        res["content"],
    )
    assert len(matches) == 5


def test_consul_node_meta(target_host):
    host = target_host("consul1")
    url = "http://localhost:8500/v1/catalog/nodes"
    res = host.ansible("uri", f"url={url} return_content=true", check=False)
    data = res["json"]

    slavens_node = next((v for v in data if v["Node"] == "slaven_bilic_big_sam"), None)
    assert slavens_node
    assert slavens_node["Datacenter"] == "my_dc"
    assert slavens_node["Meta"]["hello"] == "world"

    joses_node = next((v for v in data if v["Node"] == "jose_mourinho"), None)
    assert joses_node
    assert joses_node["Meta"]["denis"] == "supak"


def test_consul_web(host):
    url = "http://consul-web.service.consul"
    host.ansible("uri", f"url={url} return_content=true", check=False)


def test_not_internet_reachable(target_host):
    host = target_host("consul1")
    ipify_facts = host.ansible("community.general.ipify_facts")
    public_ip = ipify_facts["ansible_facts"]["ipify_public_ip"]
    with pytest.raises(requests.exceptions.ConnectTimeout):
        requests.get(f"http://{public_ip}:8500/v1/agent/members", timeout=10)
