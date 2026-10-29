"""pkt_generator.py: Native Cisco Packet Tracer .pkt file generator.

Generates authentic, directly-openable Cisco Packet Tracer (.pkt) files
from lab blueprint JSON definitions.

Architecture:
1. Loads official Packet Tracer hardware definitions (Cisco 2960-24TT, 2911, PC-PT, etc.)
   and canonical network scene graph from `pt_data/`.
2. Configures devices: places nodes on canvas, assigns IP addresses, and embeds
   Cisco IOS CLI running configurations.
3. Wires interface links: attaches cables between designated FastEthernet and
   GigabitEthernet interfaces.
4. Encodes and seals the document using `pkt_core`:
   - Qt qCompress (4-byte BE length prefix + zlib stream)
   - Layer B XOR deobfuscation
   - Crypto++ Twofish-EAX authenticated encryption
   - Layer A positional reversal & XOR scrambling
"""

from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import the pure-Python Packet Tracer container codec
from pkt_core.codec import container
from lab_validation import require_valid_lab

# Directory containing templates and baseline seed
DATA_DIR = Path(__file__).parent / "pt_data"
SEED_XML_PATH = DATA_DIR / "network_seed.xml"
TEMPLATES_JSON_PATH = DATA_DIR / "device_templates.json"


def _load_templates(path: Path) -> Tuple[Dict[str, bytes], Dict[str, str]]:
    """Load harvested hardware templates from JSON."""
    with open(path, "r", encoding="utf-8") as f:
        t = json.load(f)
    gz = t.get("gz", False)

    def dec(v: str) -> bytes:
        b = base64.b64decode(v)
        return gzip.decompress(b) if gz else b

    models = {k: dec(v) for k, v in t["models"].items()}
    modules = {k: dec(v).decode("utf-8") for k, v in t.get("modules", {}).items()}
    return models, modules


def _det_uuid(*parts: Any) -> str:
    """Generate a deterministic UUIDv4 for physical workspace nodes."""
    digest = hashlib.sha256("\x00".join(str(p) for p in parts).encode("utf-8")).digest()
    b = bytearray(digest[:16])
    b[6] = (b[6] & 0x0F) | 0x40  # version 4
    b[8] = (b[8] & 0x3F) | 0x80  # RFC 4122 variant
    return str(uuid.UUID(bytes=bytes(b)))


class LabBuilder:
    """Constructs a Cisco Packet Tracer DOM tree from device specifications."""

    def __init__(self, seed_xml_path: Path, templates_path: Path) -> None:
        self.models, self.modules = _load_templates(templates_path)
        with open(seed_xml_path, "rb") as f:
            raw = f.read()
        self.base = ET.fromstring(raw)
        self.net = self.base.find("NETWORK")
        if self.net is None:
            raise ValueError("Seed XML missing <NETWORK> element")
        self.devs = self.net.find("DEVICES")
        if self.devs is None:
            raise ValueError("Seed XML missing <DEVICES> element")
        self._pw = self.base.find("PHYSICALWORKSPACE")
        self._wsroot = self._pw.find("NODE") if self._pw is not None else None

        existing = self.devs.findall("DEVICE")
        donor_pp = donor_cid = None
        self._donor_cpur = None
        if existing:
            dc = existing[0].find("WORKSPACE/PHYSICAL_CPUR")
            if dc is not None:
                self._donor_cpur = copy.deepcopy(dc)
                donor_pp = dc.findtext("PARENT_PATH")
                donor_cid = dc.findtext("CONTAINER_ID")

        self._PP = donor_pp or (self._pw.findtext("HOMERACK") if self._pw is not None else None)
        self._rack = self._find_container(donor_cid)
        self._initial_devs = list(existing)
        self._n = 0
        self._pos = 4
        self._mac = 0x2000
        self._els: Dict[str, ET.Element] = {}
        self._name_to_sid: Dict[str, str] = {}

    def _find_container(self, cid: Optional[str]) -> Optional[ET.Element]:
        root = self._wsroot
        if root is None:
            return None
        rack = None
        for n in root.iter("NODE"):
            u = n.findtext("UUID_STR")
            if cid and u == cid:
                self._CID = cid
                return n
            if rack is None and (n.findtext("TYPE") == "4" or "rack" in (n.findtext("NAME") or "").lower()):
                rack = n
        if rack is not None:
            self._CID = rack.findtext("UUID_STR")
        return rack

    def _add_leaf(self, name: str, leaf: str, x: int = 0) -> None:
        if self._rack is None:
            return
        ch = self._rack.find("CHILDREN")
        if ch is None:
            ch = ET.SubElement(self._rack, "CHILDREN")
        el = ET.fromstring(
            f'<NODE><X>{x}</X><Y>0</Y><TYPE>6</TYPE><NAME translate="true">{name}</NAME>'
            f'<SX>1</SX><SY>1</SY><W>0</W><H>0</H><D>0</D>'
            f'<PATH isanim="false">../art/Background/grid_100x100.png</PATH><CHILDREN/>'
            f'<MANUAL_SCALING>false</MANUAL_SCALING><SCALED_PIXMAP_WIDTH>0</SCALED_PIXMAP_WIDTH>'
            f'<SCALED_PIXMAP_HEIGHT>0</SCALED_PIXMAP_HEIGHT><INIT_WIDTH>0</INIT_WIDTH><INIT_HEIGHT>0</INIT_HEIGHT>'
            f'<INIT_DEPTH>0</INIT_DEPTH><INIT_SX>1</INIT_SX><INIT_SY>1</INIT_SY><INIT_SZ>1</INIT_SZ>'
            f'<BG_TILED>false</BG_TILED><CUSTOM_IMAGE_WIDTH>-1</CUSTOM_IMAGE_WIDTH>'
            f'<CUSTOM_IMAGE_HEIGHT>-1</CUSTOM_IMAGE_HEIGHT><SCALE_FACTOR>1</SCALE_FACTOR>'
            f'<UUID_STR>{{{leaf}}}</UUID_STR><SLOT>0</SLOT><SUB_SLOT>0</SUB_SLOT>'
            f'<ICP_CSX>0</ICP_CSX><ICP_CSY>0</ICP_CSY></NODE>'
        )
        ch.append(el)

    def _make_cpur(self, x: int, leaf: str) -> str:
        c = copy.deepcopy(self._donor_cpur)
        if c is None:
            c = ET.fromstring(
                "<PHYSICAL_CPUR><X_PN>0.03175</X_PN><Y_PN>0.134</Y_PN><X>0</X><Y>0</Y>"
                "<SLOT>0</SLOT><SUBSLOT>0</SUBSLOT><PARENT_PATH></PARENT_PATH>"
                "<CONTAINER_ID></CONTAINER_ID><ICP_CONTAINER_SCENE_X>0</ICP_CONTAINER_SCENE_X>"
                "<ICP_CONTAINER_SCENE_Y>0</ICP_CONTAINER_SCENE_Y>"
                "<ORIGINAL_DEVICE_UUID></ORIGINAL_DEVICE_UUID></PHYSICAL_CPUR>"
            )

        def set_(tag: str, val: Any) -> None:
            e = c.find(tag)
            if e is None:
                e = ET.SubElement(c, tag)
            e.text = str(val)

        set_("PARENT_PATH", self._PP)
        set_("CONTAINER_ID", getattr(self, "_CID", ""))
        set_("X", str(x))
        set_("Y", "0")
        set_("SLOT", "0")
        set_("SUBSLOT", "0")
        set_("ORIGINAL_DEVICE_UUID", f"{{{_det_uuid('cpur', leaf)}}}")
        return ET.tostring(c, encoding="unicode")

    def _next_mac(self) -> str:
        self._mac += 1
        n = self._mac
        return "%04X.%04X.%04X" % (0x0212, (n >> 16) & 0xFFFF, n & 0xFFFF)

    def prune_seed_devices(self) -> None:
        """Remove pre-existing seed devices so the canvas contains only our lab."""
        dead = set()
        for el in self._initial_devs:
            eng = el.find("ENGINE")
            sid = eng.findtext("SAVE_REF_ID") if eng is not None else None
            if sid:
                dead.add(sid)
            ph = el.findtext("WORKSPACE/PHYSICAL")
            if ph and self._wsroot is not None:
                leaf = "{%s}" % ph.split(",")[-1].strip().strip("{}")
                for n in list(self._wsroot.iter("NODE")):
                    if n.findtext("UUID_STR") == leaf:
                        for parent in self._wsroot.iter("NODE"):
                            ch = parent.find("CHILDREN")
                            if ch is not None and n in list(ch):
                                ch.remove(n)
            if el in list(self.devs):
                self.devs.remove(el)

        links = self.net.find("LINKS")
        if links is not None and dead:
            for L in list(links.findall("LINK")):
                cab = L.find("CABLE")
                if cab is not None and (cab.findtext("FROM") in dead or cab.findtext("TO") in dead):
                    links.remove(L)
        self._initial_devs = []

    def add_device(
        self,
        model: str,
        name: str,
        x: int = 100,
        y: int = 100,
        power: bool = True,
        ios_config: Optional[str] = None,
        pc_ip: Optional[Tuple[str, str, str]] = None,
    ) -> str:
        """Place and configure a device on the canvas."""
        i = self._n
        self._n += 1
        cid = getattr(self, "_CID", "")
        leaf = _det_uuid("leaf", cid, i, name, model)
        px = self._pos
        self._pos += 6
        self._add_leaf(name, leaf, x=px)
        phys = f"{self._PP},{cid},{{{leaf}}}"

        blk = self.models[model].decode("utf-8", "replace")
        s = re.sub(r"save-ref-id:\d+", lambda m: "save-ref-id:%d" % (9_900_000_000_000_000_000 + i), blk)
        s = re.sub(r"<NAME[^>]*>.*?</NAME>", f'<NAME translate="true">{name}</NAME>', s, count=1, flags=re.S)
        s = re.sub(
            r"(<WORKSPACE>\s*<LOGICAL>\s*<X>)[^<]*(</X>\s*<Y>)[^<]*(</Y>)",
            lambda m: m.group(1) + str(x) + m.group(2) + str(y) + m.group(3),
            s, count=1, flags=re.S
        )
        s = re.sub(r"<PHYSICAL[^>]*>[^<]*</PHYSICAL>", f"<PHYSICAL>{phys}</PHYSICAL>", s)
        s = re.sub(r"<PHYSICAL_CPUR>.*?</PHYSICAL_CPUR>", "", s, flags=re.S)
        cpur = self._make_cpur(px, leaf)
        s = re.sub(r"(<PHYSICAL>[^<]*</PHYSICAL>)", lambda m: m.group(1) + cpur, s, count=1)
        el = ET.fromstring(s)

        for tag in ("MACADDRESS", "BIA"):
            for e in el.iter(tag):
                e.text = self._next_mac()

        eng = el.find("ENGINE")
        if eng is None:
            raise ValueError(f"Template for {model} missing <ENGINE>")

        for e in list(eng.findall("SAVE_REF_ID")):
            eng.remove(e)
        sid = f"save-ref-id:{9_900_000_000_000_000_000 + i}"
        ET.SubElement(eng, "SAVE_REF_ID").text = sid

        p = eng.find("POWER")
        if p is None:
            p = ET.Element("POWER")
            kids = list(eng)
            anchor = eng.find("NAME")
            at = kids.index(anchor) + 1 if anchor is not None else min(2, len(kids))
            eng.insert(at, p)
        p.text = "true" if power else "false"

        # Embedded Cisco IOS CLI running-configuration
        if ios_config:
            for rc in list(eng.findall("RUNNINGCONFIG")):
                eng.remove(rc)
            rc = ET.SubElement(eng, "RUNNINGCONFIG")
            lines = [line.rstrip() for line in ios_config.splitlines() if line.strip()]
            for L in lines:
                ET.SubElement(rc, "LINE").text = L

        # PC IP address configuration
        if pc_ip:
            port = el.find(".//PORT")
            if port is not None:
                ip, mask, gw = pc_ip
                for tag, val in [("IP", ip), ("SUBNET", mask), ("PORT_GATEWAY", gw), ("PORT_DHCP_ENABLE", "false")]:
                    if val is not None:
                        e = port.find(tag)
                        if e is None:
                            e = ET.SubElement(port, tag)
                        e.text = str(val)

        self.devs.append(el)
        self._els[sid] = el
        self._name_to_sid[name] = sid
        return sid

    def link(
        self,
        a_name_or_sid: str,
        a_port: str,
        b_name_or_sid: str,
        b_port: str,
        kind: str = "copper",
    ) -> None:
        """Attach a cable link between two interfaces."""
        a_sid = self._name_to_sid.get(a_name_or_sid, a_name_or_sid)
        b_sid = self._name_to_sid.get(b_name_or_sid, b_name_or_sid)

        links_el = self.net.find("LINKS")
        if links_el is None:
            links_el = ET.SubElement(self.net, "LINKS")

        L = ET.SubElement(links_el, "LINK")
        ET.SubElement(L, "TYPE").text = "eCopper" if kind == "copper" else "eSerial"
        cab = ET.SubElement(L, "CABLE")
        fields = [
            ("LENGTH", "1"), ("FUNCTIONAL", "true"),
            ("FROM", a_sid), ("PORT", a_port),
            ("TO", b_sid), ("PORT", b_port),
            ("FROM_DEVICE_MEM_ADDR", "1"), ("TO_DEVICE_MEM_ADDR", "2"),
            ("FROM_PORT_MEM_ADDR", "3"), ("TO_PORT_MEM_ADDR", "4"),
            ("GEO_VIEW_COLOR", "#6ba72e"), ("IS_MANAGED_IN_RACK_VIEW", "false"),
            ("TYPE", "eStraightThrough"),
        ]
        for t, v in fields:
            ET.SubElement(cab, t).text = v

    def build_pkt_bytes(self) -> bytes:
        """Serialize XML and compile into sealed .pkt container bytes."""
        xml_bytes = ET.tostring(self.base, encoding="unicode").encode("utf-8")
        return container.encode_bytes(xml_bytes, fmt="pkt")


# ---------------------------------------------------------------------------
# Public Generator Functions
# ---------------------------------------------------------------------------

def generate_pkt_bytes(lab_data: Dict[str, Any]) -> bytes:
    """Convert a lab blueprint JSON dictionary into a valid Cisco Packet Tracer .pkt file (bytes).

    Args:
        lab_data: Structured lab blueprint with devices, links, addressing, and configs.

    Returns:
        Raw bytes of the compiled .pkt container.
    """
    require_valid_lab(lab_data)
    builder = LabBuilder(SEED_XML_PATH, TEMPLATES_JSON_PATH)
    builder.prune_seed_devices()

    # Build IP addressing map: device_id -> (ip, mask, gateway)
    addr_map: Dict[str, Tuple[str, str, str]] = {}
    for entry in lab_data.get("addressing", []):
        dev = entry.get("device")
        if dev:
            addr_map[dev] = (
                entry.get("ip", ""),
                entry.get("mask", ""),
                entry.get("gateway", "") or "",
            )

    # Cisco IOS configs map
    configs = lab_data.get("configurations", {})

    # Model translation to canonical Packet Tracer template names
    model_map = {
        ("switch", "2960"): "2960-24TT",
        ("switch", "2960-24TT"): "2960-24TT",
        ("router", "2911"): "2911",
        ("pc", "Generic PC"): "PC-PT",
        ("pc", "Generic"): "PC-PT",
        ("pc", ""): "PC-PT",
    }

    devices = lab_data.get("devices", [])

    # Layout calculation (spread logically across canvas)
    coords: Dict[str, Tuple[int, int]] = {}
    routers = [d for d in devices if "router" in d.get("type", "").lower()]
    switches = [d for d in devices if "switch" in d.get("type", "").lower()]
    pcs = [d for d in devices if d.get("type", "pc").lower() == "pc"]

    # Place routers in top band
    for i, r in enumerate(routers):
        coords[r["id"]] = (250 + i * 280, 150)
    # Place switches in middle band
    for i, s in enumerate(switches):
        coords[s["id"]] = (220 + i * 280, 320)
    # Place PCs in bottom band
    for i, p in enumerate(pcs):
        coords[p["id"]] = (160 + i * 160, 500)

    # Add devices
    for d in devices:
        did = d["id"]
        dtype = d.get("type", "pc").lower()
        raw_m = d.get("model", "")
        pt_model = model_map.get(
            (dtype, raw_m),
            "2960-24TT" if dtype == "switch" else ("2911" if dtype == "router" else "PC-PT")
        )
        cx, cy = coords.get(did, (200, 300))

        pc_ip = addr_map.get(did) if dtype == "pc" else None
        ios_config = configs.get(did)

        builder.add_device(
            model=pt_model,
            name=did,
            x=cx,
            y=cy,
            power=True,
            ios_config=ios_config,
            pc_ip=pc_ip,
        )

    # Add cabling links
    for link in lab_data.get("links", []):
        from_dev = link.get("from", "")
        from_port = link.get("from_port", "")
        to_dev = link.get("to", "")
        to_port = link.get("to_port", "")
        if from_dev and to_dev and from_port and to_port:
            builder.link(from_dev, from_port, to_dev, to_port, kind="copper")

    return builder.build_pkt_bytes()


def save_pkt_file(lab_data: Dict[str, Any], output_path: str) -> None:
    """Write a .pkt file to disk from a lab blueprint dictionary."""
    pkt_bytes = generate_pkt_bytes(lab_data)
    with open(output_path, "wb") as f:
        f.write(pkt_bytes)


def decode_pkt_bytes(pkt_bytes: bytes) -> str:
    """Decode a .pkt file back to its XML string (for verification and inspection)."""
    c = container.decode_bytes(pkt_bytes, fmt="pkt")
    return c.xml.decode("utf-8")


if __name__ == "__main__":
    sample_file = Path(__file__).parent / "samples" / "basic_lan.json"
    with open(sample_file) as f:
        lab = json.load(f)
    out = Path(__file__).parent / "sample_basic_lan.pkt"
    save_pkt_file(lab, str(out))
    print(f"Generated: {out} ({out.stat().st_size} bytes)")
    xml = decode_pkt_bytes(out.read_bytes())
    print(f"Verification successful: Root element <{xml[1:xml.find('>')]}>, {len(xml)} XML bytes.")
    out.unlink()
