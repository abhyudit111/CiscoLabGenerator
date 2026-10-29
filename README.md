# LLM-Based Cisco Packet Tracer Lab Generator

**Course Project:** Computer Networks (Semester 3)  
**Proof of Concept:** Prompt → Gemini or Offline Generator → Blueprint Consistency Checks → Lab Blueprint (Topology + Addressing + Cisco CLI + Instructions)

---

## 📌 Project Overview

Designing practical networking labs for students can be time-consuming. This project provides a lightweight, focused Streamlit web application that accepts an instructor or student prompt and generates an end-to-end networking lab specification for **Cisco Packet Tracer** — including a directly-openable `.pkt` file.

### Key Features
- **Dynamic On-The-Fly Lab Generation:** Accepts supported natural language prompts (e.g., *"6 PCs, 3 at each switch connected by a router using 20.0.0.0 and 30.0.0.0"*, *"4 switches in a ring with 8 PCs"*, etc.) and synthesizes the topology, IP schemes, cabling, and Cisco CLI commands on the fly.
- **Dual Generation Pipeline:**
  1. **Google Gemini AI:** Live LLM generation with an API key and a configurable model ID (`GEMINI_MODEL` or the sidebar). Use a model available to your account; the application does not assume model availability.
  2. **Smart Procedural Engine (Offline):** Generates the bounded LAN, VLAN, and static-routing arrangements listed below without an API key. Unsupported or impossible requests are rejected.
- **🆕 Native `.pkt` Binary Generation:** Downloads a real Cisco Packet Tracer `.pkt` file with all devices placed, cables connected, IP addresses assigned, and Cisco CLI configurations pre-loaded. Built via a pure-Python Twofish-EAX encoder (`pkt_generator.py` and `pkt_core/`).
- **Topology Visualisation:** Clean Graphviz network diagrams with device icons and interface port labels.
- **Addressing & Cabling Tables:** Clear port mappings, IPv4 address schemes, subnet masks, and default gateways.
- **Ready-to-Paste Cisco CLI:** Formatted Cisco IOS commands for routers and switches.
- **Validation Engine:** Strict schema validation, duplicate port prevention, IP syntax verification, and gateway subnet checks using Python's `ipaddress`.
- **Reference Labs:** Quick 1-click test templates for Basic LAN, VLANs, and Static Routing.
- **Plain Text & Binary Export:** One-click downloads for `.pkt` simulation files and `.txt` lab guides.

---

## 📂 Project Structure

```text
Project/
├── app.py                 # Streamlit web interface
├── ai_generator.py        # LLM integration, sample loader, text export
├── offline_generator.py   # Supported offline prompt parsing and network generation
├── lab_validation.py      # Shared schema and network consistency checks
├── test_regressions.py    # Generation, validation, and mocked API regression tests
├── test_app.py            # Streamlit generation and fallback regression tests
├── diagram.py             # Graphviz topology generator
├── pkt_generator.py       # Native .pkt file generator
├── pkt_core/              # Pure-Python Packet Tracer container codec (Twofish-EAX)
├── pt_data/               # Hardware templates (2960, 2911, PC-PT) & baseline scene graph
├── requirements.txt       # Project dependencies
├── .env.example           # Example API configuration
├── .gitignore             # Git ignore file
├── README.md              # Project documentation and guide
├── PROGRESS.md            # Course milestone tracking
├── samples/               # Validated reference blueprints
│   ├── basic_lan.json
│   ├── vlan_lab.json
│   └── routing_lab.json
└── Cisco_Packet_Tracer_LLM_Lab_Generator_Project_Plan.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- Cisco Packet Tracer (for building and testing generated labs)
- A Google Gemini API key (optional for offline reference labs; get a free key from [Google AI Studio](https://aistudio.google.com/))

### 2. Installation

Clone or open the repository folder, then install dependencies:

```powershell
pip install -r requirements.txt
```

### 3. API Key Setup (Optional for Live LLM Generation)

Copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Open `.env` and paste your Gemini API key:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=your_available_model_id
```

Alternatively, enter the API key and model ID in the sidebar. Select **Use offline generation** to bypass Gemini even when a key is configured. API failure or invalid model output can fall back only to a supported offline lab; the displayed source and warning identify that fallback.

### 4. Running the Web Application

Launch the Streamlit app:

```powershell
python -m streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

---

## 🧪 Demonstration Script

To reproduce the project demonstration:

1. Start the app: `python -m streamlit run app.py`.
2. From the **Select Supported Lab Category** dropdown, choose **Static Routing**.
3. (Optional) In the prompt box, enter:  
   `"Create a static routing lab with 2 routers, 2 switches, and 4 PCs. Configure static routing between the two LANs."`
4. Click **🚀 Generate Lab** (or load from the sidebar if using offline mode).
5. Explore the generated sections:
   - **Network Topology Tab:** Review the visual diagram showing R1, R2, SW1, SW2, PC1–PC4 and interface labels (`Gi0/0`, `Gi0/1`, `Fa0/1`).
   - **Addressing & Cabling Tab:** Confirm the IP subnets (`192.168.1.0/24`, `192.168.2.0/24`, and WAN `10.0.0.0/30`).
   - **Cisco CLI Tab:** Copy configuration blocks for `R1`, `R2`, `SW1`, `SW2`.
   - **Steps & Verification Tab:** Follow the checklist to test ping connectivity across subnets.
6. Click **📦 Open in PT (.pkt)** to download a ready-to-open Cisco Packet Tracer file with all devices, cables and configs pre-loaded.
7. Click **📥 Guide (.txt)** to export the lab document as plain text.

---


## Supported scope and limitations

This course implementation is a **Packet Tracer lab-generation assistant**. The professor's original proposal described log upload, fault diagnosis, retrieval of networking documentation, and troubleshooting recommendations. Log analysis, root-cause diagnosis, RAG, and comparative research evaluation remain future work and are not implemented here.

Offline prompt support:

| Arrangement | Supported limits |
|---|---|
| LAN | 1–8 switches in a chain; an explicit ring needs at least 3 switches; one shared IPv4 subnet |
| One router | 1–3 switches/LANs on its three physical GigabitEthernet ports |
| Two routers | Exactly two switches/LANs, a separate WAN /30, and reciprocal static routes |
| VLANs | One switch, no router, exactly two VLAN IDs from 2–1001 (defaults: 10/20); PCs alternate between VLANs |
| Hosts | 1–192 total PCs, at most 24 per switch; a VLAN lab needs at least two |
| Addressing | IPv4 CIDR networks; bare IPv4 networks default to /24; enough usable addresses must exist |

Use prompts such as:

- `3 switches with 2 PCs each connected to 1 router`
- `4 switches in a ring with 8 PCs`
- `1 router with 1 switch and 2 PCs using 192.168.1.128/26`
- `1 switch with 4 PCs on VLAN 30 and VLAN 40`

Counts written as one through ten are also recognized. Offline parsing uses explicit patterns, not an LLM. More detailed requirements need Gemini and still must fit the supported hardware and pass validation. DHCP, dynamic routing, wireless, additional device types, inter-VLAN routing, and custom star/mesh layouts are outside the offline implementation.

All reference, offline, and Gemini paths check data types, device IDs/models, physical ports, port collisions, connected topology, usable IPv4 addresses, duplicate IPs, gateways assigned to routers, and selected CLI/addressing consistency. Static-routing labs check remote-LAN route coverage and direct next-hop references; VLAN labs check declarations and access assignments. Explicit prompt counts, supplied networks, and switch-ring requirements are also checked on generated results.

These are blueprint checks, not a full IOS interpreter or a network simulator. The validator does not prove forwarding behavior, complete VLAN/trunk correctness, or convergence. Open the exported file in the installed Packet Tracer version, verify saved device state against the guide, run the listed commands and ping tests, and record screenshots. A switch ring intentionally has an STP-blocked path. Initial pings can lose a packet during ARP learning.

## Automated verification

Tested locally with Python 3.14, Streamlit 1.65.0, and google-genai 2.29.0. From this directory run:

```powershell
python -m unittest test_regressions test_app -v
python test_pkt.py
python test_dynamic_suite.py
```

The unit/UI tests mock Gemini and use no live API quota. Packet export tests check encode/decode consistency and device/link preservation; they do not launch Packet Tracer or establish successful simulation. API availability must be checked with the user's configured account and model.

## 📋 Course Submission Checklist

- [x] Streamlit web application source code (`app.py`, `ai_generator.py`, `diagram.py`)
- [x] **🆕 Native `.pkt` file generator** (`pkt_generator.py`) — pure-Python Twofish-EAX encoder
- [x] Three JSON reference blueprints with consistency checks (`samples/`)
- [x] Automated network validation engine (IP correctness, link validation, port conflict checks)
- [x] `requirements.txt`, `.env.example`, `.gitignore`
- [x] Detailed `PROGRESS.md` milestone tracker
- [x] User and technical documentation (`README.md`)
- [ ] Manual Cisco Packet Tracer verification screenshots (to be collected during PT simulation)
