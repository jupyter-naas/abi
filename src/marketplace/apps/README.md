# Core User Interface Patterns

This directory contains reusable interface patterns that can be implemented across all ABI modules. Each pattern provides a consistent user experience and can be customized for specific domain needs.

## Interface Patterns

### 🗨️ **Chat Mode**
Natural language interaction with AI assistants
- **Inputs:** Voice, text, image, video
- **Use Cases:** AI conversations, Q&A, assistance
- **Components:** Message history, input field, voice controls

### 🕸️ **Ontology Mode**  
Interactive knowledge graph visualization and editing
- **Views:** Graph, table, tree, list
- **Use Cases:** Knowledge management, relationship mapping
- **Components:** Node editor, relationship viewer, search

### 📊 **Visualization Mode**
Interactive dashboards and data exploration tools
- **Views:** Chart, graph, table, list
- **Use Cases:** Analytics, reporting, monitoring
- **Components:** Chart builder, filters, drill-down

### 💻 **Code Mode**
Development environment for creating and editing code
- **Views:** Code editor, terminal, chat
- **Use Cases:** Programming, scripting, automation
- **Components:** Syntax highlighting, debugging, AI assistance

### 📄 **Document Mode**
Create and edit documents with AI assistance
- **Inputs:** Text, image, video, audio
- **Use Cases:** Writing, documentation, content creation
- **Components:** Rich text editor, AI suggestions, media insertion

### 🎯 **Slides Mode**
Create and edit presentations with AI assistance
- **Inputs:** Text, image, video, audio
- **Use Cases:** Presentations, training materials
- **Components:** Slide editor, template library, AI generation

### 📝 **Form Mode**
Structured data entry and configuration interfaces
- **Inputs:** Text, image, video, audio
- **Use Cases:** Data collection, settings, configuration
- **Components:** Form builder, validation, conditional logic

### 📋 **Kanban Mode**
Drag-and-drop task management board interface
- **Views:** Board, list, card
- **Use Cases:** Project management, workflow tracking
- **Components:** Drag-drop, status columns, card editor

### ⏰ **Timeline Mode**
Chronological visualization of events and milestones
- **Views:** Timeline, list, calendar
- **Use Cases:** Project planning, historical analysis
- **Components:** Timeline viewer, event editor, filtering

### 📅 **Calendar Mode**
Date-based scheduling and event management view
- **Views:** Month, week, day, agenda
- **Use Cases:** Scheduling, time management
- **Components:** Event creation, recurring events, reminders

### 🖼️ **Gallery Mode**
Grid or carousel display of images and media
- **Views:** Grid, carousel, list
- **Use Cases:** Media management, portfolios
- **Components:** Image viewer, metadata editor, search

### 📄 **List Mode**
Simple linear presentation of items
- **Views:** List, compact list
- **Use Cases:** Simple data display, navigation
- **Components:** Item renderer, search, sorting

### 📊 **Table Mode**
Structured grid view of data with sorting and filtering
- **Views:** Grid, table, spreadsheet
- **Use Cases:** Data analysis, bulk editing
- **Components:** Column editor, filters, pagination

## Implementation Guidelines

### Port Configuration
Each interface should run on a unique port:
- Chat Mode: 8510
- Ontology Mode: 8511
- Visualization Mode: 8512
- Code Mode: 8513
- Document Mode: 8514
- Slides Mode: 8515
- Form Mode: 8516
- Kanban Mode: 8517
- Timeline Mode: 8518
- Calendar Mode: 8519
- Gallery Mode: 8520
- List Mode: 8521
- Table Mode: 8522

### File Structure
Each mode should contain:
- `{mode_name}_interface.py` - Main Streamlit application
- `SOP.md` - Standard Operating Procedure
- `components/` - Reusable UI components (optional)
- `utils/` - Helper functions (optional)

### Usage
These patterns can be imported and customized by:
- Domain expert modules (`src/domain-experts/`)
- Custom modules (`src/custom/`)
- Marketplace modules (`src/marketplace/`)

### Running Interfaces
```bash
# Run individual interface
cd src/core/user-interfaces/chat-mode
streamlit run chat_interface.py

# Run all interfaces (different terminals)
make run-all-interfaces
```

## Design Principles

1. **Consistency** - Same patterns across all modules
2. **Reusability** - Easy to customize for specific needs
3. **Accessibility** - Clean, professional interfaces
4. **Performance** - Optimized for real-world usage
5. **Extensibility** - Easy to add new patterns
