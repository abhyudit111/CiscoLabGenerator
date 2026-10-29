"""app.py: Streamlit Web UI for Cisco Packet Tracer LLM Lab Generator."""

import os
import html
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

import ai_generator
import diagram
import pkt_generator

# Page configuration
st.set_page_config(
    page_title="Cisco Packet Tracer Lab Generator",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Custom CSS for styling and badge appearance
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0369a1;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        margin-right: 0.5rem;
    }
    .badge-lan { background-color: #dbeafe; color: #1e40af; }
    .badge-vlan { background-color: #dcfce7; color: #166534; }
    .badge-routing { background-color: #fef3c7; color: #92400e; }
    .stCodeBlock {
        border-radius: 6px;
    }
    .pkt-info-box {
        background: linear-gradient(135deg, #e0f2fe 0%, #f0fdf4 100%);
        border: 1px solid #0284c7;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-top: 0.5rem;
        font-size: 0.85rem;
        color: #0c4a6e;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=16)
def cached_pkt_bytes(lab):
    return pkt_generator.generate_pkt_bytes(lab)


def accept_lab(lab):
    ai_generator.require_valid_lab(lab)
    for key in list(st.session_state):
        if key.startswith("verif_check_"):
            del st.session_state[key]
    st.session_state.current_lab = lab


# Initialize session state for generated lab
if "current_lab" not in st.session_state:
    # Load basic LAN as initial default
    try:
        accept_lab(ai_generator.load_sample_lab("basic_lan"))
    except Exception:
        st.session_state.current_lab = None


# Sidebar configuration
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/0/08/Cisco_logo_blue_2016.svg", width=120)
    st.title("Settings & Tools")
    
    st.markdown("### 🔑 API Configuration")
    env_api_key = os.getenv("GEMINI_API_KEY", "")
    user_api_key = st.text_input(
        "Gemini API Key",
        value=env_api_key,
        type="password",
        help="Enter your Google Gemini API key or add GEMINI_API_KEY to your .env file."
    )
    
    selected_model = st.text_input(
        "Gemini model ID",
        value=os.getenv("GEMINI_MODEL", ""),
        placeholder="Enter a model ID available to your account",
        help="Use a model ID available to your Gemini account; you can configure GEMINI_MODEL in .env."
    )
    offline_mode = st.checkbox("Use offline generation", value=not bool(env_api_key.strip()))
    st.caption("Offline: LAN chains/rings; 1 router with up to 3 LANs; 2 routers with 2 LANs; single-switch VLANs.")

    st.markdown("---")
    st.markdown("### 📂 Reference Labs")
    st.caption("Quickly test reference blueprints without using API quota:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Basic LAN", width="stretch"):
            accept_lab(ai_generator.load_sample_lab("basic_lan"))
            st.success("Loaded Basic LAN reference lab!")
            st.rerun()
            
        if st.button("Static Routing", width="stretch"):
            accept_lab(ai_generator.load_sample_lab("static_routing"))
            st.success("Loaded Static Routing reference lab!")
            st.rerun()

    with col2:
        if st.button("VLAN Lab", width="stretch"):
            accept_lab(ai_generator.load_sample_lab("vlan"))
            st.success("Loaded VLAN reference lab!")
            st.rerun()

    st.markdown("---")

    # PKT file info in sidebar
    st.markdown("### 📦 Packet Tracer Export")
    st.info(
        "**Download .pkt File**\n\n"
        "Once a lab is generated, use the **📦 Download .pkt** button "
        "to get a ready-to-open Cisco Packet Tracer file with all devices, "
        "cables, and configurations pre-loaded.\n\n"
        "_Verify interfaces, VLANs, routes, and connectivity in Packet Tracer._"
    )

    st.markdown("---")
    st.markdown("### ℹ️ About Project")
    st.info(
        "**Cisco Packet Tracer Lab Generator**\n\n"
        "Generates topology plans with consistency checks, IP schemes, Cisco IOS CLI commands, "
        "and manual testing instructions for Packet Tracer.\n\n"
        "**Supported Lab Types:**\n"
        "- LANs with switch chains or rings\n"
        "- Two isolated VLANs on one switch\n"
        "- One or two routers with static addressing"
    )


# Main Content Area
st.markdown('<div class="main-header">🌐 Cisco Packet Tracer Lab Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated Networking Education Lab Specification Assistant</div>', unsafe_allow_html=True)

# Lab Generator Input Card
with st.container(border=True):
    st.subheader("🛠️ Lab Generation Parameters")
    
    col_type, col_btn = st.columns([3, 1])
    with col_type:
        lab_category = st.selectbox(
            "Select Supported Lab Category",
            options=[
                ("basic_lan", "1. Basic LAN (Single Subnet, Switch + PCs)"),
                ("vlan", "2. VLAN Segmentation (Access Ports, Isolated Subnets)"),
                ("static_routing", "3. Static Routing (Dual Routers, Multi-LAN)"),
                ("custom", "4. Custom Topology / Multi-LAN (Synthesized from Prompt)")
            ],
            format_func=lambda x: x[1]
        )
    
    user_prompt = st.text_area(
        "Custom Instructions / Requirements (Optional)",
        placeholder="e.g. Use subnet 192.168.10.0/24 with 3 workstations'.",
        help="Specify number of PCs, switches, routers, and IP subnets. The engine will tailor the lab to your requirements."
    )
    
    col_submit, col_space = st.columns([2, 5])
    with col_submit:
        generate_clicked = st.button("🚀 Generate Lab", type="primary", width="stretch")

if generate_clicked:
    try:
        with st.spinner("Generating and checking the lab blueprint..."):
            key = "" if offline_mode else user_api_key.strip()
            if key:
                new_lab = ai_generator.generate_lab_with_llm(
                    lab_type=lab_category[0], user_prompt=user_prompt.strip(),
                    api_key=key, model_name=selected_model.strip(),
                )
            else:
                new_lab = ai_generator.synthesize_lab_from_prompt(user_prompt.strip(), lab_category[0])
            accept_lab(new_lab)
        st.rerun()
    except Exception as exc:
        st.error(f"Generation failed: {exc}")
        st.info("The previous lab remains below. Simplify the request or adjust the generation settings.")


# Display Generated Lab
current_lab = st.session_state.current_lab

if current_lab:
    valid, validation_errors = ai_generator.validate_lab_data(current_lab)
    if not valid:
        st.error("This lab failed blueprint validation: " + "; ".join(validation_errors))
        st.stop()
    st.divider()
    generation = current_lab.get("generation", {})
    source = {"gemini": "Google Gemini", "offline": "Offline engine", "reference": "Reference sample"}.get(generation.get("source"), "Unknown")
    st.caption(f"Generation source: {source} | Blueprint consistency checks passed. Verify operation in Packet Tracer.")
    if generation.get("fallback_reason"):
        st.warning(f"Using {source.lower()} because {generation['fallback_reason']}")
    
    # Title & Objective Header
    badge_class = {
        "basic_lan": "badge-lan",
        "vlan": "badge-vlan",
        "static_routing": "badge-routing"
    }.get(current_lab.get("lab_type", ""), "badge-lan")
    
    # ---------------------------------------------------------------
    # Header row: title + download buttons
    # ---------------------------------------------------------------
    col_title, col_dl_txt, col_dl_pkt = st.columns([4, 1, 1])
    with col_title:
        st.markdown(
            f'### <span class="badge {badge_class}">{html.escape(current_lab.get("lab_type", "").replace("_", " "))}</span> '
            f'{html.escape(current_lab.get("title", "Untitled Lab"))}',
            unsafe_allow_html=True
        )
        st.markdown(f"**Objective:** {current_lab.get('objective', 'No objective provided.')}")
        
    # Generate clean descriptive filenames from lab title
    raw_title = current_lab.get("title", current_lab.get("lab_type", "lab"))
    safe_title = "_".join(w.lower() for w in raw_title.split() if w.isalnum()) or "lab"
    clean_filename = f"{safe_title}_guide.txt"
    pkt_filename = f"{safe_title}.pkt"

    with col_dl_txt:
        lab_text_content = ai_generator.export_lab_to_text(current_lab)
        st.download_button(
            label="📥 Guide (.txt)",
            data=lab_text_content,
            file_name=clean_filename,
            mime="text/plain",
            width="stretch",
            help="Download the complete lab guide as a plain-text file."
        )

    with col_dl_pkt:
        # Generate .pkt bytes
        try:
            pkt_bytes = cached_pkt_bytes(current_lab)
            st.download_button(
                label="📦 Open in PT (.pkt)",
                data=pkt_bytes,
                file_name=pkt_filename,
                mime="application/octet-stream",
                width="stretch",
                type="primary",
                help=(
                    "Download a Cisco Packet Tracer (.pkt) file with all devices, "
                    "cables, and configurations pre-loaded. Open directly in Packet Tracer."
                )
            )
        except Exception as pkt_err:
            st.error(f"PKT generation error: {pkt_err}")

    # PKT info callout
    st.markdown(
        '<div class="pkt-info-box">'
        '📦 <strong>New:</strong> Download the <strong>.pkt file</strong> above to open this lab directly in '
        'Cisco Packet Tracer — devices, cables, IP addresses, and Cisco CLI configurations are all '
        'included. Check the saved configuration and run the verification steps in Packet Tracer.'
        '</div>',
        unsafe_allow_html=True
    )

    st.write("")

    # Tabs for organized view
    tab_topo, tab_tables, tab_cli, tab_steps = st.tabs([
        "📊 Network Topology",
        "📋 Addressing & Cabling",
        "💻 Cisco CLI Commands",
        "📝 Lab Steps & Verification"
    ])

    # Tab 1: Network Topology
    with tab_topo:
        st.markdown("#### 🗺️ Visual Network Topology Diagram")
        st.caption("Auto-generated Graphviz schematic showing device models and interconnected interface ports:")
        try:
            dot_source = diagram.generate_topology_dot(current_lab)
            st.graphviz_chart(dot_source, width="stretch")
        except Exception as e:
            st.warning(f"Could not render diagram: {e}")

    # Tab 2: Addressing & Cabling Tables
    with tab_tables:
        col_cables, col_ips = st.columns([1, 1.3])
        
        with col_cables:
            st.markdown("#### 🔌 Physical Cabling Links")
            links = current_lab.get("links", [])
            if links:
                links_df = pd.DataFrame([
                    {
                        "Source Device": l.get("from"),
                        "Source Port": l.get("from_port"),
                        "Target Device": l.get("to"),
                        "Target Port": l.get("to_port")
                    } for l in links
                ])
                st.dataframe(links_df, hide_index=True, width="stretch")
            else:
                st.info("No cabling links defined.")

        with col_ips:
            st.markdown("#### 🌐 IPv4 Addressing Table")
            addressing = current_lab.get("addressing", [])
            if addressing:
                addr_df = pd.DataFrame([
                    {
                        "Device": a.get("device"),
                        "Interface": a.get("interface"),
                        "IP Address": a.get("ip"),
                        "Subnet Mask": a.get("mask"),
                        "Default Gateway": a.get("gateway") or "N/A"
                    } for a in addressing
                ])
                st.dataframe(addr_df, hide_index=True, width="stretch")
            else:
                st.info("No addressing entries defined.")

    # Tab 3: Cisco CLI Commands
    with tab_cli:
        st.markdown("#### ⚙️ Cisco Device Configurations")
        st.caption("Copy and paste these commands into the respective device's CLI tab in Cisco Packet Tracer:")
        
        configs = current_lab.get("configurations", {})
        if configs:
            for dev_id, cmd_text in configs.items():
                with st.expander(f"🖥️ Configuration for **{dev_id}**", expanded=True):
                    st.code(cmd_text, language="cisco")
        else:
            st.info("No custom CLI configurations required.")

    # Tab 4: Step-by-Step Instructions & Verification
    with tab_steps:
        col_inst, col_verif = st.columns(2)
        
        with col_inst:
            st.markdown("#### 🔨 Setup Instructions")
            instructions = current_lab.get("instructions", [])
            for idx, inst in enumerate(instructions, 1):
                st.markdown(f"**{idx}.** {inst}")
                
        with col_verif:
            st.markdown("#### 🧪 Verification & Checklist")
            verification = current_lab.get("verification", [])
            for idx, test in enumerate(verification, 1):
                st.checkbox(f"Step {idx}: {test}", key=f"verif_check_{idx}")

else:
    st.info("Select a lab type above and click 'Generate Lab' or pick a pre-tested lab from the sidebar.")
