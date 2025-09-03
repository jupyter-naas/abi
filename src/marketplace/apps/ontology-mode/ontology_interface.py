"""
Ontology Mode Interface - Interactive Knowledge Graph Visualization
Displays all TTL files from the platform using PyVis/VisJS
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from rdflib import Graph, URIRef, Literal, BNode
import networkx as nx  # type: ignore
from pyvis.network import Network  # type: ignore
import tempfile
import os
from collections import defaultdict

# Page config
st.set_page_config(
    page_title="ABI Ontology Explorer", 
    page_icon="🕸️", 
    layout="wide"
)

# Initialize session state
if 'ontology_data' not in st.session_state:
    st.session_state.ontology_data = None
if 'selected_files' not in st.session_state:
    st.session_state.selected_files = []
if 'graph_html' not in st.session_state:
    st.session_state.graph_html = None

def discover_ttl_files():
    """Discover all TTL files in the platform"""
    project_root = Path(__file__).parent.parent.parent.parent
    ttl_files = []
    
    # Search for TTL files
    for ttl_file in project_root.rglob("*.ttl"):
        # Skip hidden directories and files
        if any(part.startswith('.') for part in ttl_file.parts):
            continue
            
        relative_path = ttl_file.relative_to(project_root)
        file_info = {
            'path': str(relative_path),
            'full_path': str(ttl_file),
            'name': ttl_file.name,
            'module': get_module_from_path(str(relative_path)),
            'category': get_category_from_path(str(relative_path)),
            'size': ttl_file.stat().st_size if ttl_file.exists() else 0
        }
        ttl_files.append(file_info)
    
    return sorted(ttl_files, key=lambda x: x['path'])

def get_module_from_path(path):
    """Extract module name from file path"""
    parts = path.split('/')
    if 'modules' in parts:
        idx = parts.index('modules')
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return 'core'

def get_category_from_path(path):
    """Extract category from file path"""
    if 'domain-experts' in path:
        return 'Domain Experts'
    elif 'core/modules' in path:
        return 'Core Modules'
    elif 'marketplace' in path:
        return 'Marketplace'
    else:
        return 'Other'

@st.cache_data
def parse_ttl_file(file_path):
    """Parse a TTL file and extract triples"""
    try:
        g = Graph()
        g.parse(file_path, format='turtle')
        
        triples = []
        for subj, pred, obj in g:
            triple = {
                'subject': str(subj),
                'predicate': str(pred),
                'object': str(obj),
                'subject_type': get_node_type(subj),
                'object_type': get_node_type(obj)
            }
            triples.append(triple)
        
        return {
            'triples': triples,
            'namespaces': dict(g.namespaces()),
            'count': len(triples)
        }
    except Exception as e:
        return {
            'error': str(e),
            'triples': [],
            'namespaces': {},
            'count': 0
        }

def get_node_type(node):
    """Determine the type of RDF node"""
    if isinstance(node, URIRef):
        return 'URI'
    elif isinstance(node, Literal):
        return 'Literal'
    elif isinstance(node, BNode):
        return 'BlankNode'
    else:
        return 'Unknown'

def create_knowledge_graph(selected_files, max_nodes=500):
    """Create an interactive knowledge graph from selected TTL files"""
    
    # Create NetworkX graph
    G = nx.Graph()
    
    # Color scheme for different categories
    category_colors = {
        'Domain Experts': '#FF6B6B',
        'Core Modules': '#4ECDC4', 
        'Marketplace': '#45B7D1',
        'Other': '#96CEB4'
    }
    
    all_triples = []
    file_stats = {}
    
    # Process selected files
    for file_info in selected_files:
        if len(all_triples) > max_nodes * 3:  # Rough limit
            break
            
        parsed = parse_ttl_file(file_info['full_path'])
        if 'error' not in parsed:
            all_triples.extend(parsed['triples'])
            file_stats[file_info['name']] = {
                'triples': parsed['count'],
                'category': file_info['category']
            }
    
    # Build graph from triples
    node_counts = defaultdict(int)
    
    for triple in all_triples[:max_nodes * 3]:  # Limit processing
        subj = triple['subject']
        obj = triple['object']
        pred = triple['predicate']
        
        # Skip literals for cleaner visualization
        if triple['object_type'] == 'Literal':
            continue
            
        # Add nodes
        if subj not in G.nodes():
            G.add_node(subj)
            node_counts[subj] = 0
        if obj not in G.nodes():
            G.add_node(obj)
            node_counts[obj] = 0
            
        # Add edge
        G.add_edge(subj, obj, label=get_short_name(pred))
        node_counts[subj] += 1
        node_counts[obj] += 1
        
        if len(G.nodes()) > max_nodes:
            break
    
    # Create PyVis network
    net = Network(
        height="600px", 
        width="100%", 
        bgcolor="#1e1e1e", 
        font_color="white",
        directed=True
    )
    
    # Configure physics
    net.set_options("""
    var options = {
      "physics": {
        "enabled": true,
        "stabilization": {"iterations": 100},
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 95,
          "springConstant": 0.04,
          "damping": 0.09
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200
      }
    }
    """)
    
    # Add nodes with colors and sizes based on connections
    for node in G.nodes():
        short_name = get_short_name(node)
        size = min(10 + node_counts[node] * 2, 50)  # Size based on connections
        
        # Determine color based on namespace or type
        color = get_node_color(node, category_colors)
        
        net.add_node(
            node, 
            label=short_name,
            title=f"{short_name}\nConnections: {node_counts[node]}\nFull URI: {node}",
            size=size,
            color=color
        )
    
    # Add edges
    for edge in G.edges(data=True):
        net.add_edge(
            edge[0], 
            edge[1], 
            label=edge[2].get('label', ''),
            title=edge[2].get('label', ''),
            color={'color': '#848484'}
        )
    
    return net, file_stats, len(G.nodes()), len(G.edges())

def get_short_name(uri):
    """Extract short name from URI"""
    if '#' in uri:
        return uri.split('#')[-1]
    elif '/' in uri:
        return uri.split('/')[-1]
    else:
        return uri[:50] + '...' if len(uri) > 50 else uri

def get_node_color(uri, category_colors):
    """Determine node color based on URI namespace"""
    if 'abi:' in uri or 'abi.com' in uri:
        return '#FF6B6B'  # Red for ABI
    elif 'rdfs:' in uri or 'rdf:' in uri:
        return '#4ECDC4'  # Teal for RDF/RDFS
    elif 'owl:' in uri:
        return '#45B7D1'  # Blue for OWL
    elif 'foaf:' in uri:
        return '#96CEB4'  # Green for FOAF
    else:
        return '#FFA07A'  # Light salmon for others

# Main Interface
st.title("🕸️ ABI Ontology Explorer")
st.markdown("**Interactive Knowledge Graph Visualization of Platform TTL Files**")

# Sidebar controls
st.sidebar.header("📁 File Selection")

# Discover TTL files
with st.spinner("Discovering TTL files..."):
    ttl_files = discover_ttl_files()

st.sidebar.markdown(f"**Found {len(ttl_files)} TTL files**")

# Category filter
categories = sorted(set(f['category'] for f in ttl_files))
selected_categories = st.sidebar.multiselect(
    "Filter by Category",
    categories,
    default=categories
)

# Module filter
filtered_by_category = [f for f in ttl_files if f['category'] in selected_categories]
modules = sorted(set(f['module'] for f in filtered_by_category))
selected_modules = st.sidebar.multiselect(
    "Filter by Module",
    modules,
    default=modules[:10] if len(modules) > 10 else modules  # Limit default selection
)

# File selection
filtered_files = [
    f for f in filtered_by_category 
    if f['module'] in selected_modules
]

st.sidebar.markdown(f"**Filtered to {len(filtered_files)} files**")

# File list with checkboxes
selected_file_paths = st.sidebar.multiselect(
    "Select Files to Visualize",
    [f['path'] for f in filtered_files],
    default=[f['path'] for f in filtered_files[:5]]  # Default to first 5
)

st.session_state.selected_files = [
    f for f in filtered_files 
    if f['path'] in selected_file_paths
]

# Visualization controls
st.sidebar.header("🎛️ Visualization")
max_nodes = st.sidebar.slider("Max Nodes", 50, 1000, 300)
show_stats = st.sidebar.checkbox("Show Statistics", True)

# Main content
if st.session_state.selected_files:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("🌐 Knowledge Graph")
        
        if st.button("🔄 Generate Visualization", type="primary"):
            with st.spinner("Creating knowledge graph..."):
                try:
                    net, file_stats, node_count, edge_count = create_knowledge_graph(
                        st.session_state.selected_files, 
                        max_nodes
                    )
                    
                    # Save to temporary file
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
                    temp_file_path = temp_file.name
                    temp_file.close()
                    
                    net.save_graph(temp_file_path)
                    with open(temp_file_path, 'r') as html_file:
                        st.session_state.graph_html = html_file.read()
                    os.unlink(temp_file_path)
                    
                    st.success(f"✅ Generated graph with {node_count} nodes and {edge_count} edges")
                    
                except Exception as e:
                    st.error(f"❌ Error creating visualization: {e}")
        
        # Display graph
        if st.session_state.graph_html:
            st.components.v1.html(st.session_state.graph_html, height=650)
    
    with col2:
        if show_stats:
            st.subheader("📊 Statistics")
            
            # File statistics
            st.markdown("**Selected Files:**")
            for file_info in st.session_state.selected_files:
                st.markdown(f"- `{file_info['name']}`")
                st.caption(f"  {file_info['category']} | {file_info['module']}")
            
            # Category breakdown
            st.markdown("**By Category:**")
            category_counts: dict[str, int] = defaultdict(int)
            for f in st.session_state.selected_files:
                category_counts[f['category']] += 1
            
            for category, count in category_counts.items():
                st.metric(category, count)

else:
    st.info("👆 Select TTL files from the sidebar to begin visualization")

# File browser
st.subheader("📋 File Browser")

if ttl_files:
    # Create DataFrame for file browser
    df = pd.DataFrame(ttl_files)
    
    # Display with filtering
    st.dataframe(
        df[['name', 'category', 'module', 'path', 'size']],
        use_container_width=True,
        column_config={
            'name': 'File Name',
            'category': 'Category', 
            'module': 'Module',
            'path': 'Path',
            'size': st.column_config.NumberColumn('Size (bytes)', format='%d')
        }
    )
else:
    st.warning("No TTL files found in the platform")

# SOP Section
st.sidebar.markdown("---")
if st.sidebar.button("📖 View SOP", use_container_width=True):
    st.session_state.page = "sop"
    st.rerun()

# Initialize session state for page routing
if 'page' not in st.session_state:
    st.session_state.page = "main"

# Page routing
if st.session_state.page == "sop":
    # SOP Page
    st.title("📖 Standard Operating Procedure")

    if st.button("← Back to Ontology Explorer"):
        st.session_state.page = "main"
        st.rerun()

    st.markdown("---")

    # Read and display the SOP.md file
    try:
        sop_path = os.path.join(os.path.dirname(__file__), "SOP.md")
        with open(sop_path, 'r', encoding='utf-8') as f:
            sop_content = f.read()
        st.markdown(sop_content)
    except FileNotFoundError:
        st.error("SOP.md file not found. Please ensure the SOP file exists in the same directory as this interface.")
    except Exception as e:
        st.error(f"Error loading SOP: {str(e)}")

    st.stop()  # Stop execution here for SOP page
