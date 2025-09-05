# """
# ABI Marketplace - Minimalist Design
# Apple-level clean interface for apps and modules
# """

# import streamlit as st
# import requests
# from pathlib import Path
# from typing import Dict, List, Any

# # Configure page
# st.set_page_config(
#     page_title="ABI Marketplace", 
#     page_icon="🏪", 
#     layout="wide",
#     initial_sidebar_state="collapsed"
# )

# # Minimal CSS - Apple-inspired
# st.markdown("""
# <style>
# /* Updated spacing v2 */
#     .main > div {
#         padding-top: 2rem;
#         max-width: 1200px;
#         margin: 0 auto;
#     }
    
#     .marketplace-header {
#         text-align: center;
#         margin-bottom: 3rem;
#     }
    
#     .marketplace-title {
#         font-size: 2.5rem;
#         font-weight: 300;
#         color: #1d1d1f;
#         margin-bottom: 0.5rem;
#     }
    
#     .marketplace-subtitle {
#         font-size: 1.2rem;
#         color: #86868b;
#         font-weight: 400;
#     }
    
#     .search-container {
#         margin-bottom: 2rem;
#     }
    
#     .search-input {
#         width: 100%;
#         padding: 12px 20px;
#         font-size: 1.1rem;
#         border: 1px solid #d2d2d7;
#         border-radius: 12px;
#         background: #f5f5f7;
#         outline: none;
#         transition: all 0.2s ease;
#     }
    
#     .search-input:focus {
#         border-color: #007aff;
#         background: white;
#         box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
#     }
    
#     .tabs-container {
#         display: flex;
#         justify-content: center;
#         margin-bottom: 2rem;
#         border-bottom: 1px solid #d2d2d7;
#     }
    
#     .tab-button {
#         padding: 12px 24px;
#         background: none;
#         border: none;
#         font-size: 1rem;
#         color: #86868b;
#         cursor: pointer;
#         border-bottom: 2px solid transparent;
#         transition: all 0.2s ease;
#     }
    
#     .tab-button.active {
#         color: #007aff;
#         border-bottom-color: #007aff;
#     }
    
#     .tab-button:hover {
#         color: #1d1d1f;
#     }
    
#     .card-container {
#         margin-bottom: 2.5rem;
#     }
    
#     .card {
#         background: white;
#         border-radius: 12px;
#         padding: 2rem;
#         border: 1px solid #f0f0f0;
#         transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
#         cursor: pointer;
#         height: 320px;
#         display: flex;
#         flex-direction: column;
#         position: relative;
#     }
    
#     .card:hover {
#         transform: translateY(-2px);
#         box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
#         border-color: #e5e5ea;
#     }
    
#     .card-icon {
#         font-size: 2.5rem;
#         margin-bottom: 1rem;
#         display: block;
#         height: 3.5rem;
#         display: flex;
#         align-items: center;
#         justify-content: flex-start;
#     }
    
#     .card-icon img {
#         width: 48px;
#         height: 48px;
#         border-radius: 8px;
#         object-fit: cover;
#     }
    
#     .card-tag {
#         position: absolute;
#         top: 1rem;
#         right: 1rem;
#         background: #f5f5f7;
#         color: #1d1d1f;
#         padding: 4px 8px;
#         border-radius: 6px;
#         font-size: 0.75rem;
#         font-weight: 500;
#         text-transform: uppercase;
#         letter-spacing: 0.5px;
#     }
    
#     .card-tag.app {
#         background: #007AFF;
#         color: white;
#     }
    
#     .card-tag.module {
#         background: #34C759;
#         color: white;
#     }
    
#     .card-title {
#         font-size: 1.3rem;
#         font-weight: 600;
#         color: #000000 !important;
#         margin-bottom: 2rem;
#         line-height: 1.2;
#         height: 2.6rem;
#         overflow: hidden;
#         display: -webkit-box;
#         -webkit-line-clamp: 2;
#         -webkit-box-orient: vertical;
#     }
    
#     .card-description {
#         font-size: 0.95rem;
#         color: #424245;
#         line-height: 1.4;
#         margin-bottom: 1rem;
#         height: 4.2rem;
#         overflow: hidden;
#         display: -webkit-box;
#         -webkit-line-clamp: 3;
#         -webkit-box-orient: vertical;
#     }
    
#     .card-status {
#         display: flex;
#         align-items: center;
#         justify-content: space-between;
#         margin-bottom: 1rem;
#         height: 1.5rem;
#     }
    
#     .card-status span {
#         color: #1d1d1f !important;
#         font-weight: 500;
#         font-size: 0.9rem;
#     }
    
#     .card-actions {
#         margin-top: auto;
#         padding-top: 1.5rem;
#         border-top: 1px solid #f5f5f7;
#     }
    
#     .status-dot {
#         width: 8px;
#         height: 8px;
#         border-radius: 50%;
#         margin-right: 6px;
#     }
    
#     .status-running { background: #30d158; }
#     .status-stopped { background: #ff3b30; }
#     .status-available { background: #ff9500; }
    
#     .launch-button {
#         background: #007aff;
#         color: white;
#         border: none;
#         padding: 8px 16px;
#         border-radius: 8px;
#         font-size: 0.9rem;
#         font-weight: 500;
#         cursor: pointer;
#         transition: all 0.2s ease;
#     }
    
#     .launch-button:hover {
#         background: #0056cc;
#     }
    
#     .launch-button:disabled {
#         background: #d1d1d6;
#         cursor: not-allowed;
#     }
    
#     .results-count {
#         text-align: center;
#         color: #86868b;
#         margin-bottom: 1rem;
#         font-size: 0.95rem;
#     }
    
#     .card-button {
#         flex: 1;
#         padding: 8px 16px;
#         border: 1px solid #d2d2d7;
#         border-radius: 8px;
#         background: #f5f5f7;
#         color: #1d1d1f;
#         font-size: 0.9rem;
#         font-weight: 500;
#         cursor: pointer;
#         transition: all 0.2s ease;
#         text-align: center;
#         text-decoration: none;
#         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
#     }
    
#     .card-button.primary {
#         background: #1d1d1f;
#         color: white;
#         border-color: #1d1d1f;
#     }
    
#     .card-button:hover {
#         background: #e8e8ed;
#         border-color: #c7c7cc;
#     }
    
#     .card-button.primary:hover {
#         background: #424245;
#     }
    
#     .card-button:disabled {
#         background: #f2f2f7;
#         color: #86868b;
#         cursor: not-allowed;
#         border-color: #e5e5ea;
#     }
# </style>
# """, unsafe_allow_html=True)

# def get_app_status(port: int) -> str:
#     """Check if app is running"""
#     try:
#         response = requests.get(f"http://localhost:{port}", timeout=2)
#         return "running" if response.status_code == 200 else "stopped"
#     except Exception:
#         return "stopped"

# def load_modules_from_path(path: Path, module_type: str = "module") -> List[Dict[str, Any]]:
#     """Helper function to load modules from a given path"""
#     modules = []
    
#     if path.exists():
#         for module_dir in path.iterdir():
#             if module_dir.is_dir() and not module_dir.name.startswith("__"):
#                 # Try to load avatar URL and description from agent file
#                 avatar_url = None
#                 description = None
#                 agent_path = module_dir / "agents"
#                 if agent_path.exists():
#                     for agent_file in agent_path.glob("*Agent.py"):
#                         try:
#                             # Read the agent file to extract AVATAR_URL and DESCRIPTION
#                             with open(agent_file, 'r') as f:
#                                 content = f.read()
#                                 for line in content.split('\n'):
#                                     line = line.strip()
#                                     if line.startswith('AVATAR_URL = '):
#                                         avatar_url = line.split('=', 1)[1].strip().strip('"\'')
#                                     elif line.startswith('DESCRIPTION = '):
#                                         description = line.split('=', 1)[1].strip().strip('"\'')
#                             if avatar_url and description:
#                                 break
#                         except Exception:
#                             continue
                
#                 # Fallback values
#                 fallback_icon = {"chatgpt": "🤖", "claude": "🎭", "gemini": "💎", "grok": "🚀", 
#                                 "llama": "🦙", "mistral": "🌪️", "deepseek": "🔍", "abi": "⭐"}.get(module_dir.name, "🧠")
#                 fallback_description = f"AI module with {module_dir.name} capabilities"
                
#                 # Format name for domain experts (replace hyphens with spaces and title case)
#                 if "domain" in module_type.lower():
#                     name = module_dir.name.replace("-", " ").title()
#                 else:
#                     name = module_dir.name.title()
                
#                 modules.append({
#                     "name": name,
#                     "type": module_type, 
#                     "description": description if description else fallback_description,
#                     "icon": avatar_url if avatar_url else fallback_icon,
#                     "status": "available"
#                 })
    
#     return modules

# def get_modules() -> List[Dict[str, Any]]:
#     """Get available modules"""
#     modules = []
    
#     # Core modules
#     core_path = Path("src/core/modules")
#     modules.extend(load_modules_from_path(core_path, "core-module"))
    
#     # Custom modules
#     custom_path = Path("src/custom/modules")
#     modules.extend(load_modules_from_path(custom_path, "custom-module"))
    
#     # Domain expert modules
#     domain_path = Path("src/marketplace/modules/domains/modules")
#     modules.extend(load_modules_from_path(domain_path, "domain-expert"))
    
#     # Marketplace application modules (disabled ones)
#     marketplace_apps_path = Path("src/marketplace/modules/applications")
#     modules.extend(load_modules_from_path(marketplace_apps_path, "marketplace-app"))
    
#     return modules

# # Apps data
# apps_data: list[dict[str, str | int]] = [
#     {"name": "Dashboard", "port": 8500, "icon": "🎛️", "description": "Central control hub with system monitoring"},
#     {"name": "Chat API", "port": 8511, "icon": "💬", "description": "API-based chat interface with multi-agent support"},
#     {"name": "Table Mode", "port": 8503, "icon": "📊", "description": "Advanced data table interface with filtering"},
#     {"name": "Kanban Mode", "port": 8504, "icon": "📋", "description": "Project management with kanban boards"},
#     {"name": "Ontology Mode", "port": 8505, "icon": "🕸️", "description": "Knowledge graph visualization"},
#     {"name": "Financial Dashboard", "port": 8506, "icon": "💰", "description": "Financial analytics and KPIs"},
#     {"name": "Calendar", "port": 8507, "icon": "📅", "description": "Advanced scheduling interface"},
#     {"name": "Project Board", "port": 8508, "icon": "📈", "description": "Enterprise project tracking"},
#     {"name": "Reconciliation", "port": 8509, "icon": "🧮", "description": "Financial reconciliation tool"},
#     {"name": "Network Viz", "port": 8510, "icon": "🌐", "description": "Interactive network visualization"}
# ]

# # Add status to apps
# for app in apps_data:
#     app["status"] = get_app_status(int(app["port"]))
#     app["type"] = "app"

# # Header
# st.markdown("""
# <div class="marketplace-header">
#     <h1 class="marketplace-title">ABI Marketplace</h1>
#     <p class="marketplace-subtitle">Discover and launch AI applications and modules</p>
# </div>
# """, unsafe_allow_html=True)

# # Search
# search_query = st.text_input("Search", placeholder="Search apps and modules...", key="search", label_visibility="collapsed")

# # Tabs
# col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
# with col1:
#     if st.button("All", key="tab_all", use_container_width=True):
#         st.session_state.active_tab = "all"
# with col2:
#     if st.button("Apps", key="tab_apps", use_container_width=True):
#         st.session_state.active_tab = "apps"
# with col3:
#     if st.button("Modules", key="tab_modules", use_container_width=True):
#         st.session_state.active_tab = "modules"
# with col4:
#     if st.button("Running", key="tab_running", use_container_width=True):
#         st.session_state.active_tab = "running"

# # Initialize active tab
# if "active_tab" not in st.session_state:
#     st.session_state.active_tab = "all"

# # Get all items
# all_items = apps_data + get_modules()

# # Filter items
# filtered_items = all_items

# # Apply search filter
# if search_query:
#     filtered_items = [item for item in filtered_items 
#                      if search_query.lower() in item["name"].lower() 
#                      or search_query.lower() in item["description"].lower()]

# # Apply tab filter
# if st.session_state.active_tab == "apps":
#     filtered_items = [item for item in filtered_items if item["type"] == "app"]
# elif st.session_state.active_tab == "modules":
#     filtered_items = [item for item in filtered_items if item["type"] in ["module", "core-module", "domain-expert", "custom-module", "marketplace-app"]]
# elif st.session_state.active_tab == "running":
#     filtered_items = [item for item in filtered_items if item.get("status") == "running"]

# # Results count
# if search_query or st.session_state.active_tab != "all":
#     st.markdown(f'<div class="results-count">{len(filtered_items)} results</div>', unsafe_allow_html=True)

# # Cards grid - proper Streamlit grid with spacing
# if filtered_items:
#     cols_per_row = 3
#     for i in range(0, len(filtered_items), cols_per_row):
#         cols = st.columns(cols_per_row, gap="large")
        
#         for j, col in enumerate(cols):
#             if i + j < len(filtered_items):
#                 item = filtered_items[i + j]
                
#                 with col:
#                     # Card container with proper spacing
#                     st.markdown('<div class="card-container">', unsafe_allow_html=True)
                    
#                     # Card content
#                     # Determine if icon is URL or emoji
#                     icon_html = f'<img src="{item["icon"]}" alt="{item["name"]}">' if item["icon"].startswith("http") else item["icon"]
                    
#                     # Determine tag text and class
#                     tag_text = "APP" if item["type"] == "app" else "MODULE"
#                     tag_class = "app" if item["type"] == "app" else "module"
                    
#                     card_html = f"""
#                     <div class="card">
#                         <div class="card-tag {tag_class}">{tag_text}</div>
#                         <span class="card-icon">{icon_html}</span>
#                         <h3 class="card-title">{item["name"]}</h3>
#                         <p class="card-description">{item["description"]}</p>
#                         <div class="card-status">
#                     """
                    
#                     if item["type"] == "app":
#                         status = item["status"]
#                         status_text = "🟢 Running" if status == "running" else "🔴 Stopped"
#                         card_html += f'<span><span class="status-dot status-{status}"></span>{status_text}</span>'
#                     else:
#                         card_html += '<span><span class="status-dot status-available"></span>🟡 Available</span>'
                    
#                     card_html += """</div>
#                         <div class="card-actions">
#                     """
                    
#                     st.markdown(card_html, unsafe_allow_html=True)
                    
#                     # Single action button that changes based on status
#                     if item["type"] == "app":
#                         button_label = "Launch"
#                         if item["status"] == "running":
#                             button_key = f"launch_running_{item['port']}"
#                         else:
#                             button_key = f"launch_stopped_{item['port']}"
#                     else:
#                         button_label = "Install"
#                         button_key = f"install_{item['name']}"
                    
#                     if st.button(button_label, key=button_key, use_container_width=True):
#                         if item["type"] == "app":
#                             if item["status"] == "running":
#                                 # Launch running app in new tab
#                                 import webbrowser
#                                 webbrowser.open(f"http://localhost:{item['port']}")
#                             else:
#                                 # Start the app and open it
#                                 import subprocess
#                                 import os
#                                 import time
#                                 import threading
                                
#                                 # Map ports to their corresponding app files
#                                 app_files = {
#                                     8500: "apps/dashboard.py",
#                                     8511: "apps/chat-mode/chat_interface_api.py",
#                                     8503: "apps/table-mode/table_interface.py",
#                                     8504: "apps/kanban-mode/kanban_interface.py",
#                                     8505: "apps/ontology-mode/ontology_interface.py",
#                                     8506: "modules/domains/apps/dashboard/financial_dashboard.py",
#                                     8507: "modules/domains/apps/calendar/scheduling_interface.py",
#                                     8508: "modules/domains/apps/project-board/project_management.py",
#                                     8509: "modules/domains/apps/reconciliation/account_reconciliation.py",
#                                     8510: "apps/network-vizualization/streamlit.py"
#                                 }
                                
#                                 app_file = app_files.get(item['port'])
#                                 if app_file and os.path.exists(app_file):
#                                     try:
#                                         # Start the app in background
#                                         subprocess.Popen([
#                                             "streamlit", "run", app_file,
#                                             "--server.port", str(item['port']),
#                                             "--server.headless", "true"
#                                         ], cwd=os.path.dirname(os.path.abspath(__file__)))
                                        
#                                         # Open the app in a new tab after a short delay (no rerun interruption)
#                                         def open_after_delay():
#                                             time.sleep(4)  # Slightly longer to ensure app is ready
#                                             webbrowser.open(f"http://localhost:{item['port']}")
                                        
#                                         threading.Thread(target=open_after_delay, daemon=True).start()
#                                         # Don't call st.rerun() here to avoid interrupting the flow
#                                     except Exception as e:
#                                         st.error(f"❌ Failed to start {item['name']}: {str(e)}")
#                                 else:
#                                     st.error(f"❌ App file not found for {item['name']}")
#                         else:
#                             # Module installation
#                             st.success(f"Installing {item['name']}...")
                    
#                     # Close card
#                     st.markdown("</div></div></div>", unsafe_allow_html=True)

# else:
#     st.markdown("""
#     <div style="text-align: center; padding: 3rem; color: #86868b;">
#         <h3>No results found</h3>
#         <p>Try adjusting your search or filters</p>
#     </div>
#     """, unsafe_allow_html=True)

# # Footer
# st.markdown("""
# <div style="text-align: center; padding: 2rem; color: #86868b; border-top: 1px solid #f0f0f0; margin-top: 2rem;">
#     <p>ABI Marketplace • Simple • Clean • Functional</p>
# </div>
# """, unsafe_allow_html=True)
