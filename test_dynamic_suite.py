"""test_dynamic_suite.py: Verify dynamic on-the-fly prompt generation across arbitrary topologies."""

import sys
from pathlib import Path

PROJ = Path(__file__).parent
sys.path.insert(0, str(PROJ))

import ai_generator
import pkt_generator

test_cases = [
    ("6 pcs 3 at each switch connected by a router using networks 20.0.0.0 and 30.0.0.0", 9, 8),
    ("3 switches with 2 pcs each connected to 1 router using subnets 10.1.0.0, 10.2.0.0, 10.3.0.0", 10, 9),
    ("2 routers connected together with 2 switches and 4 pcs", 8, 7),
    ("1 switch with 8 PCs on 172.16.1.0/24", 9, 8),
    ("5 workstations on a switch", 6, 5),
    ("4 computers connected to 2 switches with a router", 7, 6)
]

print("=== Running Dynamic On-The-Fly Prompt Test Suite ===")

for prompt, exp_devs, exp_links in test_cases:
    lab = ai_generator.synthesize_lab_from_prompt(prompt)
    valid, errors = ai_generator.validate_lab_data(lab)
    assert valid, f"Validation failed for '{prompt}': {errors}"
    assert len(lab["devices"]) == exp_devs, f"Requested device count mismatch for '{prompt}'"
    assert len(lab["links"]) == exp_links, f"Requested link count mismatch for '{prompt}'"

    pkt_bytes = pkt_generator.generate_pkt_bytes(lab)
    xml = pkt_generator.decode_pkt_bytes(pkt_bytes)

    dev_count = xml.count("<DEVICE>")
    link_count = xml.count("<LINK>")

    assert dev_count == len(lab["devices"]), f"Mismatch: {dev_count} vs {len(lab['devices'])}"
    assert link_count == len(lab["links"]), f"Mismatch: {link_count} vs {len(lab['links'])}"

    print(f"  [OK] \"{prompt[:45]}...\"")
    print(f"       -> {dev_count} Devices, {link_count} Cables, PKT={len(pkt_bytes)} bytes | Validated")

print("\nAll dynamic on-the-fly prompt tests succeeded!")
