"""
Kanban Mode Interface Pattern
Drag-and-drop task management board interface with customizable columns and workflows
"""

import streamlit as st
from datetime import datetime, timedelta
import plotly.express as px
import json
import os

st.set_page_config(page_title="Kanban Mode", page_icon="📋", layout="wide")

# Configure port for this interface
if __name__ == "__main__":
    os.environ["STREAMLIT_SERVER_PORT"] = "8517"

# SOP Section in Sidebar
st.sidebar.markdown("---")
if st.sidebar.button("📖 View SOP", use_container_width=True):
    st.session_state.page = "sop"
    st.rerun()

# Initialize session state
if "page" not in st.session_state:
    st.session_state.page = "main"

# Page routing
if st.session_state.page == "sop":
    # SOP Page
    st.title("📖 Standard Operating Procedure")

    if st.button("← Back to Kanban"):
        st.session_state.page = "main"
        st.rerun()

    st.markdown("---")

    # Read and display the SOP.md file
    try:
        import os

        sop_path = os.path.join(os.path.dirname(__file__), "SOP.md")
        with open(sop_path, "r", encoding="utf-8") as f:
            sop_content = f.read()
        st.markdown(sop_content)
    except FileNotFoundError:
        st.error(
            "SOP.md file not found. Please ensure the SOP file exists in the same directory as this interface."
        )
    except Exception as e:
        st.error(f"Error loading SOP: {str(e)}")

    st.stop()  # Stop execution here for SOP page

# Main Kanban Interface
st.title("📋 Kanban Mode Interface")
st.markdown("**Drag-and-Drop Task Management & Workflow Visualization**")

# Initialize session state for kanban data
if "kanban_tasks" not in st.session_state:
    # Sample kanban data
    st.session_state.kanban_tasks = [
        {
            "id": "T001",
            "title": "User Authentication System",
            "description": "Implement OAuth 2.0 authentication",
            "status": "To Do",
            "priority": "High",
            "assignee": "Alice",
            "points": 8,
            "tags": ["Backend", "Security"],
            "created": datetime.now() - timedelta(days=5),
        },
        {
            "id": "T002",
            "title": "Dashboard UI Design",
            "description": "Create responsive dashboard layout",
            "status": "In Progress",
            "priority": "Medium",
            "assignee": "Bob",
            "points": 5,
            "tags": ["Frontend", "UI"],
            "created": datetime.now() - timedelta(days=3),
        },
        {
            "id": "T003",
            "title": "API Documentation",
            "description": "Document REST API endpoints",
            "status": "In Progress",
            "priority": "Low",
            "assignee": "Charlie",
            "points": 3,
            "tags": ["Documentation"],
            "created": datetime.now() - timedelta(days=2),
        },
        {
            "id": "T004",
            "title": "Database Migration",
            "description": "Migrate to PostgreSQL",
            "status": "Review",
            "priority": "High",
            "assignee": "Alice",
            "points": 13,
            "tags": ["Backend", "Database"],
            "created": datetime.now() - timedelta(days=7),
        },
        {
            "id": "T005",
            "title": "Mobile Responsive",
            "description": "Make app mobile-friendly",
            "status": "Done",
            "priority": "Medium",
            "assignee": "Bob",
            "points": 8,
            "tags": ["Frontend", "Mobile"],
            "created": datetime.now() - timedelta(days=10),
        },
        {
            "id": "T006",
            "title": "Performance Testing",
            "description": "Load testing and optimization",
            "status": "To Do",
            "priority": "Medium",
            "assignee": "David",
            "points": 5,
            "tags": ["Testing", "Performance"],
            "created": datetime.now() - timedelta(days=1),
        },
        {
            "id": "T007",
            "title": "User Feedback Integration",
            "description": "Add feedback collection system",
            "status": "In Progress",
            "priority": "Low",
            "assignee": "Eve",
            "points": 3,
            "tags": ["Frontend", "UX"],
            "created": datetime.now() - timedelta(days=4),
        },
        {
            "id": "T008",
            "title": "Security Audit",
            "description": "Comprehensive security review",
            "status": "Review",
            "priority": "High",
            "assignee": "Charlie",
            "points": 8,
            "tags": ["Security", "Audit"],
            "created": datetime.now() - timedelta(days=6),
        },
    ]

if "kanban_columns" not in st.session_state:
    st.session_state.kanban_columns = ["To Do", "In Progress", "Review", "Done"]

# Sidebar controls
st.sidebar.header("🔧 Kanban Configuration")

# Board Settings
board_name = st.sidebar.text_input("Board Name", value="Development Sprint")
workflow_type = st.sidebar.selectbox(
    "Workflow Type",
    [
        "Software Development",
        "Marketing Campaign",
        "Content Creation",
        "Sales Pipeline",
        "Custom",
    ],
)

# Column Management
st.sidebar.markdown("### 📋 Columns")
if st.sidebar.button("➕ Add Column"):
    new_column = st.sidebar.text_input("New Column Name", key="new_column")
    if new_column and new_column not in st.session_state.kanban_columns:
        st.session_state.kanban_columns.append(new_column)
        st.rerun()

# Display current columns with delete option
for i, column in enumerate(st.session_state.kanban_columns):
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.text(f"• {column}")
    with col2:
        if len(st.session_state.kanban_columns) > 2:  # Keep at least 2 columns
            if st.button("🗑️", key=f"del_col_{i}"):
                # Move tasks from deleted column to first column
                for task in st.session_state.kanban_tasks:
                    if task["status"] == column:
                        task["status"] = st.session_state.kanban_columns[0]
                st.session_state.kanban_columns.remove(column)
                st.rerun()

# Filters
st.sidebar.markdown("### 🔍 Filters")
filter_assignee = st.sidebar.selectbox(
    "Assignee",
    ["All"] + list(set([task["assignee"] for task in st.session_state.kanban_tasks])),
)

filter_priority = st.sidebar.selectbox("Priority", ["All", "High", "Medium", "Low"])

filter_tags = st.sidebar.multiselect(
    "Tags",
    list(set([tag for task in st.session_state.kanban_tasks for tag in task["tags"]])),
)

# Apply filters
filtered_tasks = st.session_state.kanban_tasks.copy()

if filter_assignee != "All":
    filtered_tasks = [
        task for task in filtered_tasks if task["assignee"] == filter_assignee
    ]

if filter_priority != "All":
    filtered_tasks = [
        task for task in filtered_tasks if task["priority"] == filter_priority
    ]

if filter_tags:
    filtered_tasks = [
        task
        for task in filtered_tasks
        if any(tag in task["tags"] for tag in filter_tags)
    ]

# Board Statistics
st.markdown("### 📊 Board Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_tasks = len(filtered_tasks)
    st.metric("Total Tasks", total_tasks)

with col2:
    total_points = sum([task["points"] for task in filtered_tasks])
    st.metric("Story Points", total_points)

with col3:
    completed_tasks = len([task for task in filtered_tasks if task["status"] == "Done"])
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    st.metric("Completion Rate", f"{completion_rate:.1f}%")

with col4:
    in_progress = len(
        [task for task in filtered_tasks if task["status"] == "In Progress"]
    )
    st.metric("In Progress", in_progress)

# Kanban Board
st.markdown("### 📋 Kanban Board")

# Create columns for the kanban board
columns = st.columns(len(st.session_state.kanban_columns))

for col_idx, column_name in enumerate(st.session_state.kanban_columns):
    with columns[col_idx]:
        # Column header
        column_tasks = [
            task for task in filtered_tasks if task["status"] == column_name
        ]
        column_points = sum([task["points"] for task in column_tasks])

        st.markdown(
            f"""
        <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <h4 style="margin: 0; color: #1f1f1f;">{column_name}</h4>
            <small>{len(column_tasks)} tasks • {column_points} points</small>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Task cards
        for task in column_tasks:
            # Priority color coding
            priority_colors = {"High": "#ff4444", "Medium": "#ffaa00", "Low": "#00aa00"}
            priority_color = priority_colors.get(task["priority"], "#888888")

            # Task card
            with st.container():
                st.markdown(
                    f"""
                <div style="
                    border: 1px solid #ddd; 
                    border-radius: 8px; 
                    padding: 12px; 
                    margin-bottom: 10px; 
                    background-color: white;
                    border-left: 4px solid {priority_color};
                ">
                    <div style="display: flex; justify-content: between; align-items: center;">
                        <strong style="color: #1f1f1f;">{task["title"]}</strong>
                        <span style="background-color: {priority_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; margin-left: 8px;">
                            {task["priority"]}
                        </span>
                    </div>
                    <p style="margin: 8px 0; color: #666; font-size: 14px;">{task["description"]}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px;">
                        <small style="color: #888;">👤 {task["assignee"]}</small>
                        <small style="color: #888;">📊 {task["points"]} pts</small>
                    </div>
                    <div style="margin-top: 8px;">
                        {" ".join([f'<span style="background-color: #e1f5fe; color: #01579b; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin-right: 4px;">{tag}</span>' for tag in task["tags"]])}
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                # Task actions
                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    if st.button("✏️", key=f"edit_{task['id']}", help="Edit task"):
                        st.session_state.editing_task = task["id"]

                with col_b:
                    # Move task buttons
                    current_idx = st.session_state.kanban_columns.index(task["status"])
                    if current_idx > 0:
                        if st.button("⬅️", key=f"left_{task['id']}", help="Move left"):
                            # Find the task and update its status
                            for t in st.session_state.kanban_tasks:
                                if t["id"] == task["id"]:
                                    t["status"] = st.session_state.kanban_columns[
                                        current_idx - 1
                                    ]
                                    break
                            st.rerun()

                with col_c:
                    if current_idx < len(st.session_state.kanban_columns) - 1:
                        if st.button("➡️", key=f"right_{task['id']}", help="Move right"):
                            # Find the task and update its status
                            for t in st.session_state.kanban_tasks:
                                if t["id"] == task["id"]:
                                    t["status"] = st.session_state.kanban_columns[
                                        current_idx + 1
                                    ]
                                    break
                            st.rerun()

# Add new task
st.markdown("---")
st.markdown("### ➕ Add New Task")

with st.expander("Create New Task"):
    col1, col2 = st.columns(2)

    with col1:
        new_title = st.text_input("Task Title")
        new_description = st.text_area("Description")
        new_assignee = st.selectbox(
            "Assignee",
            list(set([task["assignee"] for task in st.session_state.kanban_tasks]))
            + ["New Person"],
        )
        if new_assignee == "New Person":
            new_assignee = st.text_input("New Assignee Name")

    with col2:
        new_priority = st.selectbox("Priority", ["High", "Medium", "Low"])
        new_points = st.number_input("Story Points", min_value=1, max_value=21, value=3)
        new_status = st.selectbox("Initial Status", st.session_state.kanban_columns)
        new_tags = st.text_input(
            "Tags (comma-separated)", placeholder="backend, api, urgent"
        )

    if st.button("➕ Create Task"):
        if new_title and new_assignee:
            new_task = {
                "id": f"T{len(st.session_state.kanban_tasks) + 1:03d}",
                "title": new_title,
                "description": new_description,
                "status": new_status,
                "priority": new_priority,
                "assignee": new_assignee,
                "points": new_points,
                "tags": [tag.strip() for tag in new_tags.split(",") if tag.strip()],
                "created": datetime.now(),
            }
            st.session_state.kanban_tasks.append(new_task)
            st.success(f"Task '{new_title}' created successfully!")
            st.rerun()
        else:
            st.error("Please fill in at least the title and assignee.")

# Analytics
st.markdown("### 📈 Analytics")

col1, col2 = st.columns(2)

with col1:
    # Tasks by status
    status_counts = {}
    for column in st.session_state.kanban_columns:
        status_counts[column] = len(
            [task for task in filtered_tasks if task["status"] == column]
        )

    fig_status = px.bar(
        x=list(status_counts.keys()),
        y=list(status_counts.values()),
        title="Tasks by Status",
        labels={"x": "Status", "y": "Number of Tasks"},
    )
    st.plotly_chart(fig_status, use_container_width=True)

with col2:
    # Tasks by assignee
    assignee_counts: dict[str, int] = {}
    for task in filtered_tasks:
        assignee = task["assignee"]
        assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1

    if assignee_counts:
        fig_assignee = px.pie(
            values=list(assignee_counts.values()),
            names=list(assignee_counts.keys()),
            title="Tasks by Assignee",
        )
        st.plotly_chart(fig_assignee, use_container_width=True)

# Export and Import
st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Data Management")

if st.sidebar.button("📥 Export Board"):
    board_data = {
        "board_name": board_name,
        "columns": st.session_state.kanban_columns,
        "tasks": st.session_state.kanban_tasks,
    }

    board_json = json.dumps(board_data, default=str, indent=2)
    st.sidebar.download_button(
        label="💾 Download JSON",
        data=board_json,
        file_name=f"kanban_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )

uploaded_board = st.sidebar.file_uploader("📤 Import Board", type="json")
if uploaded_board is not None:
    try:
        board_data = json.load(uploaded_board)
        st.session_state.kanban_columns = board_data["columns"]
        st.session_state.kanban_tasks = board_data["tasks"]
        # Convert string dates back to datetime objects
        for task in st.session_state.kanban_tasks:
            if isinstance(task["created"], str):
                task["created"] = datetime.fromisoformat(task["created"])
        st.sidebar.success("Board imported successfully!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error importing board: {str(e)}")

# Quick Actions
st.sidebar.markdown("### ⚡ Quick Actions")
if st.sidebar.button("🔄 Reset Demo Data"):
    # Reset to original demo data
    del st.session_state.kanban_tasks
    del st.session_state.kanban_columns
    st.rerun()

if st.sidebar.button("📊 Generate Report"):
    st.sidebar.info("Board report generation would be implemented here")

# Footer
st.markdown("---")
st.markdown(
    f"**Kanban Board: {board_name}** | Tasks: {len(filtered_tasks)} | Workflow: {workflow_type} | Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
