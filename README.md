![logo](./logo.png)

# ansible-role-consul

Deploys a consul cluster as containers.

### Features / design decisions

- Deploys a consul cluster of servers and clients.
- Configures [dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) to
    resolve DNS queries for the consul domain (.consul) and and routes other
    DNS queries to public or pre-configured nameservers. Configurable in [defaults.yml](./defaults/main.yml).
- Resolves DNS queries on the host machine for .consul domains. Falls back to public DNS servers by default.
- Resolves DNS queries from within docker containers (specify `--dns=172.17.0.1`) See below.
- Deploys [registrator](https://github.com/gliderlabs/registrator) on every host to automatically register healthy Docker
    containers in consul.
- Disables systemd-resolved in favor of dnsmasq.
- Tested on a 5 node DigitalOcean cluster using Molecule and Testinfra.

#### Drawbacks
- The gossip communication between instances in unencrypted. The HTTP endpoints
    are unencrypted. This is only suitable for deployment within private
    networks.

### Usage

##### Deployment

The deployment requires the docker daemon to be installed on each host since
Consul runs as a container.

The role will deploy server agents to any node inside the `consul_server` group
and otherwise deploy a client to the remaining nodes. It is required that
you specify **at least 3 server nodes** for high availablilty.

Refer to the Consul [architecture docs](https://www.consul.io/docs/architecture) for a better overview.

```yaml
---
all:
  children:
    web:
      hosts:
        web01:
          ansible_host: 172.16.142.101
        web02:
          ansible_host: 172.16.142.102
    db:
      hosts:
        db01:
          ansible_host: 172.16.142.103
    cache:
      hosts:
        cache01:
          ansible_host: 172.16.142.104

    consul_server:
      hosts:
        web02:
        db01:
        cache01:
```

Using the playbook below we will deploy a Consul server instance to `web02`,
`db01`, `cache01`. Consul client will be deployed to the rest.

**You have to specify what IP range consul will be listening on** (most likely
your cloud private network). Consul will then find largest IP address listening
on that network range `ansible_all_ipv4_addresses | ipaddr(consul_network_range) | max`.

```yaml
---
- name: Deploy consul
  hosts: all
  tasks:
    - name: Deploy consul
      import_role:
        name: ansible-role-consul
      vars:
        consul_network_range: '172.16.142.0/24'
```

##### DNS resolution from within Docker containers

Specify the DNS server as the host IP when starting the container

```sh
docker run --dns 172.17.0.1 curlimages/curl "http://echo.service.consul:13000"
```

##### Automatic registration and health checks with registrator

In order for a container to be registered it needs to have **at least one
published port**.

Use docker labels to specify a service name and health checks.

```sh
docker run \
    -p 13000:5678 \
    -l SERVICE_NAME=echo \
    -l SERVICE_CHECK_HTTP=/ \
    -l SERVICE_CHECK_INTERVAL=10s \
    hashicorp/http-echo -text hello
```

The above service will then be available as

```sh
curl echo.service.consul:13000 -s
hello
```
