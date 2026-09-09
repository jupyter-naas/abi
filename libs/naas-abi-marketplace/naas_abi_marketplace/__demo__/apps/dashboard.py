"""
ABI Interface Dashboard
Central hub showing all running Streamlit interfaces
"""

from datetime import datetime

import requests
import streamlit as st

st.set_page_config(
    page_title="ABI Interface Dashboard", 
    page_icon="🎛️", 
    layout="wide"
)

st.title("🎛️ ABI Interface Dashboard")
st.markdown("**Central hub for all ABI user interfaces**")

# Interface definitions
interfaces: list[dict[str, str | int | list[str]]] = [
    {
        "name": "Chat Interface (API)",
        "description": "API-based chat interface with multi-agent support",
        "port": 8501,
        "category": "Marketplace Apps",
        "icon": "🤖",
        "features": ["Multi-agent chat", "API-based", "@mentions", "Thread persistence"]
    },
    {
        "name": "Chat Interface (MCP)",
        "description": "Model Context Protocol compliant chat interface",
        "port": 8502,
        "category": "Marketplace Apps", 
        "icon": "🚀",
        "features": ["MCP protocol", "Async communication", "Agent buttons", "Clean UI"]
    },
    {
        "name": "Table Mode",
        "description": "Structured data view with sorting and filtering",
        "port": 8503,
        "category": "Marketplace Apps",
        "icon": "📊",
        "features": ["Data tables", "Sorting", "Filtering", "Pagination"]
    },
    {
        "name": "Kanban Mode", 
        "description": "Task management board with drag-and-drop",
        "port": 8504,
        "category": "Marketplace Apps",
        "icon": "📋",
        "features": ["Task boards", "Drag & drop", "Status tracking", "Analytics"]
    },
    {
        "name": "Ontology Mode",
        "description": "Knowledge graph visualization and exploration",
        "port": 8505,
        "category": "Marketplace Apps",
        "icon": "🕸️",
        "features": ["Graph visualization", "TTL files", "Interactive exploration", "PyVis"]
    },
    {
        "name": "Financial Dashboard",
        "description": "Business metrics and financial analytics",
        "port": 8506,
        "category": "Marketplace Domains",
        "icon": "💰",
        "features": ["Financial metrics", "Charts", "KPIs", "Analytics"]
    },
    {
        "name": "Scheduling Interface",
        "description": "Calendar and time management tools",
        "port": 8507,
        "category": "Marketplace Domains", 
        "icon": "📅",
        "features": ["Calendar view", "Scheduling", "Time management", "Events"]
    },
    {
        "name": "Project Management",
        "description": "Project tracking and team collaboration",
        "port": 8508,
        "category": "Marketplace Domains",
        "icon": "📈",
        "features": ["Project tracking", "Team collaboration", "Milestones", "Reports"]
    },
    {
        "name": "Account Reconciliation",
        "description": "Financial reconciliation workflows",
        "port": 8509,
        "category": "Marketplace Domains",
        "icon": "🔍",
        "features": ["Account matching", "Reconciliation", "Workflows", "audit trails"]
    },
    {
        "name": "Network Visualization",
        "description": "Interactive network and graph visualization",
        "port": 8510,
        "category": "Marketplace Apps",
        "icon": "🌐",
        "features": ["Network graphs", "Interactive viz", "YAML config", "Graph analysis"]
    }
]

def check_interface_status(port):
    """Check if interface is running"""
    try:
        response = requests.get(f"http://localhost:{port}", timeout=2)
        return "🟢 Online" if response.status_code == 200 else "🟡 Issues"
    except Exception:
        return "🔴 Offline"

# Group by category
categories: dict[str, list[dict[str, str | int | list[str]]]] = {}
for interface in interfaces:
    category = str(interface["category"])
    if category not in categories:
        categories[category] = []
    categories[category].append(interface)

# Display interfaces by category
for category, category_interfaces in categories.items():
    st.header(f"📁 {category} Interfaces")
    
    cols = st.columns(2)
    for i, interface in enumerate(category_interfaces):
        with cols[i % 2]:
            with st.container():
                st.subheader(f"{interface['icon']} {interface['name']}")
                st.write(interface['description'])
                
                # Status and link
                status = check_interface_status(interface['port'])
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.write(f"**Status:** {status}")
                with col2:
                    st.write(f"**Port:** {interface['port']}")
                
                # Features
                st.write("**Features:**")
                features = interface['features']
                if isinstance(features, list):
                    for feature in features:
                        st.write(f"• {feature}")
                
                # Launch button
                if st.button(f"🚀 Launch {interface['name']}", key=f"launch_{interface['port']}"):
                    st.write(f"Opening http://localhost:{interface['port']}")
                    # Note: st.link_button would be better but requires newer Streamlit
                
                st.markdown(f"**Direct Link:** [http://localhost:{interface['port']}](http://localhost:{interface['port']})")
                st.divider()

# System status
st.header("🔧 System Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Interfaces", len(interfaces))

with col2:
    online_count = sum(1 for interface in interfaces if "🟢" in check_interface_status(interface['port']))
    st.metric("Online Interfaces", online_count)

with col3:
    st.metric("Categories", len(categories))

# Quick actions
st.header("⚡ Quick Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 Refresh Status"):
        st.rerun()

with col2:
    if st.button("📊 View All Tables"):
        st.write("Opening all table-based interfaces...")

with col3:
    if st.button("💬 Open All Chat"):
        st.write("Opening all chat interfaces...")

# Footer
st.markdown("---")
st.markdown(f"**ABI Interface Dashboard** | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.markdown("**🎛️ Central Control Hub** | Powered by NaasAI")
