"""Regression tests for prompt fidelity, validation, exports, and AI fallback.

Run with: python -m unittest test_regressions -v
No API key or live network access is used.
"""

import copy
import ipaddress
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import ai_generator as a
import pkt_generator


class GenerationTests(unittest.TestCase):
    def test_per_switch_counts(self):
        lab = a.synthesize_lab_from_prompt("3 switches with 2 PCs each connected to 1 router")
        self.assertEqual(len(lab["devices"]), 10)
        self.assertEqual(len(lab["links"]), 9)
        for switch in ("SW1", "SW2", "SW3"):
            self.assertEqual(sum(l["to"] == switch and l["from"].startswith("PC") for l in lab["links"]), 2)

    def test_word_counts(self):
        lab = a.synthesize_lab_from_prompt("two switches with three PCs each and one router")
        self.assertEqual(len(lab["devices"]), 9)

    def test_switch_ring(self):
        lab = a.synthesize_lab_from_prompt("4 switches in a ring with 8 PCs")
        self.assertEqual(len(lab["links"]), 12)
        switch_links = [l for l in lab["links"] if l["from"].startswith("SW")]
        for switch in ("SW1", "SW2", "SW3", "SW4"):
            self.assertEqual(sum(switch in (l["from"], l["to"]) for l in switch_links), 2)
        self.assertEqual(len({e["ip"] for e in lab["addressing"]}), 8)

    def test_switch_chain(self):
        lab = a.synthesize_lab_from_prompt("3 switches with 6 PCs")
        self.assertEqual(len(lab["links"]), 8)
        self.assertTrue(a.validate_lab_data(lab)[0])

    def test_subnet_arithmetic(self):
        for prompt, subnet in [
            ("1 switch with 3 PCs using 192.168.1.0/28", "192.168.1.0/28"),
            ("1 router with 1 switch and 2 PCs using 192.168.1.128/26", "192.168.1.128/26"),
            ("1 switch with 20 PCs using 10.0.0.0/8", "10.0.0.0/8"),
        ]:
            with self.subTest(subnet=subnet):
                lab = a.synthesize_lab_from_prompt(prompt)
                net = ipaddress.IPv4Network(subnet)
                self.assertTrue(all(ipaddress.IPv4Address(e["ip"]) in net for e in lab["addressing"]))

    def test_vlan_generation(self):
        lab = a.synthesize_lab_from_prompt("1 switch with 4 PCs on VLAN 30 and VLAN 40")
        config = lab["configurations"]["SW1"]
        self.assertEqual(lab["lab_type"], "vlan")
        for vid in (30, 40):
            self.assertIn(f"vlan {vid}\n", config)
            self.assertEqual(config.count(f"switchport access vlan {vid}\n"), 2)
        self.assertIn("Expected: failure", "\n".join(lab["verification"]))

    def test_vlan_category_is_honored(self):
        self.assertEqual(a.synthesize_lab_from_prompt("4 PCs on a switch", "vlan")["lab_type"], "vlan")

    def test_single_pc_has_no_nonexistent_ping_target(self):
        lab = a.synthesize_lab_from_prompt("1 PC on 3 switches")
        self.assertEqual(sum(d["type"] == "pc" for d in lab["devices"]), 1)
        self.assertNotIn("PC2", "\n".join(lab["verification"]))

    def test_wan_avoids_lan_overlap(self):
        lab = a.synthesize_lab_from_prompt("2 routers with 2 switches and 4 PCs using 10.0.0.0/8 and 192.168.1.0/24")
        wan = [e for e in lab["addressing"] if e["device"] == "R1" and e["interface"] == "GigabitEthernet0/1"][0]
        self.assertNotIn(ipaddress.IPv4Address(wan["ip"]), ipaddress.IPv4Network("10.0.0.0/8"))

    def test_unsupported_and_impossible_requests(self):
        for prompt in (
            "0 switches and 2 PCs", "1 switch with 0 PCs", "1 switch with 25 PCs",
            "3 routers with 3 switches and 6 PCs", "1 router with 4 switches and 8 PCs",
            "2 routers with 3 switches and 6 PCs", "1 switch with 3 PCs on 192.168.1.0/30",
            "1 switch with 4 PCs and DHCP", "hello", "1 switch using 999.1.1.0/24",
            "1 router and 2 switches using 10.0.0.0/8 and 10.1.0.0/24",
            "6 PCs with 2 at each switch on 2 switches",
            "1 switch with 4 PCs on 192.168.1.0/100",
            "1 switch with 4 PCs on VLANs 10, 20 and 30",
            "1 switch with 6 PCs and 3 VLANs",
            "-1 routers and 2 switches and 4 PCs",
        ):
            with self.subTest(prompt=prompt), self.assertRaises(ValueError):
                a.synthesize_lab_from_prompt(prompt)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.lab = a.load_sample_lab("basic_lan")

    def reject(self, mutation):
        lab = copy.deepcopy(self.lab)
        mutation(lab)
        valid, errors = a.validate_lab_data(lab)
        self.assertFalse(valid)
        self.assertTrue(errors)

    def test_malformed_json_values_do_not_crash(self):
        for value in (None, [], "bad", 42, True):
            self.assertFalse(a.validate_lab_data(value)[0])
            for key in self.lab:
                if key == "generation":
                    continue
                with self.subTest(key=key, value=value):
                    lab = copy.deepcopy(self.lab)
                    lab[key] = value
                    a.validate_lab_data(lab)
        for collection in ("devices", "links", "addressing"):
            for value in (None, [], "bad", 42, {}, {"id": []}, {"from": []}, {"device": []}):
                self.reject(lambda l, c=collection, v=value: l[c].append(v))

    def test_invalid_ports_and_collisions(self):
        self.reject(lambda l: l["links"][0].update(to_port="FastEthernet0/99"))
        self.reject(lambda l: l["links"][0].pop("from_port"))
        self.reject(lambda l: l["links"][1].update(to_port=l["links"][0]["to_port"]))

    def test_invalid_address_assignments(self):
        for changes in ({"ip": ""}, {"mask": ""}, {"ip": "192.168.1.0"},
                        {"ip": "192.168.1.255"}, {"gateway": None}, {"gateway": "192.168.1.1"},
                        {"ip": "192.168.1.20"}):
            self.reject(lambda l, c=changes: l["addressing"][0].update(c))
        self.reject(lambda l: l["addressing"].pop())

    def test_disconnected_network(self):
        self.reject(lambda l: l["links"].pop())

    def test_unsupported_models_and_unsafe_ids(self):
        self.reject(lambda l: l["devices"][0].update(model="invented"))
        self.reject(lambda l: l["devices"][0].update(id='SW1<&"'))

    def test_router_cli_consistency_and_routes(self):
        self.lab = a.load_sample_lab("static_routing")
        self.reject(lambda l: l["configurations"].update(R1=l["configurations"]["R1"].replace("192.168.1.1", "192.168.1.99")))
        self.reject(lambda l: l["configurations"].update(R1=l["configurations"]["R1"].replace("no shutdown", "shutdown")))
        self.reject(lambda l: l["configurations"].update(R1=l["configurations"]["R1"].replace("ip route 192.168.2.0 255.255.255.0 10.0.0.2", "")))
        self.reject(lambda l: l["addressing"][0].update(gateway=""))

    def test_vlan_configuration_required(self):
        self.lab = a.load_sample_lab("vlan")
        self.reject(lambda l: l["configurations"].update(SW1="enable\nconfigure terminal\nhostname SW1\nend"))

    def test_export_rejects_invalid_lab(self):
        self.lab["addressing"][0]["ip"] = ""
        with self.assertRaises(ValueError):
            pkt_generator.generate_pkt_bytes(self.lab)
        with self.assertRaises(ValueError):
            a.export_lab_to_text(self.lab)

    def test_malformed_generation_metadata(self):
        for value in (None, [], "bad", {"source": []}):
            self.reject(lambda l, v=value: l.update(generation=v))


class ModelTests(unittest.TestCase):
    def test_blank_model_is_rejected_before_api_call(self):
        with patch("google.genai.Client") as client, self.assertRaises(ValueError):
            a.generate_lab_with_llm("basic_lan", api_key="test-placeholder", model_name="")
        client.assert_not_called()

    def run_model(self, response=None, error=None, prompt="4 PCs on 1 switch", category="basic_lan"):
        client = MagicMock()
        client.models.generate_content.side_effect = error
        client.models.generate_content.return_value = SimpleNamespace(text=response)
        with patch("google.genai.Client", return_value=client):
            lab = a.generate_lab_with_llm(category, prompt, api_key="test-placeholder", model_name="test-model")
        client.close.assert_called_once()
        return lab, client

    def test_api_failure_has_honest_source(self):
        lab, client = self.run_model(error=RuntimeError("simulated API failure"))
        self.assertEqual(lab["generation"]["source"], "offline")
        self.assertIn("fallback_reason", lab["generation"])
        self.assertEqual(client.models.generate_content.call_count, 1)

    def test_valid_model_output(self):
        lab, _ = self.run_model(json.dumps(a.load_sample_lab("basic_lan")), prompt="3 PCs on 1 switch")
        self.assertEqual(lab["generation"], {"source": "gemini", "model": "test-model"})

    def test_wrong_counts_retry_then_fallback(self):
        lab, client = self.run_model(json.dumps(a.load_sample_lab("basic_lan")))
        self.assertEqual(client.models.generate_content.call_count, 2)
        self.assertEqual(lab["generation"]["source"], "offline")
        self.assertEqual(sum(d["type"] == "pc" for d in lab["devices"]), 4)

    def test_malformed_model_output(self):
        for response in ('{"devices": null}', '[]', 'not JSON'):
            with self.subTest(response=response):
                lab, client = self.run_model(response)
                self.assertEqual(lab["generation"]["source"], "offline")
                self.assertEqual(client.models.generate_content.call_count, 2)

    def test_unsupported_fallback_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_model(error=RuntimeError("offline"), prompt="3 routers with 3 switches and 6 PCs")


if __name__ == "__main__":
    unittest.main()
