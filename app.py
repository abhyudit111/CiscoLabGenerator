"""app.py: Streamlit Web UI for Cisco Packet Tracer LLM Lab Generator."""

import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

import ai_generator
import diagram

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
</style>
""", unsafe_allow_html=True)


# Initialize session state for generated lab
if "current_lab" not in st.session_state:
    # Load basic LAN as initial default
    try:
        st.session_state.current_lab = ai_generator.load_sample_lab("basic_lan")
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
    
    selected_model = st.selectbox(
        "Model",
        ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
        index=0,
        help="Select Gemini model for lab generation."
    )

    st.markdown("---")
    st.markdown("### 📂 Pre-tested Reference Labs")
    st.caption("Quickly test reference blueprints without using API quota:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Basic LAN", use_container_width=True):
            st.session_state.current_lab = ai_generator.load_sample_lab("basic_lan")
            st.success("Loaded Basic LAN reference lab!")
            st.rerun()
            
        if st.button("Static Routing", use_container_width=True):
            st.session_state.current_lab = ai_generator.load_sample_lab("static_routing")
            st.success("Loaded Static Routing reference lab!")
            st.rerun()

    with col2:
        if st.button("VLAN Lab", use_container_width=True):
            st.session_state.current_lab = ai_generator.load_sample_lab("vlan")
            st.success("Loaded VLAN reference lab!")
            st.rerun()

    st.markdown("---")
    st.markdown("### ℹ️ About Project")
    st.info(
        "**Cisco Packet Tracer Lab Generator**\n\n"
        "Generates verified topology plans, IP schemes, Cisco IOS CLI commands, "
        "and manual testing instructions for Packet Tracer.\n\n"
        "**Supported Lab Types:**\n"
        "- Basic LAN (1 Switch, 3-4 PCs)\n"
        "- VLANs (1 Switch, 4 PCs, VLAN 10/20)\n"
        "- Static Routing (2 Routers, 2 Switches, 4 PCs)"
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
                ("static_routing", "3. Static Routing (Dual Routers, Multi-LAN)")
            ],
            format_func=lambda x: x[1]
        )
    
    user_prompt = st.text_area(
        "Custom Instructions / Requirements (Optional)",
        placeholder="e.g., 'Use subnet 192.168.10.0/24 with 3 workstations' or 'Name VLANs HR and Finance'.",
        help="Leave empty to use standardized educational defaults."
    )
    
    col_submit, col_space = st.columns([2, 5])
    with col_submit:
        generate_clicked = st.button("🚀 Generate Lab", type="primary", use_container_width=True)

if generate_clicked:
    lab_key = lab_category[0]
    api_key_to_use = user_api_key.strip() or env_api_key.strip()
    
    if not api_key_to_use:
        st.warning(
            "⚠️ No Gemini API key provided. Loading pre-tested reference template for this category instead. "
            "To generate with live LLM, enter your Gemini API key in the sidebar."
        )
        try:
            st.session_state.current_lab = ai_generator.load_sample_lab(lab_key)
            st.rerun()
        except Exception as e:
            st.error(f"Error loading sample lab: {e}")
    else:
        with st.spinner("🤖 Communicating with LLM and validating lab network specification..."):
            try:
                new_lab = ai_generator.generate_lab_with_llm(
                    lab_type=lab_key,
                    user_prompt=user_prompt,
                    api_key=api_key_to_use,
                    model_name=selected_model
                )
                st.session_state.current_lab = new_lab
                st.success("✅ Lab generated and verified successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Generation Failed: {str(e)}")
                st.info("Tip: You can load the reference sample lab from the sidebar anytime.")


# Display Generated Lab
current_lab = st.session_state.current_lab

if current_lab:
    st.divider()
    
    # Title & Objective Header
    badge_class = {
        "basic_lan": "badge-lan",
        "vlan": "badge-vlan",
        "static_routing": "badge-routing"
    }.get(current_lab.get("lab_type", ""), "badge-lan")
    
    col_title, col_download = st.columns([4, 1.2])
    with col_title:
        st.markdown(
            f'### <span class="badge {badge_class}">{current_lab.get("lab_type", "").replace("_", " ")}</span> '
            f'{current_lab.get("title", "Untitled Lab")}',
            unsafe_allow_html=True
        )
        st.markdown(f"**Objective:** {current_lab.get('objective', 'No objective provided.')}")
        
    with col_download:
        lab_text_content = ai_generator.export_lab_to_text(current_lab)
        clean_filename = f"{current_lab.get('lab_type', 'lab')}_guide.txt"
        st.download_button(
            label="📥 Download Guide (.txt)",
            data=lab_text_content,
            file_name=clean_filename,
            mime="text/plain",
            use_container_width=True
        )

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
            st.graphviz_chart(dot_source, use_container_width=True)
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
                st.dataframe(links_df, hide_index=True, use_container_width=True)
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
                st.dataframe(addr_df, hide_index=True, use_container_width=True)
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
