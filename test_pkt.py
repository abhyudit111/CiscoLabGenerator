"""Quick test suite for the Cisco Packet Tracer .pkt generator."""

import json
import sys
from pathlib import Path

PROJ_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJ_DIR))

import ai_generator
import diagram
import pkt_generator

print("=== Testing Cisco Packet Tracer .pkt Generator ===")

labs = [
    ("basic_lan", "basic_lan"),
    ("vlan_lab", "vlan"),
    ("routing_lab", "static_routing"),
]

for lab_name, lab_key in labs:
    lab = ai_generator.load_sample_lab(lab_key)

    # 1. Schema and network logic validation
    valid, errors = ai_generator.validate_lab_data(lab)
    assert valid, f"Validation failed for {lab_name}: {errors}"

    # 2. PKT byte generation
    pkt_bytes = pkt_generator.generate_pkt_bytes(lab)
    assert len(pkt_bytes) > 20000, f"PKT size unexpectedly small ({len(pkt_bytes)} bytes)"

    # 3. Round-trip decoding & tag verification
    xml = pkt_generator.decode_pkt_bytes(pkt_bytes)
    assert "PACKETTRACER5" in xml, "Missing PACKETTRACER5 root tag"
    assert "PHYSICALWORKSPACE" in xml, "Missing PHYSICALWORKSPACE scene graph"
    assert "DEVICES" in xml, "Missing DEVICES block"

    # Count devices
    n_devices = len(lab["devices"])
    found_devices = xml.count("<DEVICE>")
    assert found_devices == n_devices, f"Device count mismatch: {found_devices} vs {n_devices}"

    # Count links
    n_links = len(lab.get("links", []))
    found_links = xml.count("<LINK>")
    assert found_links == n_links, f"Link count mismatch: {found_links} vs {n_links}"

    # 4. Topology rendering check
    dot = diagram.generate_topology_dot(lab)
    assert "NetworkTopology" in dot

    # 5. Text guide export check
    text = ai_generator.export_lab_to_text(lab)
    assert "CISCO PACKET TRACER LAB GUIDE" in text

    print(f"  [OK] {lab_name:<12}: PKT={len(pkt_bytes):>6} bytes | XML={len(xml):>7} bytes | Devices={n_devices} | Links={n_links} | PASSED")

print()
print("=== All tests passed successfully! ===")
