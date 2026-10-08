# Project Progress Tracker

**Project:** LLM-Based Cisco Packet Tracer Lab Generator  
**Course:** Computer Networks (Semester 3)  
**Last Updated:** October 8, 2026  
**Status:** MVP Core & Application Fully Operational (Weeks 1 & 2 Completed)

---

## 📊 Summary Dashboard

| Phase | Planned Timeline | Status | Deliverables Completed |
|---|---|---|---|
| **Week 1: Core AI Pipeline** | Days 1–7 | ✅ Complete | Python 3.14 env, dependencies, JSON schema, prompt engineering, sample datasets |
| **Week 2: Visible Working Application** | Days 8–14 | ✅ Complete | Streamlit UI (`app.py`), Graphviz topology renderer (`diagram.py`), IP/port validation, CLI display, `.txt` exporter |
| **Week 3: Packet Tracer Verification** | Days 15–21 | 🔄 Ready for PT Testing | Reference labs created & internally verified against rules; ready for manual verification in Cisco Packet Tracer |
| **Week 4: Polish, Reporting & Demo** | Days 22–30 | ⏳ In Progress | Documentation, user instructions, presentation script, project report outline |

---

## 🎯 Detailed Milestone Breakdown

### Phase 1: Core AI Pipeline & Setup (Days 1–7) — ✅ COMPLETED
- [x] **Repo & Environment Setup**: Python 3.14 configured with `streamlit`, `google-genai`, `python-dotenv`, `pydantic`.
- [x] **Model Integration**: Configured to use **Gemini 3.8 Flash** (`gemini-3.8-flash`) as the target LLM.
- [x] **Project Structure**:
  - `app.py`: Streamlit frontend.
  - `ai_generator.py`: Prompt, LLM caller, schema validation, sample loader, text exporter.
  - `diagram.py`: Network topology DOT diagram generator for Graphviz.
  - `requirements.txt`, `.gitignore`, `.env.example`.
- [x] **JSON Schema Definition**:
  - Defined strict schema enforcing device models, links, IP addressing, CLI configs, instructions, and verification checklists.
- [x] **Prompt Engineering**:
  - Strict system instruction adhering to Project Plan Section 9.
  - Enforced structured JSON output without markdown fences and single automatic retry mechanism.
- [x] **Sample Datasets Created**:
  - `samples/basic_lan.json`: 1 switch (2960), 3 PCs in 192.168.1.0/24.
  - `samples/vlan_lab.json`: 1 switch (2960), 4 PCs partitioned into VLAN 10 (Faculty) and VLAN 20 (Students).
  - `samples/routing_lab.json`: 2 routers (2911), 2 switches (2960), 4 PCs across two subnets with static IPv4 routes.

---

### Phase 2: Visible Working Application (Days 8–14) — ✅ COMPLETED
- [x] **Network Diagram Visualisation**:
  - Built `diagram.py` generating clear Graphviz DOT syntax.
  - Distinct iconography and color coding for Routers (blue 3D box), Switches (green box), and Host PCs (gray ellipse).
  - Interface port labeling at connection endpoints (`taillabel` / `headlabel`).
  - Integrated with Streamlit's native `st.graphviz_chart` (renders in browser without requiring external Graphviz binaries).
- [x] **Addressing & Cabling Tables**:
  - Physical Cabling Links table (Source/Target device & interface).
  - IPv4 Addressing table (Device, Interface, IP, Subnet Mask, Gateway).
- [x] **Cisco CLI Configuration Blocks**:
  - Expandable syntax-highlighted code blocks for each device (switches and routers).
  - Copyable configuration ready to paste into Packet Tracer CLI tabs.
- [x] **Validation Rules (`validate_lab_data`)**:
  - [x] Required top-level keys presence.
  - [x] Supported `lab_type` validation.
  - [x] Device ID uniqueness.
  - [x] Link endpoint validity (no dangling links).
  - [x] Port conflict detection (one cable per physical interface).
  - [x] IPv4 format & subnet mask validity (`ipaddress`).
  - [x] Duplicate IP address detection.
  - [x] Default gateway subnet membership verification.
  - [x] CLI configuration presence for infrastructure devices.
- [x] **Downloadable Lab Guide**:
  - Export to structured `.txt` guide implemented via Streamlit `st.download_button`.
- [x] **Offline / Demo Mode**:
  - Interactive sidebar loader allowing instant loading and testing of the 3 pre-tested reference labs without requiring an API key.

---

### Phase 3: Packet Tracer Verification (Days 15–21) — 🔄 IN PROGRESS / READY FOR MANUAL TEST
- [ ] **Lab 1: Basic LAN Verification**:
  - [ ] Place Cisco Catalyst 2960 and 3 PCs in Cisco Packet Tracer.
  - [ ] Connect cabling: PC1 (Fa0) -> SW1 (Fa0/1), PC2 (Fa0) -> SW1 (Fa0/2), PC3 (Fa0) -> SW1 (Fa0/3).
  - [ ] Assign IPs: 192.168.1.10, 192.168.1.20, 192.168.1.30 (/24).
  - [ ] Apply SW1 commands.
  - [ ] Ping test PC1 -> PC2 and PC1 -> PC3 (expect 0% loss).
- [ ] **Lab 2: VLAN Segmentation Verification**:
  - [ ] Place Catalyst 2960 and 4 PCs in Packet Tracer.
  - [ ] Connect cabling to ports Fa0/1 through Fa0/4.
  - [ ] Paste SW1 VLAN configuration.
  - [ ] Ping PC1 -> PC3 (same VLAN 10): expect SUCCESS.
  - [ ] Ping PC1 -> PC2 (VLAN 10 to VLAN 20): expect REQUEST TIMED OUT (confirmed isolation).
  - [ ] `show vlan brief` verification.
- [ ] **Lab 3: Static Routing Verification**:
  - [ ] Place 2x 2911 routers, 2x 2960 switches, 4 PCs.
  - [ ] Connect Gi0/0 to switches and Gi0/1 between R1 and R2.
  - [ ] Paste R1 and R2 configs (including `ip route` commands).
  - [ ] Ping PC1 -> PC3 across subnets: expect SUCCESS.
  - [ ] Capture Packet Tracer verification screenshots.

---

### Phase 4: Polish, Reporting & Submission (Days 22–30) — ⏳ UPCOMING
- [x] **User Documentation (`README.md`)**: Complete setup and run guide.
- [ ] **Capture Screenshots**: UI screenshots and Packet Tracer CLI test screenshots.
- [ ] **Project Report**: Draft 4-6 page course project report based on Project Plan sections.
- [ ] **Presentation & Demo**: Rehearse demonstration script (Project Plan Section 11).

---

## 🛠️ How to Test the App Right Now
```powershell
python -m streamlit run app.py
```
Open `http://localhost:8501` in your browser.
