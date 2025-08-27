# Ontology Mode - Standard Operating Procedure

## Overview
The Ontology Mode interface provides interactive visualization and exploration of all TTL (Turtle) files within the ABI platform using PyVis/VisJS knowledge graphs.

## Purpose
- **Discover** all ontology files across the platform
- **Visualize** knowledge graphs from TTL files
- **Explore** relationships between entities
- **Analyze** platform knowledge structure

## Key Features

### 1. File Discovery
- Automatically scans the entire platform for `.ttl` files
- Categorizes files by:
  - **Domain Experts**: Specialized domain ontologies
  - **Core Modules**: Platform core ontologies  
  - **Marketplace**: Third-party ontologies
  - **Other**: Miscellaneous ontologies

### 2. Interactive Filtering
- **Category Filter**: Select specific categories to focus on
- **Module Filter**: Filter by specific modules
- **File Selection**: Choose individual files for visualization

### 3. Knowledge Graph Visualization
- **Interactive Network**: Pan, zoom, and explore the graph
- **Node Sizing**: Nodes sized by number of connections
- **Color Coding**: Different colors for different namespaces
- **Edge Labels**: Relationship types displayed on connections
- **Hover Information**: Detailed node/edge information on hover

### 4. Statistics Dashboard
- File count by category
- Selected files overview
- Graph metrics (nodes, edges)

## How to Use

### Step 1: File Selection
1. Use the **Category Filter** to select relevant categories
2. Use the **Module Filter** to narrow down to specific modules
3. Select individual files from the **File Selection** dropdown
4. Start with 3-5 files for optimal performance

### Step 2: Generate Visualization
1. Click **"🔄 Generate Visualization"** button
2. Wait for the knowledge graph to be created
3. The graph will appear in the main panel

### Step 3: Explore the Graph
1. **Pan**: Click and drag to move around
2. **Zoom**: Use mouse wheel to zoom in/out
3. **Hover**: Hover over nodes/edges for details
4. **Physics**: Graph will stabilize automatically

### Step 4: Analyze Results
1. Check the **Statistics** panel for metrics
2. Look for clusters and connection patterns
3. Identify key entities with many connections
4. Explore namespace relationships

## Performance Guidelines

### Recommended Limits
- **Max Nodes**: 300-500 for smooth interaction
- **File Count**: 5-10 files per visualization
- **Large Files**: Be cautious with files >1000 triples

### Optimization Tips
1. Start with smaller file sets
2. Use category/module filters effectively
3. Adjust max nodes slider if performance is slow
4. Clear and regenerate if graph becomes cluttered

## Technical Details

### Supported Formats
- **TTL (Turtle)**: Primary format
- **RDF/XML**: Parsed as RDF
- **N-Triples**: Basic triple format

### Graph Elements
- **Nodes**: RDF subjects and objects (URIs only)
- **Edges**: RDF predicates (relationships)
- **Colors**: Based on namespace prefixes
- **Size**: Based on node degree (connections)

### Filtering Logic
- **Literals**: Excluded from visualization for clarity
- **Blank Nodes**: Included but may appear as complex IDs
- **Namespaces**: Shortened for readability

## Troubleshooting

### Common Issues

**"No TTL files found"**
- Check if platform has ontology files
- Verify file permissions
- Look in expected directories

**"Visualization too slow"**
- Reduce max nodes limit
- Select fewer files
- Choose smaller ontology files

**"Graph appears empty"**
- Check if selected files contain valid triples
- Verify TTL syntax is correct
- Try different file combinations

**"Nodes overlap too much"**
- Increase physics iterations
- Adjust graph layout settings
- Use zoom to explore dense areas

### Performance Issues
- **High CPU**: Reduce node count or file selection
- **Memory Usage**: Clear browser cache, restart interface
- **Slow Loading**: Check file sizes, network connectivity

## Best Practices

### Exploration Strategy
1. **Start Small**: Begin with 2-3 related files
2. **Build Up**: Gradually add more files
3. **Focus Areas**: Use filters to explore specific domains
4. **Compare**: Generate multiple visualizations for comparison

### Analysis Approach
1. **Identify Hubs**: Look for highly connected nodes
2. **Find Patterns**: Look for recurring relationship types
3. **Explore Clusters**: Investigate dense connection areas
4. **Cross-Reference**: Compare different module ontologies

### Documentation
1. **Screenshot**: Capture interesting graph configurations
2. **Notes**: Document insights and patterns found
3. **Share**: Export findings for team collaboration

## Advanced Usage

### Custom Analysis
- Use statistics to identify key entities
- Export node/edge data for external analysis
- Combine with SPARQL queries for deeper insights

### Integration
- Use insights to improve ontology design
- Identify missing relationships
- Validate ontology consistency

## Support
For technical issues or feature requests, use the platform's support system or contact the development team.
