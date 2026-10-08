# LLM-Based Cisco Packet Tracer Lab Generator

**Course Project:** Computer Networks (Semester 3)  
**Proof of Concept:** Natural-Language Prompt → Single LLM API → Lab Blueprint (Topology + Addressing + Cisco CLI + Instructions)

---

## 📌 Project Overview

Designing practical networking labs for students can be time-consuming. This project provides a lightweight, focused Streamlit web application that accepts an instructor or student prompt and generates an end-to-end networking lab specification for **Cisco Packet Tracer**.

### Key Features
- **3 Supported Core Lab Categories:**
  1. **Basic LAN:** Single switch (Catalyst 2960) with 3–4 PCs in one subnet.
  2. **VLAN Segmentation:** Port-based VLANs (VLAN 10 & 20) demonstrating Layer 2 broadcast domain isolation.
  3. **Static Routing:** Dual Cisco routers (2911), dual switches (2960), and 4 PCs across multiple subnets with static IPv4 routes.
- **Topology Visualisation:** Clean Graphviz network diagrams with device icons and interface port labels.
- **Addressing & Cabling Tables:** Clear port mappings, IPv4 address schemes, subnet masks, and default gateways.
- **Ready-to-Paste Cisco CLI:** Formatted Cisco IOS commands for routers and switches.
- **Validation Engine:** Strict schema validation, duplicate port prevention, IP syntax verification, and gateway subnet checks using Python's `ipaddress`.
- **Pre-tested Offline Reference Labs:** Test the system instantly without needing an external API key.
- **Plain Text Export:** Download the entire lab guide as a `.txt` file with one click.

> **Honesty & Scope Note:** As agreed in the course project plan, the application generates a **Packet Tracer-ready blueprint**, not a native proprietary `.pkt` binary file. Students and instructors use the generated specification to build and test the network inside Cisco Packet Tracer.

---

## 📂 Project Structure

```text
Project/
├── app.py                 # Streamlit web interface
├── ai_generator.py        # LLM integration, prompt engineering, validation, export
├── diagram.py             # Graphviz topology generator
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
```

*(Alternatively, you can enter your API key directly into the sidebar in the Streamlit web interface at runtime.)*

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
6. Click **📥 Download Guide (.txt)** to export the lab document.

---

## 📋 Course Submission Checklist

- [x] Streamlit web application source code (`app.py`, `ai_generator.py`, `diagram.py`)
- [x] Three verified JSON sample blueprints (`samples/`)
- [x] Automated network validation engine (IP correctness, link validation, port conflict checks)
- [x] `requirements.txt`, `.env.example`, `.gitignore`
- [x] Detailed `PROGRESS.md` milestone tracker
- [x] User and technical documentation (`README.md`)
- [ ] Manual Cisco Packet Tracer verification screenshots (to be collected during PT simulation)
