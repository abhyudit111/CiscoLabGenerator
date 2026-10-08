"""ai_generator.py: LLM call, prompt engineering, JSON validation, and text export for Cisco Packet Tracer Lab Generator."""

import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Load local environment variables if available
load_dotenv()

# System prompt adhering strictly to Project Plan Section 9
SYSTEM_PROMPT = """You generate beginner-friendly Cisco Packet Tracer lab exercises.
Only support these lab types: basic_lan, vlan, static_routing.
Use the approved device models and exact device/interface conventions provided in the request.
Return valid JSON that conforms to the given schema. Ensure topology links, IP assignments, configurations and instructions agree.
Never invent unsupported features. For a VLAN-only exercise, do not expect communication between different VLANs without routing.
For static routing, include LAN gateways and routes in both directions. Include realistic verification commands and expectations.
Return JSON only, without markdown fences."""

JSON_SCHEMA_DESCRIPTION = """{
  "title": "string (Descriptive lab title)",
  "lab_type": "string (one of: 'basic_lan', 'vlan', 'static_routing')",
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
    """Load a verified reference lab from the samples directory."""
    mapping = {
        "basic_lan": SAMPLES_DIR / "basic_lan.json",
        "vlan": SAMPLES_DIR / "vlan_lab.json",
        "static_routing": SAMPLES_DIR / "routing_lab.json",
    }
    sample_file = mapping.get(lab_type)
    if not sample_file or not sample_file.exists():
        raise FileNotFoundError(f"Sample file for lab type '{lab_type}' not found.")
    
    with open(sample_file, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_lab_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate lab data against required schema and network correctness rules.
    
    Returns (is_valid, list_of_errors_or_warnings).
    """
    errors: List[str] = []
    
    # 1. Check required top-level keys
    required_keys = [
        "title", "lab_type", "objective", "devices",
        "links", "addressing", "configurations",
        "instructions", "verification"
    ]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required top-level key: '{key}'")
            
    if errors:
        return False, errors

    # 2. Check lab_type
    valid_lab_types = {"basic_lan", "vlan", "static_routing"}
    if data.get("lab_type") not in valid_lab_types:
        errors.append(f"Invalid lab_type '{data.get('lab_type')}'. Must be one of: {list(valid_lab_types)}")

    # 3. Check devices
    devices = data.get("devices", [])
    if not isinstance(devices, list) or len(devices) == 0:
        errors.append("Device list must be a non-empty list.")
        return False, errors
        
    device_ids = set()
    device_types: Dict[str, str] = {}
    for dev in devices:
        dev_id = dev.get("id")
        if not dev_id:
            errors.append("Found device missing 'id' attribute.")
            continue
        if dev_id in device_ids:
            errors.append(f"Duplicate device ID found: '{dev_id}'. Device IDs must be unique.")
        device_ids.add(dev_id)
        device_types[dev_id] = dev.get("type", "pc").lower()

    # 4. Check links
    links = data.get("links", [])
    if not isinstance(links, list):
        errors.append("Links must be a list.")
    else:
        assigned_interfaces = set()
        for idx, link in enumerate(links):
            from_dev = link.get("from")
            to_dev = link.get("to")
            from_port = link.get("from_port")
            to_port = link.get("to_port")
            
            if not from_dev or from_dev not in device_ids:
                errors.append(f"Link #{idx+1} references unknown source device: '{from_dev}'.")
            if not to_dev or to_dev not in device_ids:
                errors.append(f"Link #{idx+1} references unknown destination device: '{to_dev}'.")
            if from_dev and to_dev and from_dev == to_dev:
                errors.append(f"Link #{idx+1} connects device '{from_dev}' to itself.")
                
            # Port conflict check: each physical port can only connect to one cable
            if from_dev and from_port:
                from_endpoint = f"{from_dev}:{from_port}"
                if from_endpoint in assigned_interfaces:
                    errors.append(f"Port collision: Interface '{from_endpoint}' is wired to multiple links.")
                assigned_interfaces.add(from_endpoint)
                
            if to_dev and to_port:
                to_endpoint = f"{to_dev}:{to_port}"
                if to_endpoint in assigned_interfaces:
                    errors.append(f"Port collision: Interface '{to_endpoint}' is wired to multiple links.")
                assigned_interfaces.add(to_endpoint)

    # 5. Check addressing
    addressing = data.get("addressing", [])
    if not isinstance(addressing, list):
        errors.append("Addressing must be a list.")
    else:
        assigned_ips = set()
        for idx, entry in enumerate(addressing):
            dev = entry.get("device")
            ip = entry.get("ip")
            mask = entry.get("mask")
            gateway = entry.get("gateway", "").strip()
            
            if not dev or dev not in device_ids:
                errors.append(f"Addressing entry #{idx+1} references unknown device: '{dev}'.")
                
            # IP validation
            if ip:
                try:
                    ip_obj = ipaddress.IPv4Address(ip)
                    if ip in assigned_ips:
                        errors.append(f"Duplicate IP assignment: '{ip}' assigned multiple times.")
                    assigned_ips.add(ip)
                except ValueError:
                    errors.append(f"Invalid IPv4 address format: '{ip}' for device '{dev}'.")
                    
            if mask:
                try:
                    ipaddress.IPv4Network(f"0.0.0.0/{mask}")
                except ValueError:
                    errors.append(f"Invalid subnet mask format: '{mask}' for device '{dev}'.")

            # Default gateway check
            if gateway:
                try:
                    gw_obj = ipaddress.IPv4Address(gateway)
                    if ip and mask:
                        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                        if gw_obj not in net:
                            errors.append(
                                f"Gateway mismatch: Gateway '{gateway}' for '{dev}' is not in subnet {net}."
                            )
                except ValueError:
                    errors.append(f"Invalid default gateway format: '{gateway}' for device '{dev}'.")

    # 6. Check configurations for routers/switches
    configs = data.get("configurations", {})
    if not isinstance(configs, dict):
        errors.append("Configurations must be a dictionary mapping device ID to CLI commands.")
    else:
        for dev_id, dev_type in device_types.items():
            if dev_type in {"router", "switch"}:
                if dev_id not in configs or not str(configs[dev_id]).strip():
                    errors.append(f"Missing CLI configuration block for infrastructure device '{dev_id}'.")

    # 7. Check instructions and verification
    instructions = data.get("instructions", [])
    if not isinstance(instructions, list) or len(instructions) == 0:
        errors.append("Instructions must be a non-empty list of setup steps.")
        
    verification = data.get("verification", [])
    if not isinstance(verification, list) or len(verification) == 0:
        errors.append("Verification must be a non-empty list of test steps.")

    return len(errors) == 0, errors


def generate_lab_with_llm(
    lab_type: str,
    user_prompt: str = "",
    api_key: Optional[str] = None,
    model_name: str = "gemini-3.8-flash"
) -> Dict[str, Any]:
    """Call Google Gemini API using google-genai to generate a structured lab blueprint."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API key is required. Provide it in the sidebar or set GEMINI_API_KEY in .env.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)

    type_descriptions = {
        "basic_lan": "A single switch (Cisco Catalyst 2960) and 3 to 4 PCs in one subnet (e.g., 192.168.1.0/24).",
        "vlan": "A Cisco Catalyst 2960 switch with 4 PCs partitioned into VLAN 10 and VLAN 20 (no routing, demonstrating broadcast isolation).",
        "static_routing": "2 Cisco 2911 Routers (R1 and R2), 2 Cisco 2960 Switches (SW1 and SW2), and 4 PCs across two subnets with static IPv4 routes.",
    }

    prompt_content = f"""Generate a complete Cisco Packet Tracer lab exercise.

Lab Category: {lab_type}
Template expectation: {type_descriptions.get(lab_type, lab_type)}
User's specific request: {user_prompt.strip() if user_prompt.strip() else "Standard lab implementation according to educational best practices."}

Strict Requirements:
1. Adhere exactly to this JSON schema:
{JSON_SCHEMA_DESCRIPTION}
2. Output valid, raw JSON only. Do not include markdown code fences (```json or ```).
3. Ensure all ports, links, IP addresses, and Cisco commands strictly match each other.
"""

    def _call_model(content: str) -> str:
        response = client.models.generate_content(
            model=model_name,
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json"
            )
        )
        return response.text or ""

    def _clean_json_str(text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    # Initial call
    raw_response = _call_model(prompt_content)
    cleaned = _clean_json_str(raw_response)

    try:
        lab_data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Single retry as specified in the project plan
        retry_prompt = f"The previous output had a JSON parsing error. Please return ONLY valid JSON matching this schema:\n{prompt_content}"
        retry_response = _call_model(retry_prompt)
        cleaned = _clean_json_str(retry_response)
        lab_data = json.loads(cleaned)

    # Validate output
    is_valid, validation_errors = validate_lab_data(lab_data)
    if not is_valid:
        raise ValueError("Generated lab failed validation checks:\n- " + "\n- ".join(validation_errors))

    return lab_data


def export_lab_to_text(lab_data: Dict[str, Any]) -> str:
    """Format the lab data into a clear, clean student lab document for .txt download."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"CISCO PACKET TRACER LAB GUIDE: {lab_data.get('title', 'Lab Exercise')}")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Category:  {lab_data.get('lab_type', 'N/A')}")
    lines.append(f"Objective: {lab_data.get('objective', '')}")
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
