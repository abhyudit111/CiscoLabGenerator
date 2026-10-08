"""diagram.py: Graphviz topology renderer for Cisco Packet Tracer Lab Generator."""

from typing import Any, Dict


def generate_topology_dot(lab_data: Dict[str, Any]) -> str:
    """Generate a Graphviz DOT string representing the network topology.
    
    Compatible directly with Streamlit's st.graphviz_chart.
    """
    devices = lab_data.get("devices", [])
    links = lab_data.get("links", [])
    addressing = lab_data.get("addressing", [])
    
    # Map device ID to IP addresses for helpful node annotations
    device_ips: Dict[str, list[str]] = {}
    for addr in addressing:
        dev_id = addr.get("device")
        ip = addr.get("ip")
        if dev_id and ip:
            device_ips.setdefault(dev_id, []).append(f"{addr.get('interface', '')}: {ip}")
            
    dot_lines = [
        "graph NetworkTopology {",
        "    // Graph configuration",
        "    layout=dot;",
        "    rankdir=LR;",
        "    bgcolor=\"transparent\";",
        "    node [fontname=\"Helvetica, Arial, sans-serif\", fontsize=11, margin=\"0.15,0.1\"];",
        "    edge [fontname=\"Helvetica, Arial, sans-serif\", fontsize=9, color=\"#374151\", penwidth=1.8];",
        "",
        "    // Subgraph styling and device nodes"
    ]
    
    for dev in devices:
        dev_id = dev.get("id", "Unknown")
        dev_type = dev.get("type", "pc").lower()
        model = dev.get("model", "")
        
        # Color palettes and shapes based on device type
        if "router" in dev_type:
            shape = "box3d"
            fillcolor = "#E0F2FE"  # Light blue
            color = "#0284C7"      # Cisco router blue
            icon = "📡 Router"
        elif "switch" in dev_type:
            shape = "box"
            fillcolor = "#DCFCE7"  # Light green
            color = "#16A34A"      # Switch green
            icon = "🔀 Switch"
        elif "server" in dev_type:
            shape = "box"
            fillcolor = "#FEF3C7"  # Light amber
            color = "#D97706"
            icon = "🖥️ Server"
        else:  # PC / Host
            shape = "ellipse"
            fillcolor = "#F3F4F6"  # Light gray
            color = "#4B5563"
            icon = "💻 PC"
            
        label_parts = [f"{icon} {dev_id}"]
        if model:
            label_parts.append(f"Model: {model}")
            
        ips = device_ips.get(dev_id, [])
        if ips and len(ips) <= 2:
            label_parts.append("\\n" + "\\n".join(ips))
            
        full_label = "\\n".join(label_parts)
        
        dot_lines.append(
            f'    "{dev_id}" ['
            f'shape="{shape}", '
            f'style="filled,rounded", '
            f'fillcolor="{fillcolor}", '
            f'color="{color}", '
            f'penwidth=2, '
            f'label="{full_label}"'
            f'];'
        )
        
    dot_lines.append("\n    // Physical Cable Links")
    
    seen_links = set()
    for link in links:
        from_dev = link.get("from", "")
        to_dev = link.get("to", "")
        from_port = link.get("from_port", "")
        to_port = link.get("to_port", "")
        
        if not from_dev or not to_dev:
            continue
            
        # Avoid duplicate rendering in undirected graph
        link_key = tuple(sorted([f"{from_dev}:{from_port}", f"{to_dev}:{to_port}"]))
        if link_key in seen_links:
            continue
        seen_links.add(link_key)
        
        # Port labels at head and tail
        dot_lines.append(
            f'    "{from_dev}" -- "{to_dev}" ['
            f'taillabel="{from_port}  ", '
            f'headlabel="  {to_port}", '
            f'labeldistance=2.4, '
            f'labelangle=25, '
            f'labelfontcolor="#1E293B"'
            f'];'
        )
        
    dot_lines.append("}")
    return "\n".join(dot_lines)
