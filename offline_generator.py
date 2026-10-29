"""Bounded, deterministic lab generation without an API or language model."""

import ipaddress
import re

from lab_validation import require_valid_lab


def normalized_prompt(prompt):
    words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
             "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
    return re.sub(r"\b(" + "|".join(words) + r")\b", lambda m: words[m[0]], prompt.lower())


def explicit_counts(prompt):
    """Extract totals and per-switch counts from the supported prompt grammar."""
    p = normalized_prompt(prompt)
    result = {}
    patterns = {"router": r"routers?", "switch": r"switch(?:es)?",
                "pc": r"(?:pcs?|hosts?|computers?|workstations?|nodes?)"}
    for kind, noun in patterns.items():
        match = re.search(r"\b(\d+)\s*" + noun + r"\b", p)
        if match:
            result[kind] = int(match[1])
        elif kind != "pc" and re.search(r"\b(?:a|an|the)\s+" + noun + r"\b", p):
            result[kind] = 1
    if "switch" not in result and re.search(r"\b(?:each switch|per switch|both switches)\b", p):
        result["switch"] = 2
    per = re.search(r"\b(\d+)\s*(?:pcs?|hosts?|computers?|workstations?)\s*(?:on\s+|per\s+|at\s+)?(?:each(?:\s+switch)?|every switch|per switch)\b", p)
    per = per or re.search(r"\b(\d+)\s*(?:at|per|on)\s*(?:each\s+)?switch\b", p)
    if per:
        per_count = int(per[1])
        # In '2 PCs each', 2 describes the per-switch count, not the total.
        pc_match = re.search(r"\b(\d+)\s*(?:pcs?|hosts?|computers?|workstations?|nodes?)\b", p)
        if pc_match and pc_match.start() == per.start():
            result.pop("pc", None)
        result["per_switch"] = per_count
        if "switch" in result:
            total = per_count * result["switch"]
            if "pc" in result and result["pc"] != total:
                raise ValueError("Total PC count conflicts with the requested PCs per switch.")
            result["pc"] = total
    return result


def requested_subnets(prompt):
    nets = []
    for text in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/[+-]?\d+)?\b", prompt):
        try:
            net = ipaddress.IPv4Network(text if "/" in text else text + "/24", strict=False)
        except ValueError as exc:
            raise ValueError(f"Invalid requested IPv4 network: {text}.") from exc
        if net not in nets:
            nets.append(net)
    return nets


def requested_vlans(prompt):
    groups = re.findall(r"\bvlans?\s+(\d+(?:\s*(?:,|and)\s*\d+)*)", prompt.lower())
    return list(dict.fromkeys(int(n) for group in groups for n in re.findall(r"\d+", group)))


def check_prompt_requirements(lab, prompt):
    """Check explicit counts and networks even when a model produced the lab."""
    for kind, requested in explicit_counts(prompt).items():
        if kind == "per_switch":
            for switch in (d["id"] for d in lab["devices"] if d["type"] == "switch"):
                pc_ids = {d["id"] for d in lab["devices"] if d["type"] == "pc"}
                count = sum((l["from"] == switch and l["to"] in pc_ids) or
                            (l["to"] == switch and l["from"] in pc_ids) for l in lab["links"])
                if count != requested:
                    raise ValueError(f"'{switch}' does not have the requested {requested} PCs.")
        elif sum(d["type"] == kind for d in lab["devices"]) != requested:
            raise ValueError(f"Lab does not contain the requested {requested} {kind} devices.")
    actual = {ipaddress.IPv4Network(f"{a['ip']}/{a['mask']}", strict=False) for a in lab["addressing"]}
    for net in requested_subnets(prompt):
        if net not in actual:
            raise ValueError(f"Lab does not use the requested network {net}.")
    p = normalized_prompt(prompt)
    if re.search(r"\bvlans?\b", p):
        if lab["lab_type"] != "vlan":
            raise ValueError("The request requires VLAN segmentation.")
        for vid in requested_vlans(p):
            if not any(re.search(r"(?m)^\s*vlan\s+" + str(vid) + r"\s*$", c) for c in lab["configurations"].values()):
                raise ValueError(f"The lab does not create requested VLAN {vid}.")
    if "ring" in p:
        switches = {d["id"] for d in lab["devices"] if d["type"] == "switch"}
        edges = [l for l in lab["links"] if l["from"] in switches and l["to"] in switches]
        if len(switches) < 3 or any(sum(name in (l["from"], l["to"]) for l in edges) != 2 for name in switches):
            raise ValueError("The lab does not contain the requested switch ring.")


def build_offline_lab(prompt, category="custom"):
    p = normalized_prompt(prompt)
    if re.search(r"-\s*\d+\s*(?:pcs?|routers?|switch(?:es)?|hosts?)\b", p):
        raise ValueError("Device counts must not be negative.")
    unsupported = re.search(r"\b(ospf|bgp|eigrp|rip|dhcp|dns|nat|acl|ipv6|wireless|wifi|firewalls?|mesh|trunk|inter-vlan|servers?|hubs?|serial|vpn)\b", p)
    if unsupported:
        raise ValueError(f"Offline generation does not support '{unsupported[0]}'. Use Gemini or a simpler prompt.")
    if not re.search(r"\b(router|routers|switch|switches|pc|pcs|hosts?|computers?|workstations?|lan|vlan|routing|subnet|network)\b", p):
        raise ValueError("Describe a LAN, VLAN, or static-routing lab with device counts and optional IPv4 subnets.")
    counts = explicit_counts(prompt)
    vlan = category == "vlan" or bool(re.search(r"\bvlans?\b", p))
    nr = counts.get("router", 2 if category == "static_routing" or "static routing" in p else 0)
    if "router" not in counts and not nr and re.search(r"\brout(?:ed|ing)\b", p):
        nr = 1
    subnets = requested_subnets(prompt)
    ns = counts.get("switch", max(2, len(subnets)) if nr else 1)
    np = counts.get("pc", counts.get("per_switch", 2) * ns)
    if not 1 <= ns <= 8 or not 1 <= np <= 192 or nr < 0:
        raise ValueError("Offline limits: 1–8 switches and 1–192 PCs, with at most 24 PCs per switch.")
    if nr > 2 or (nr == 2 and ns != 2) or (nr == 1 and ns > 3):
        raise ValueError("Offline routing supports one router with 1–3 switches, or two routers with exactly two switches.")
    if vlan and (nr or ns != 1):
        raise ValueError("Offline VLAN labs support one switch without routers; inter-VLAN routing requires Gemini.")
    if nr and re.search(r"\b(ring|chain|star)\b", p):
        raise ValueError("Explicit ring, chain, and star shapes are supported offline for switch-only LANs.")
    if not nr and ns > 2 and re.search(r"\bstar\b", p):
        raise ValueError("Offline multi-switch LANs support chains or rings; star layouts require Gemini.")

    vlan_ids = requested_vlans(p) if vlan else []
    if vlan:
        vlan_count = re.search(r"\b(\d+)\s+vlans\b", p)
        if vlan_count and int(vlan_count[1]) != 2:
            raise ValueError("Offline VLAN generation supports exactly two VLANs.")
        vlan_ids = vlan_ids or [10, 20]
        if len(vlan_ids) != 2 or any(v < 2 or v > 1001 for v in vlan_ids):
            raise ValueError("Offline VLAN generation supports exactly two distinct VLAN IDs in the range 2–1001.")
        if np < 2:
            raise ValueError("A two-VLAN lab needs at least two PCs.")

    subnet_count = 2 if vlan else ns if nr else 1
    if len(subnets) > subnet_count:
        raise ValueError(f"This offline topology uses {subnet_count} LAN subnet(s); too many networks were supplied.")
    if not subnets:
        subnets = ([ipaddress.IPv4Network("192.168.10.0/24"), ipaddress.IPv4Network("192.168.20.0/24")]
                   if vlan else [ipaddress.IPv4Network("192.168.1.0/24")])
    while len(subnets) < subnet_count:
        candidate = int(subnets[-1].broadcast_address) + 1
        try:
            subnets.append(ipaddress.IPv4Network((candidate, subnets[-1].prefixlen)))
        except ValueError as exc:
            raise ValueError("Cannot allocate another subnet; specify all LAN subnets explicitly.") from exc
    if any(a.overlaps(b) for i, a in enumerate(subnets) for b in subnets[i + 1:]):
        raise ValueError("LAN subnets must not overlap.")
    if any(net.prefixlen >= 31 for net in subnets):
        raise ValueError("LAN subnets must be /30 or larger and have room for every host and gateway.")

    distribution = [np // ns + (s < np % ns) for s in range(ns)]
    if max(distribution) > 24:
        raise ValueError("A 2960 supports at most 24 PC access ports per switch.")
    group_sizes = [(np + 1) // 2, np // 2] if vlan else distribution if nr else [np]
    allocations = []
    for net, size in zip(subnets, group_sizes):
        needed = size + bool(nr)
        if needed > net.num_addresses - 2:
            raise ValueError(f"Subnet {net} has {net.num_addresses - 2} usable addresses but needs {needed}.")
        # Arithmetic avoids materializing a /8 or /0 host list.
        allocations.append(iter(ipaddress.IPv4Address(n) for n in
                                range(int(net.network_address) + 1, int(net.network_address) + needed + 1)))

    devices, links, addressing, configs = [], [], [], {}
    for kind, number, prefix, model in (("router", nr, "R", "2911"), ("switch", ns, "SW", "2960")):
        for i in range(number):
            name = f"{prefix}{i + 1}"
            devices.append({"id": name, "type": kind, "model": model})
            configs[name] = f"enable\nconfigure terminal\nhostname {name}\n"

    def address(name, port, ip, net, gateway=""):
        addressing.append({"device": name, "interface": port, "ip": str(ip),
                           "mask": str(net.netmask), "gateway": str(gateway)})

    def router_port(name, port, ip, net):
        address(name, port, ip, net)
        configs[name] += f"interface {port}\n ip address {ip} {net.netmask}\n no shutdown\nexit\n"

    for vid in vlan_ids:
        configs["SW1"] += f"vlan {vid}\n name LAB_{vid}\nexit\n"
    pc_index = 0
    gateways = [next(allocations[s]) for s in range(ns)] if nr else []
    for s, size in enumerate(distribution):
        switch = f"SW{s + 1}"
        if nr:
            router = "R1" if nr == 1 else f"R{s + 1}"
            port = f"GigabitEthernet0/{s}" if nr == 1 else "GigabitEthernet0/0"
            links.append({"from": switch, "from_port": "GigabitEthernet0/1", "to": router, "to_port": port})
            router_port(router, port, gateways[s], subnets[s])
        for local in range(size):
            name = f"PC{pc_index + 1}"
            group = pc_index % 2 if vlan else s if nr else 0
            devices.append({"id": name, "type": "pc", "model": "Generic PC"})
            links.append({"from": name, "from_port": "FastEthernet0", "to": switch, "to_port": f"FastEthernet0/{local + 1}"})
            address(name, "FastEthernet0", next(allocations[group]), subnets[group], gateways[s] if nr else "")
            if vlan:
                configs[switch] += f"interface FastEthernet0/{local + 1}\n switchport mode access\n switchport access vlan {vlan_ids[group]}\n no shutdown\nexit\n"
            pc_index += 1
    if not nr and ns > 1:
        for s in range(ns - 1):
            links.append({"from": f"SW{s + 1}", "from_port": "GigabitEthernet0/2",
                          "to": f"SW{s + 2}", "to_port": "GigabitEthernet0/1"})
        if "ring" in p:
            if ns < 3:
                raise ValueError("A switch ring needs at least three switches.")
            links.append({"from": f"SW{ns}", "from_port": "GigabitEthernet0/2", "to": "SW1", "to_port": "GigabitEthernet0/1"})
    if nr == 2:
        # Select a WAN /30 outside all LAN ranges, including user-supplied /8s.
        wan = None
        for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"):
            candidate = ipaddress.IPv4Network(block)
            if not any(candidate.overlaps(net) for net in subnets):
                wan = next(candidate.subnets(new_prefix=30))
                break
        if wan is None:
            raise ValueError("No private WAN range is available outside the requested LANs.")
        left, right = wan.network_address + 1, wan.network_address + 2
        links.append({"from": "R1", "from_port": "GigabitEthernet0/1", "to": "R2", "to_port": "GigabitEthernet0/1"})
        router_port("R1", "GigabitEthernet0/1", left, wan)
        router_port("R2", "GigabitEthernet0/1", right, wan)
        configs["R1"] += f"ip route {subnets[1].network_address} {subnets[1].netmask} {right}\n"
        configs["R2"] += f"ip route {subnets[0].network_address} {subnets[0].netmask} {left}\n"
    for name in configs:
        configs[name] += "end\nwrite memory"

    verification = ["On switches, run 'show mac address-table' after generating traffic."]
    pcs = [a for a in addressing if a["device"].startswith("PC")]
    if vlan:
        verification.append(f"On SW1, run 'show vlan brief'; check VLANs {vlan_ids[0]} and {vlan_ids[1]} and their access ports.")
        verification.append(f"From PC1, ping {pcs[1]['ip']} (PC2). Expected: failure; the two VLANs are isolated.")
        if np >= 3:
            verification.append(f"From PC1, ping {pcs[2]['ip']} (PC3). Expected: success within VLAN {vlan_ids[0]} after ARP learning.")
    else:
        if nr:
            verification.append(f"From PC1, ping {pcs[0]['gateway']}. Expected: gateway responds after ARP learning.")
            verification.append("On each router, run 'show ip interface brief' and 'show ip route'; check active interfaces and required routes.")
        if np > 1:
            verification.append(f"From PC1, ping {pcs[-1]['ip']} ({pcs[-1]['device']}). Expected: success after ARP/STP convergence.")
    lab = {
        "title": f"{'VLAN' if vlan else 'Routed' if nr else 'LAN'} Lab ({np} PCs, {ns} Switches, {nr} Routers)",
        "lab_type": "vlan" if vlan else "static_routing" if nr else "basic_lan",
        "objective": "Configure and test " + ("isolated VLANs" if vlan else "IPv4 connectivity") + " on " + ", ".join(map(str, subnets)) + ".",
        "devices": devices, "links": links, "addressing": addressing, "configurations": configs,
        "instructions": ["Open the exported topology in Packet Tracer, or build it using the cabling table.",
                         "Check PC addressing and apply the supplied Cisco CLI configurations as needed.",
                         "Wait for STP and ARP learning, then run the verification checklist. A ring intentionally has an STP-blocked path."],
        "verification": verification, "generation": {"source": "offline"},
    }
    require_valid_lab(lab)
    check_prompt_requirements(lab, prompt)
    return lab
