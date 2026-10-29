"""Structural and network checks shared by generators, the UI, and exports.

These checks establish blueprint consistency, not Packet Tracer simulation results.
"""

import ipaddress
import re


MODELS = {"router": {"2911"}, "switch": {"2960", "2960-24TT"},
          "pc": {"Generic PC", "Generic", "PC-PT"}}
PORTS = {
    "router": {f"GigabitEthernet0/{n}" for n in range(3)},
    "switch": ({f"FastEthernet0/{n}" for n in range(1, 25)} |
               {"GigabitEthernet0/1", "GigabitEthernet0/2"}),
    "pc": {"FastEthernet0"},
}


def validate_lab_data(data):
    """Return (valid, errors), including for malformed or untrusted JSON values."""
    errors = []
    if not isinstance(data, dict):
        return False, ["Lab must be a JSON object."]
    for key in ("title", "lab_type", "objective"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"'{key}' must be a non-empty string.")
    for key in ("devices", "links", "addressing", "instructions", "verification"):
        if not isinstance(data.get(key), list) or not data[key]:
            errors.append(f"'{key}' must be a non-empty list.")
    if not isinstance(data.get("configurations"), dict):
        errors.append("Configurations must map device IDs to CLI strings.")
    if errors:
        return False, errors
    generation = data.get("generation")
    if "generation" in data:
        if not isinstance(generation, dict) or any(not isinstance(v, str) for v in generation.values()):
            errors.append("Generation metadata must be an object with string values.")
    if data["lab_type"] not in {"basic_lan", "vlan", "static_routing", "custom"}:
        errors.append("Unsupported lab_type.")
    for key in ("instructions", "verification"):
        if any(not isinstance(s, str) or not s.strip() for s in data[key]):
            errors.append(f"Every '{key}' item must be a non-empty string.")

    devices = {}
    for device in data["devices"]:
        if not isinstance(device, dict):
            errors.append("Each device must be an object.")
            continue
        name, kind, model = (device.get(k) for k in ("id", "type", "model"))
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,62}", name):
            errors.append("Device IDs must start with a letter and contain only letters, digits, '_' or '-'.")
            continue
        if name in devices:
            errors.append(f"Duplicate device ID: '{name}'.")
        if not isinstance(kind, str) or kind not in MODELS:
            errors.append(f"Unsupported device type for '{name}'.")
            continue
        if not isinstance(model, str) or model not in MODELS[kind]:
            errors.append(f"Unsupported model for '{name}': {model!r}.")
        devices[name] = kind

    adjacency = {name: set() for name in devices}
    endpoints = set()
    for link in data["links"]:
        if not isinstance(link, dict):
            errors.append("Each link must be an object.")
            continue
        a, b = link.get("from"), link.get("to")
        for name, port in ((a, link.get("from_port")), (b, link.get("to_port"))):
            if not isinstance(name, str) or name not in devices:
                errors.append(f"Link references unknown device: {name!r}.")
                continue
            if not isinstance(port, str) or port not in PORTS[devices[name]]:
                errors.append(f"Invalid physical port on '{name}': {port!r}. Use its full interface name.")
                continue
            endpoint = (name, port)
            if endpoint in endpoints:
                errors.append(f"Port collision: '{name}:{port}' is wired more than once.")
            endpoints.add(endpoint)
        if isinstance(a, str) and isinstance(b, str) and a in devices and b in devices:
            if a == b:
                errors.append(f"Self-link on '{a}'.")
            adjacency[a].add(b)
            adjacency[b].add(a)
    if devices:
        seen, pending = set(), [next(iter(devices))]
        while pending:
            name = pending.pop()
            if name not in seen:
                seen.add(name)
                pending.extend(adjacency[name] - seen)
        if seen != set(devices):
            errors.append("Physical topology is disconnected: " + ", ".join(sorted(set(devices) - seen)))

    addresses, ips, networks = {}, set(), {}
    for entry in data["addressing"]:
        if not isinstance(entry, dict):
            errors.append("Each addressing entry must be an object.")
            continue
        name, port, ip, mask = (entry.get(k) for k in ("device", "interface", "ip", "mask"))
        gateway = entry.get("gateway", "")
        if not all(isinstance(v, str) for v in (name, port, ip, mask, gateway)):
            errors.append("Addressing fields must be strings; use an empty string for no gateway.")
            continue
        if name not in devices:
            errors.append(f"Addressing references unknown device: '{name}'.")
            continue
        svi = devices[name] == "switch" and re.fullmatch(r"Vlan([1-9]\d{0,3})", port)
        if port not in PORTS[devices[name]] and not (svi and 1 <= int(svi[1]) <= 4094):
            errors.append(f"Invalid addressed interface: '{name}:{port}'.")
        elif not svi and (name, port) not in endpoints:
            errors.append(f"Address assigned to unwired interface: '{name}:{port}'.")
        if (name, port) in addresses:
            errors.append(f"Duplicate addressing entry: '{name}:{port}'.")
        try:
            if not ip or not mask:
                raise ValueError("IP and mask are required")
            host = ipaddress.IPv4Interface(f"{ip}/{mask}")
            if host.network.prefixlen >= 31 or host.ip in (host.network.network_address, host.network.broadcast_address):
                raise ValueError("Use a usable host address on a /30 or larger subnet")
            if host.ip.is_multicast or host.ip.is_unspecified or host.ip.is_loopback:
                raise ValueError("Not a supported unicast host address")
            if host.ip in ips:
                errors.append(f"Duplicate IP assignment: '{host.ip}'.")
            ips.add(host.ip)
            addresses[name, port] = (host, gateway)
            networks.setdefault(name, set()).add(host.network)
            if gateway:
                gw = ipaddress.IPv4Address(gateway)
                if gw not in host.network or gw in (host.ip, host.network.network_address, host.network.broadcast_address):
                    errors.append(f"Invalid default gateway '{gateway}' for '{name}' on {host.network}.")
        except ValueError as exc:
            errors.append(f"Invalid addressing for '{name}': {exc}.")

    configs = data["configurations"]
    for name, config in configs.items():
        if name not in devices or devices.get(name) == "pc":
            errors.append(f"CLI configuration references unsupported device: '{name}'.")
        if not isinstance(config, str) or not config.strip():
            errors.append(f"CLI configuration for '{name}' must be a non-empty string.")
    router_addresses = {str(host.ip): name for (name, _), (host, _) in addresses.items()
                        if devices[name] == "router"}
    for name, kind in devices.items():
        if kind == "pc" and (name, "FastEthernet0") not in addresses:
            errors.append(f"Missing host addressing for '{name}'.")
        if kind in {"router", "switch"} and not configs.get(name):
            errors.append(f"Missing CLI configuration for '{name}'.")
        if kind == "router":
            for endpoint in endpoints:
                if endpoint[0] == name and endpoint not in addresses:
                    errors.append(f"Missing router interface addressing: '{name}:{endpoint[1]}'.")
    for (name, port), (host, gateway) in addresses.items():
        if devices[name] == "pc" and data["lab_type"] == "static_routing" and not gateway:
            errors.append(f"Routed host '{name}' needs a default gateway.")
        if gateway and gateway not in router_addresses:
            errors.append(f"Gateway '{gateway}' for '{name}' is not assigned to a router.")
        if devices[name] in {"router", "switch"} and isinstance(configs.get(name), str):
            blocks = re.split(r"(?im)^\s*interface\s+", configs[name])
            matching = [b for b in blocks[1:] if b.splitlines()[0].strip().lower() == port.lower()]
            expected = f"ip address {host.ip} {host.netmask}"
            if not matching or not re.search(r"(?m)^\s*" + re.escape(expected) + r"\s*$", matching[0].lower()):
                errors.append(f"CLI/addressing mismatch for '{name}:{port}'.")
            elif devices[name] == "router" and not re.search(r"(?m)^\s*no shutdown\s*$", matching[0]):
                errors.append(f"Router interface '{name}:{port}' needs 'no shutdown'.")

    # Ethernet links between routers must share a subnet. LAN ports on a router
    # must not overlap; switches may carry several VLAN subnets on one cable.
    for name, kind in devices.items():
        if kind == "router":
            nets = [host.network for (dev, _), (host, _) in addresses.items() if dev == name]
            if any(a.overlaps(b) for i, a in enumerate(nets) for b in nets[i + 1:]):
                errors.append(f"Overlapping interface subnets on '{name}'.")
    for link in data["links"]:
        if not isinstance(link, dict):
            continue
        a, b = link.get("from"), link.get("to")
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        if devices.get(a) == devices.get(b) == "router":
            pa, pb = link.get("from_port"), link.get("to_port")
            if not isinstance(pa, str) or not isinstance(pb, str):
                continue
            left, right = addresses.get((a, pa)), addresses.get((b, pb))
            if not left or not right or left[0].network != right[0].network:
                errors.append(f"Router link '{a}' to '{b}' needs addresses in the same subnet.")

    if data["lab_type"] == "static_routing":
        host_nets = {host.network for (name, _), (host, _) in addresses.items() if devices[name] == "pc"}
        for name, kind in devices.items():
            if kind != "router" or not isinstance(configs.get(name), str):
                continue
            routes = []
            for target, mask, hop in re.findall(r"(?im)^\s*ip route\s+(\S+)\s+(\S+)\s+(\S+)", configs[name]):
                try:
                    target_net = ipaddress.IPv4Network(f"{target}/{mask}")
                    next_hop = ipaddress.IPv4Address(hop)
                    peer = router_addresses.get(str(next_hop))
                    if peer == name or peer not in adjacency[name] or not any(next_hop in net for net in networks.get(name, set())):
                        errors.append(f"Static route on '{name}' has an unreachable next hop: '{hop}'.")
                    routes.append(target_net)
                except ValueError:
                    errors.append(f"Invalid static route on '{name}'.")
            for remote in host_nets - networks.get(name, set()):
                if not any(remote.subnet_of(route) for route in routes):
                    errors.append(f"Missing static route on '{name}' for remote LAN {remote}.")

    if data["lab_type"] == "vlan":
        vlan_ids, access_ids = set(), set()
        for name, kind in devices.items():
            if kind != "switch" or not isinstance(configs.get(name), str):
                continue
            declared = set(re.findall(r"(?im)^\s*vlan\s+(\d+)\s*$", configs[name]))
            access = set(re.findall(r"(?im)^\s*switchport access vlan\s+(\d+)\s*$", configs[name]))
            if not access.issubset(declared | {"1"}):
                errors.append(f"Access ports on '{name}' reference VLANs that are not created.")
            vlan_ids.update(declared)
            access_ids.update(access)
        if len(vlan_ids) < 2 or len(access_ids) < 2:
            errors.append("A VLAN segmentation lab needs at least two created VLANs and access-port assignments.")
    return not errors, errors


def require_valid_lab(data):
    """Reject inconsistent data before it becomes the current lab or an export."""
    valid, errors = validate_lab_data(data)
    if not valid:
        raise ValueError("Lab validation failed:\n" + "\n".join(errors))
    return data
