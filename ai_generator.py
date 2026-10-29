"""ai_generator.py: LLM call, prompt engineering, dynamic network synthesis, JSON validation, and text export for Cisco Packet Tracer Lab Generator."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from lab_validation import validate_lab_data, require_valid_lab
from offline_generator import build_offline_lab, check_prompt_requirements

# Load local environment variables if available
load_dotenv()

# System prompt for LLM generation
SYSTEM_PROMPT = """You generate Cisco Packet Tracer lab exercises from user prompts.
Always prioritize the user's explicit instructions (device counts, IP subnets, switch connections, router topology).
Support any required network architecture (single LAN, multiple subnets, routed inter-networks, VLANs).
Use approved Cisco device models: '2960' for switches, '2911' for routers, 'Generic PC' for workstations.
Ensure interface port names are valid Cisco names:
  - PCs: FastEthernet0
  - Switches: FastEthernet0/1 to FastEthernet0/24, GigabitEthernet0/1 to GigabitEthernet0/2
  - Routers: GigabitEthernet0/0, GigabitEthernet0/1, GigabitEthernet0/2
Return valid JSON conforming to the schema. Ensure topology links, IP assignments, configurations, and instructions agree.
For routed networks, include default gateways on hosts and interface IP commands with 'no shutdown' on routers.
Return JSON only, without markdown fences."""

JSON_SCHEMA_DESCRIPTION = """{
  "title": "string (Descriptive lab title)",
  "lab_type": "string (one of: 'basic_lan', 'vlan', 'static_routing', 'custom')",
  "objective": "string (Clear 1-2 sentence learning goal)",
  "devices": [
    {"id": "string (e.g. SW1, PC1, R1)", "type": "string ('router', 'switch', or 'pc')", "model": "string (e.g. '2960' for switch, '2911' for router, 'Generic PC' for PC)"}
  ],
  "links": [
    {"from": "string (device id)", "from_port": "string (e.g. FastEthernet0/1 or GigabitEthernet0/0)", "to": "string (device id)", "to_port": "string"}
  ],
  "addressing": [
    {"device": "string", "interface": "string", "ip": "string (IPv4)", "mask": "string (e.g. 255.255.255.0)", "gateway": "string (default gateway or empty string)"}
  ],
  "configurations": {
    "DeviceID": "string (multi-line Cisco IOS CLI commands)"
  },
  "instructions": [
    "string (step-by-step ordered setup steps for the student in Packet Tracer)"
  ],
  "verification": [
    "string (explicit ping and show commands with expected outputs)"
  ]
}"""

SAMPLES_DIR = Path(__file__).parent / "samples"


def load_sample_lab(lab_type: str) -> Dict[str, Any]:
    """Load a reference lab and check blueprint consistency."""
    mapping = {
        "basic_lan": SAMPLES_DIR / "basic_lan.json",
        "vlan": SAMPLES_DIR / "vlan_lab.json",
        "static_routing": SAMPLES_DIR / "routing_lab.json",
        "custom": SAMPLES_DIR / "routing_lab.json",
    }
    sample_file = mapping.get(lab_type, SAMPLES_DIR / "basic_lan.json")
    if not sample_file or not sample_file.exists():
        raise FileNotFoundError(f"Sample file for lab type '{lab_type}' not found.")

    with open(sample_file, "r", encoding="utf-8") as f:
        lab = json.load(f)
    lab["generation"] = {"source": "reference"}
    return require_valid_lab(lab)


def synthesize_lab_from_prompt(user_prompt: str, default_category: str = "custom") -> Dict[str, Any]:
    """Generate a supported offline topology, rejecting unsupported requirements."""
    if not user_prompt.strip():
        return load_sample_lab(default_category)
    return build_offline_lab(user_prompt.strip(), default_category)


def generate_lab_with_llm(
    lab_type: str,
    user_prompt: str = "",
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate model output; explicitly label a supported offline fallback."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return synthesize_lab_from_prompt(user_prompt, lab_type)
    model_name = model_name if model_name is not None else os.getenv("GEMINI_MODEL", "")
    if not model_name.strip():
        raise ValueError("Enter a Gemini model ID before generating an AI lab.")

    def fallback(reason):
        lab = synthesize_lab_from_prompt(user_prompt, lab_type)
        lab["generation"]["fallback_reason"] = reason
        return require_valid_lab(lab)

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key, http_options={"timeout": 30000})
    except Exception:
        return fallback("Gemini client could not be initialized. Check the API configuration.")

    content = f"""Generate a complete Cisco Packet Tracer lab exercise.
Category: {lab_type}
User request: {user_prompt.strip() or 'Standard lab for the selected category.'}
Follow explicit device counts, PCs per switch, VLANs, topology, and IPv4 networks.
Use full interface names, approved models, and mutually consistent CLI/addressing.
Return raw JSON matching this schema:
{JSON_SCHEMA_DESCRIPTION}
"""
    try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=content,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT, temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
            except Exception:
                return fallback("Gemini request failed. Check the model ID, API key, quota, and connection.")
            try:
                text = (response.text or "").strip()
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
                lab = require_valid_lab(json.loads(text))
                check_prompt_requirements(lab, user_prompt)
                if lab_type == "vlan" and lab["lab_type"] != "vlan":
                    raise ValueError("The selected category requires a VLAN lab.")
                lab["generation"] = {"source": "gemini", "model": model_name}
                return lab
            except (ValueError, TypeError) as exc:
                content += f"\nCorrect the following validation problems and return the complete JSON again:\n{exc}"
        return fallback("Gemini output failed blueprint or prompt validation after two attempts.")
    finally:
        client.close()


def export_lab_to_text(lab_data: Dict[str, Any]) -> str:
    """Format the lab data into a clear, clean student lab document for .txt download."""
    require_valid_lab(lab_data)
    lines = []
    lines.append("=" * 70)
    lines.append(f"CISCO PACKET TRACER LAB GUIDE: {lab_data.get('title', 'Lab Exercise')}")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Category:  {lab_data.get('lab_type', 'N/A')}")
    lines.append(f"Objective: {lab_data.get('objective', '')}")
    generation = lab_data.get("generation", {})
    lines.append(f"Generation source: {generation.get('source', 'unknown')}")
    if generation.get("fallback_reason"):
        lines.append(f"Fallback: {generation['fallback_reason']}")
    lines.append("Validation: blueprint consistency checks; verify operation in Packet Tracer.")
    lines.append("")
    lines.append("-" * 70)
    lines.append("1. DEVICE INVENTORY")
    lines.append("-" * 70)
    for dev in lab_data.get("devices", []):
        model_str = f" (Model: {dev.get('model')})" if dev.get("model") else ""
        lines.append(f"  • {dev.get('id')} [{dev.get('type', 'Device').upper()}]{model_str}")
    lines.append("")
    lines.append("-" * 70)
    lines.append("2. PHYSICAL CABLING & CONNECTIONS")
    lines.append("-" * 70)
    for link in lab_data.get("links", []):
        lines.append(f"  • {link.get('from')} [{link.get('from_port')}]  <=======>  {link.get('to')} [{link.get('to_port')}]")
    lines.append("")
    lines.append("-" * 70)
    lines.append("3. IP ADDRESSING TABLE")
    lines.append("-" * 70)
    header = f"  {'Device':<10} | {'Interface':<18} | {'IP Address':<16} | {'Subnet Mask':<16} | {'Gateway':<15}"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for addr in lab_data.get("addressing", []):
        gw = addr.get("gateway") or "N/A"
        lines.append(
            f"  {addr.get('device', ''):<10} | {addr.get('interface', ''):<18} | "
            f"{addr.get('ip', ''):<16} | {addr.get('mask', ''):<16} | {gw:<15}"
        )
    lines.append("")
    lines.append("-" * 70)
    lines.append("4. CISCO DEVICE CONFIGURATIONS (CLI)")
    lines.append("-" * 70)
    for dev_id, config in lab_data.get("configurations", {}).items():
        lines.append(f"--- Configuration for {dev_id} ---")
        lines.append(config.strip())
        lines.append("")
    lines.append("-" * 70)
    lines.append("5. STEP-BY-STEP IMPLEMENTATION INSTRUCTIONS")
    lines.append("-" * 70)
    for i, step in enumerate(lab_data.get("instructions", []), 1):
        lines.append(f"  {i}. {step}")
    lines.append("")
    lines.append("-" * 70)
    lines.append("6. VERIFICATION & TESTING CHECKLIST")
    lines.append("-" * 70)
    for i, test in enumerate(lab_data.get("verification", []), 1):
        lines.append(f"  [ ] Step {i}: {test}")
    lines.append("")
    lines.append("=" * 70)
    lines.append("End of Lab Guide — Generated with Cisco Packet Tracer LLM Lab Generator")
    lines.append("=" * 70)

    return "\n".join(lines)
