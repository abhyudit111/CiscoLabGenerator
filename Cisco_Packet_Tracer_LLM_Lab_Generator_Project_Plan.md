# LLM-Based Cisco Packet Tracer Lab Generator

**Practical Course Project Plan — 30 Days**  
**Status:** Agreed simplified scope  
**Project type:** Small academic course project (working proof of concept)

## 1. Project idea and context

### Original proposal
The original idea, titled **“LLM-Based Intelligent Cisco Packet Tracer Lab Generator for Automated Networking Education,”** aims to reduce the effort instructors spend designing networking labs. An instructor describes the lab in natural language, and AI generates a topology, addressing plan, device configurations, student instructions, and related materials. The source proposal envisaged a broad range of protocols, RAG, automated assessment, research evaluation, and potential native `.pkt` generation.

### Final agreed approach
Because this is a **one-month course project worth a few marks**, we will build a small, working demonstration rather than a research-grade platform.

> **Core concept: Natural-language prompt → single LLM API → lab blueprint → topology diagram + IP table + Cisco CLI commands + setup/verification instructions.**

The application **does not automatically create or modify a Cisco Packet Tracer `.pkt` file**. Users build the generated network in Packet Tracer and apply the provided commands manually. The team will test reference examples in Packet Tracer to prove that the output is usable.

## 2. Objective and success definition

Build a simple Streamlit web app where a student or instructor can:

1. Select one of three supported lab categories and describe the desired lab.
2. Click **Generate Lab**.
3. See a readable topology diagram.
4. See the device list, connections, and IP addressing table.
5. Copy Cisco commands for supported routers and switches.
6. Follow clear instructions for creating and checking the lab in Packet Tracer.
7. Download the generated lab as a text file (PDF optional only if spare time).

**Project completed when:** these workflows function, and the three reference labs are verified manually in Packet Tracer.

## 3. Scope freeze

### Features we will build (MVP)

- Streamlit interface with a lab-type dropdown, optional prompt, and **Generate Lab** button.
- One LLM API integration (choose **either** GPT or Gemini; no multi-model framework).
- Structured JSON lab output with basic schema checks.
- Graphviz topology visualisation from the JSON device/link list.
- Device inventory and IP-addressing tables.
- Per-device Cisco CLI configuration blocks.
- Short, ordered student implementation instructions.
- Basic verification checklist and suggested `ping`/`show` commands.
- Simple error handling for API failures and malformed outputs.
- Downloadable text output.

### Explicitly out of scope

- Native `.pkt` file generation and Packet Tracer API integration.
- Automatic construction of a topology inside Packet Tracer.
- Automated end-to-end network simulation and digital twins.
- RAG, vector databases, document ingestion, LangChain, LangGraph, and multi-agent AI.
- Fine-tuning or training an LLM.
- Student accounts, logins, backend database, saved history, dashboards, and analytics.
- Grading rubrics, quizzes, adaptive difficulty, student performance tracking, and educational experiments.
- Advanced BGP, QoS, IPv6, wireless, NAT, firewall policies, complex ACLs, and arbitrary multi-protocol scenarios.
- Production deployment, comprehensive security systems, or scalability engineering.
- Formal instructor-vs-student research trials or statistical evaluation.

**Change-control rule:** Do not add optional features until all three lab types work and the reference examples are tested.

## 4. Supported networking labs

Restrict topology choices and device models to those tested in the installed Packet Tracer version.

| Lab | Typical devices | Concepts | Expected verification |
|---|---|---|---|
| **1. Basic LAN** | 1 switch, 3–4 PCs | IP addressing, connecting PCs through a switch | PCs in the same subnet successfully ping |
| **2. VLANs** | 1–2 switches, 4 PCs | VLAN 10 and VLAN 20, access ports; trunk if two switches used | Same-VLAN connectivity works; different VLANs remain isolated without routing |
| **3. Static Routing** | 2 routers, 2 switches, 2–4 PCs | Router interface addresses, distinct LAN subnets, static routes | PCs on different LANs successfully ping |

**Important:** The VLAN lab should **not** promise inter-VLAN ping unless a router or Layer-3 switching configuration is explicitly included. For this MVP, keep VLAN separation as the demonstration.

### Generation constraints
- Limit the number and types of devices to tested layouts. An unsupported prompt should receive a clear explanation or be mapped to one of the supported templates.
- Use a single known router model and switch model wherever possible; confirm interface names in Packet Tracer.
- Generate private IPv4 addresses with correct subnet masks and gateways.
- Ensure every displayed cable has a matching pair of device interfaces.
- The diagram, addressing table, commands, and instructions must describe **the same** lab.

## 5. Minimal technical architecture

```text
Streamlit web app (app.py)
    |
    | user chooses type and enters a prompt
    v
LLM API request (ai_generator.py)
    |
    | structured JSON lab blueprint
    v
Basic Python validation
    |-- devices and links exist
    |-- device IDs are unique
    |-- links reference real devices
    |-- addresses are parseable / not duplicated
    v
Graphviz renderer (diagram.py)
    |
    v
Streamlit output:
  topology + addressing table + CLI commands
  + lab setup steps + verification steps
    |
    v
Download as .txt
    |
    v
Student manually builds and tests in Packet Tracer
```

### Technology choices

| Purpose | Use |
|---|---|
| Programming language | Python |
| UI and app execution | Streamlit |
| AI lab generation | GPT **or** Gemini API |
| Structured data | Python `json`, optional Pydantic |
| Network diagrams | Graphviz (Python package + installed Graphviz executable) |
| IP correctness | Python `ipaddress` |
| Secrets | `.env` locally / environment variables |
| IDE and version control | VS Code + GitHub |
| Network verification | Cisco Packet Tracer, manual |
| Export | Plain `.txt` download (Streamlit) |

**Avoid:** React, FastAPI, Docker, PostgreSQL, ChromaDB, external orchestration systems, and additional infrastructure.

## 6. Proposed folder structure

```text
cisco-lab-generator/
├── app.py                 # Streamlit inputs, displays, download
├── ai_generator.py        # LLM call, prompt, JSON parsing, basic checks
├── diagram.py             # Graphviz rendering from nodes and links
├── requirements.txt
├── .env                   # API key; never commit to Git
├── .gitignore
├── README.md
└── samples/
    ├── basic_lan.json
    ├── vlan_lab.json
    └── routing_lab.json
```

A small project can keep the validation helper functions inside `ai_generator.py`. Do not create extra services/modules just for architectural appearance.

## 7. Data format: the single source of truth

Ask the LLM to output **JSON only**, conforming to a consistent structure. A simple illustrative payload:

```json
{
  "title": "Basic LAN Lab",
  "lab_type": "basic_lan",
  "objective": "Connect two PCs through a switch and verify connectivity.",
  "devices": [
    {"id": "SW1", "type": "switch", "model": "2960"},
    {"id": "PC1", "type": "pc"},
    {"id": "PC2", "type": "pc"}
  ],
  "links": [
    {"from": "PC1", "from_port": "FastEthernet0", "to": "SW1", "to_port": "FastEthernet0/1"},
    {"from": "PC2", "from_port": "FastEthernet0", "to": "SW1", "to_port": "FastEthernet0/2"}
  ],
  "addressing": [
    {"device": "PC1", "interface": "FastEthernet0", "ip": "192.168.1.10", "mask": "255.255.255.0", "gateway": ""},
    {"device": "PC2", "interface": "FastEthernet0", "ip": "192.168.1.11", "mask": "255.255.255.0", "gateway": ""}
  ],
  "configurations": {
    "SW1": "enable\nconfigure terminal\nhostname SW1\nend"
  },
  "instructions": [
    "Add a 2960 switch and two PCs in Packet Tracer.",
    "Connect each PC FastEthernet0 port to its indicated switch port.",
    "Assign the listed IPv4 addresses and subnet masks on the PCs.",
    "Apply the switch commands in its CLI."
  ],
  "verification": [
    "From PC1, ping 192.168.1.11. Expected: replies when connections and IP settings are correct."
  ]
}
```

For the Basic LAN example, a default gateway is not needed because both PCs are in the same subnet. For the Static Routing lab, host gateways and router interfaces are essential.

### Mandatory simple checks

- JSON parses successfully and required top-level keys exist.
- Selected lab type is one of the three supported categories.
- Every link endpoint refers to a defined device.
- A device interface is not assigned to two different cables.
- IP addresses and subnet masks are valid and do not conflict.
- Every relevant router/switch has a corresponding configuration or a documented reason one is unnecessary.
- A failed check produces a readable message; never quietly label an invalid lab as ready.

A single retry to the LLM for malformed JSON is sufficient for this project. More elaborate repair loops are unnecessary.

## 8. User interface: one page

**Inputs**
- **Lab category:** Basic LAN / VLANs / Static Routing (required dropdown).
- **Optional description:** e.g., “Create a static routing lab with 2 routers, 2 switches, and 4 PCs.”
- **Generate Lab** button.

**Outputs**
1. Lab title and objective.
2. Graphviz network topology.
3. Device/interface connection table.
4. IPv4 addressing table.
5. Cisco configurations (one expandable block per router/switch).
6. Setup steps and verification checklist.
7. **Download Lab (.txt)** button.

**Error states:** invalid key, API timeout, invalid model JSON, unsupported topic, and invalid addressing/device links.

There is no need for login, navigation sidebar, multi-page app, project history, or elaborate visual design.

## 9. Prompting strategy

Keep one reusable **system instruction** and a user prompt. A compact system instruction can be:

```text
You generate beginner-friendly Cisco Packet Tracer lab exercises.
Only support these lab types: basic_lan, vlan, static_routing.
Use the approved device models and exact device/interface conventions
provided in the request. Return valid JSON that conforms to the given
schema. Ensure topology links, IP assignments, configurations and
instructions agree. Never invent unsupported features. For a VLAN-only
exercise, do not expect communication between different VLANs without
routing. For static routing, include LAN gateways and routes in both
directions. Include realistic verification commands and expectations.
Return JSON only, without markdown fences.
```

The application adds the selected lab type, limits, and JSON shape to each request. Try to constrain the LLM to the three reference topology patterns rather than asking it to design arbitrary networks.

## 10. 30-day plan

### Week 1 (Days 1–7): Core AI pipeline

**Tasks**
1. Initialize GitHub repo and virtual environment.
2. Install Streamlit, the selected AI SDK, Graphviz dependencies, and `python-dotenv`.
3. Obtain API key and test a basic model call.
4. Implement the three-option lab selection and prompt field.
5. Write the JSON response contract and generation prompt.
6. Generate and display a basic LAN lab as JSON/table output.
7. Save the first correct example in `samples/basic_lan.json`.

**Exit:** The app accepts a request and returns valid structured Basic LAN data.

### Week 2 (Days 8–14): Visible working application

**Tasks**
1. Render devices and links using Graphviz.
2. Show device, addressing, and port/link tables.
3. Show CLI commands and procedural instructions.
4. Add the VLAN template and example.
5. Add the Static Routing template and example.
6. Add JSON error handling and simple IP/link checks.
7. Verify that all output sections remain internally consistent.

**Exit:** All three categories produce complete, readable lab packages inside Streamlit.

### Week 3 (Days 15–21): Packet Tracer verification

**Tasks**
1. Manually create the Basic LAN example in Packet Tracer.
2. Verify same-subnet pings.
3. Manually create the VLAN lab and verify same-VLAN reachability and cross-VLAN isolation.
4. Manually create the two-router static-routing lab.
5. Verify routes and end-to-end pings.
6. Correct failing generated commands or unsupported interface assumptions.
7. Implement `.txt` export and retest the output.

**Exit:** Three tested sample labs; screenshots of successful verification and saved test notes.

### Week 4 (Days 22–30): Polish and submit

**Tasks**
1. Re-test the app with at least two prompt variations per lab type.
2. Improve UI labels and messages (no major redesign).
3. Fix critical bugs only; freeze new features.
4. Make a clean README with installation and run instructions.
5. Prepare screenshots and a short demo recording.
6. Write a brief report: problem, objective, design, implementation, outputs, testing, limitations, conclusion.
7. Create a short presentation and rehearse the demonstration.

**Exit:** Runnable app, report, slides, three validated examples, and demo.

## 11. Final demonstration script

1. Launch the Streamlit app (`streamlit run app.py`).
2. Select **Static Routing**.
3. Enter: **“Create a network with 2 routers, 2 switches and 4 PCs. Configure static routing between the two LANs.”**
4. Click **Generate Lab**.
5. Show the topology, interface links, IP table, and router commands.
6. Explain how the student builds the network in Packet Tracer.
7. Show the **previously manually verified** Packet Tracer version and a successful ping between the LANs.
8. Download the generated lab as a `.txt` file.

**Presentation honesty:** The app generates a Packet Tracer-*ready* lab specification, **not** a native `.pkt` file. The prepared simulation demonstrates that the recommended topology and commands can work when implemented correctly.

## 12. Final submission package

- [ ] Working Streamlit source code.
- [ ] `requirements.txt` and `.env.example` (never include the actual API key).
- [ ] README with installation, key setup and launch instructions.
- [ ] Three sample JSON outputs.
- [ ] Three manually tested Packet Tracer reference labs (include `.pkt` examples created manually if permitted and useful).
- [ ] Screenshots of each generated lab and its verification.
- [ ] Basic text export.
- [ ] Brief course project report.
- [ ] PPT and short demo recording (if required by the course).

## 13. Known limitations

- Output is limited to three supported educational lab categories.
- The generated diagram is a visual plan, not a Packet Tracer native project.
- Device placement and configuration in Packet Tracer are manual.
- LLM-generated commands may have errors; validation is basic and manual testing is still necessary.
- Arbitrary prompt combinations and advanced networking protocols are unsupported.
- The app requires an internet connection to call a hosted model API.

These limitations are acceptable for a small academic proof of concept and should be clearly stated in the report.

## 14. Project management rules

1. **Working software comes before optional features.**
2. **Three supported labs are sufficient.** Do not broaden the protocol list.
3. **Use one model provider.** Do not build an abstraction layer for future providers.
4. **Use one simple app.** No separate frontend/backend unless a real blocker arises.
5. **Always test in Packet Tracer.** AI output alone is not proof of correctness.
6. **No native `.pkt` automation.** Manual lab construction is explicitly part of this project.
7. **Reserve the final week for demo and documentation.**

## 15. Final one-line scope statement

> **Build a simple Python Streamlit app that uses one LLM API to generate Basic LAN, VLAN, or Static Routing lab exercises, displaying a network diagram, IP addressing, Cisco device commands, step-by-step instructions, and a downloadable text guide; manually verify one representative example of each in Cisco Packet Tracer.**

---

### Relationship to the original proposal

The original proposal considered LLMs, RAG, advanced routing, automatic `.pkt` generation, digital-twin validation, grading, adaptive analytics, and formal educational-effectiveness evaluation. This document **intentionally excludes** those elements to meet the one-month deadline and low-stakes course-project objective. They should not be represented as implemented features in the final submission.
