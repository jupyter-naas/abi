"""
Project Management Board Interface
Multi-use: Project Manager, Software Engineer, DevOps Engineer, Product Manager, Team Leads
Tools: Kanban boards, sprint planning, resource allocation, timeline tracking, deliverable management
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="Project Board", page_icon="📋", layout="wide")

# Configure port for this interface
if __name__ == "__main__":
    import os

    os.environ["STREAMLIT_SERVER_PORT"] = "8503"

# Sidebar controls
st.sidebar.header("🔧 Project Controls")
project_filter = st.sidebar.selectbox(
    "Project Filter",
    ["All Projects", "Active Projects", "My Projects", "Overdue Projects"],
)

team_filter = st.sidebar.multiselect(
    "Team Filter",
    ["Engineering", "Design", "Marketing", "Sales", "Operations"],
    default=["Engineering", "Design"],
)

view_mode = st.sidebar.selectbox(
    "View Mode", ["Kanban Board", "Timeline View", "Resource View", "Sprint View"]
)

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

    if st.button("← Back to Dashboard"):
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

# Main Dashboard Page
st.title("📋 Project Management Board")
st.markdown("**Multi-Team Project Tracking & Resource Management**")


# Sample project data
@st.cache_data
def load_project_data():
    projects = pd.DataFrame(
        {
            "Project_ID": [f"PRJ-{i:03d}" for i in range(1, 16)],
            "Title": [
                "Mobile App Redesign",
                "API Integration",
                "Database Migration",
                "User Authentication",
                "Payment Gateway",
                "Analytics Dashboard",
                "Performance Optimization",
                "Security Audit",
                "Marketing Campaign",
                "Sales Automation",
                "Customer Portal",
                "Inventory System",
                "Reporting Module",
                "Cloud Migration",
                "Quality Assurance",
            ],
            "Status": np.random.choice(
                ["Backlog", "In Progress", "Review", "Testing", "Done"], 15
            ),
            "Priority": np.random.choice(["Low", "Medium", "High", "Critical"], 15),
            "Team": np.random.choice(
                ["Engineering", "Design", "Marketing", "Sales", "Operations"], 15
            ),
            "Assignee": np.random.choice(
                ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"], 15
            ),
            "Start_Date": pd.date_range(
                start=datetime.now() - timedelta(days=60), periods=15, freq="4D"
            ),
            "Due_Date": pd.date_range(
                start=datetime.now() + timedelta(days=10), periods=15, freq="5D"
            ),
            "Progress": np.random.randint(0, 101, 15),
            "Story_Points": np.random.randint(1, 21, 15),
        }
    )

    # Calculate days remaining
    projects["Days_Remaining"] = (projects["Due_Date"] - datetime.now()).dt.days

    return projects


projects_data = load_project_data()

# Filter data based on selections
filtered_projects = projects_data.copy()
if team_filter:
    filtered_projects = filtered_projects[filtered_projects["Team"].isin(team_filter)]

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    active_projects = len(
        filtered_projects[
            filtered_projects["Status"].isin(["In Progress", "Review", "Testing"])
        ]
    )
    st.metric("Active Projects", active_projects, f"{np.random.randint(-2, 5)}")

with col2:
    overdue_projects = len(filtered_projects[filtered_projects["Days_Remaining"] < 0])
    st.metric(
        "Overdue Projects", overdue_projects, "🚨" if overdue_projects > 0 else "✅"
    )

with col3:
    avg_progress = filtered_projects["Progress"].mean()
    st.metric(
        "Avg Progress", f"{avg_progress:.1f}%", f"{np.random.uniform(-5, 10):.1f}%"
    )

with col4:
    total_story_points = filtered_projects["Story_Points"].sum()
    st.metric("Total Story Points", total_story_points, f"{np.random.randint(-10, 20)}")

# Main view based on selection
if view_mode == "Kanban Board":
    st.subheader("📋 Kanban Board")

    # Create columns for each status
    statuses = ["Backlog", "In Progress", "Review", "Testing", "Done"]
    cols = st.columns(len(statuses))

    for i, status in enumerate(statuses):
        with cols[i]:
            st.markdown(f"**{status}**")
            status_projects = filtered_projects[filtered_projects["Status"] == status]

            for _, project in status_projects.iterrows():
                priority_color = {
                    "Low": "lightblue",
                    "Medium": "lightyellow",
                    "High": "lightorange",
                    "Critical": "lightcoral",
                }.get(project["Priority"], "lightgray")

                with st.container():
                    st.markdown(
                        f"""
                    <div style='background-color: {priority_color}; padding: 10px; margin: 5px 0; border-radius: 5px; border-left: 4px solid #333;'>
                        <strong>{project["Project_ID"]}</strong><br>
                        {project["Title"]}<br>
                        <small>👤 {project["Assignee"]} | 🎯 {project["Priority"]}</small><br>
                        <small>📅 {project["Days_Remaining"]} days left</small>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

elif view_mode == "Timeline View":
    st.subheader("📅 Project Timeline")

    # Gantt-like chart
    fig_timeline = px.timeline(
        filtered_projects,
        x_start="Start_Date",
        x_end="Due_Date",
        y="Title",
        color="Team",
        title="Project Timeline Overview",
    )
    fig_timeline.update_yaxes(autorange="reversed")
    st.plotly_chart(fig_timeline, width="stretch")

    # Progress tracking
    col1, col2 = st.columns(2)

    with col1:
        fig_progress = px.bar(
            filtered_projects,
            x="Title",
            y="Progress",
            title="Project Progress (%)",
            color="Progress",
            color_continuous_scale="RdYlGn",
        )
        fig_progress.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_progress, width="stretch")

    with col2:
        # Days remaining analysis
        fig_days = px.scatter(
            filtered_projects,
            x="Days_Remaining",
            y="Progress",
            color="Priority",
            size="Story_Points",
            title="Progress vs Time Remaining",
            hover_data=["Title", "Assignee"],
        )
        st.plotly_chart(fig_days, width="stretch")

elif view_mode == "Resource View":
    st.subheader("👥 Resource Allocation")

    col1, col2 = st.columns(2)

    with col1:
        # Workload by assignee
        workload = (
            filtered_projects.groupby("Assignee")
            .agg({"Story_Points": "sum", "Project_ID": "count"})
            .rename(columns={"Project_ID": "Project_Count"})
        )

        fig_workload = px.bar(
            workload,
            x=workload.index,
            y="Story_Points",
            title="Story Points by Assignee",
            color="Story_Points",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig_workload, width="stretch")

    with col2:
        # Team distribution
        team_dist = filtered_projects["Team"].value_counts()
        fig_teams = px.pie(
            values=team_dist.values, names=team_dist.index, title="Projects by Team"
        )
        st.plotly_chart(fig_teams, width="stretch")

    # Resource capacity table
    st.markdown("**👤 Team Member Capacity**")
    capacity_data = pd.DataFrame(
        {
            "Team_Member": ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"],
            "Current_Projects": [3, 2, 4, 1, 3, 2],
            "Story_Points": [25, 18, 32, 8, 28, 15],
            "Capacity": [30, 25, 35, 20, 30, 25],
            "Utilization": [83, 72, 91, 40, 93, 60],
        }
    )

    def color_utilization(val):
        if val >= 90:
            return "background-color: lightcoral"
        elif val >= 80:
            return "background-color: lightyellow"
        else:
            return "background-color: lightgreen"

    styled_capacity = capacity_data.style.apply(
        color_utilization, subset=["Utilization"]
    )
    st.dataframe(styled_capacity, use_container_width=True)

elif view_mode == "Sprint View":
    st.subheader("🏃‍♂️ Sprint Planning")

    # Mock sprint data
    current_sprint = "Sprint 23"
    sprint_start = datetime.now() - timedelta(days=5)
    sprint_end = datetime.now() + timedelta(days=9)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Current Sprint", current_sprint)
        st.metric("Days Remaining", (sprint_end - datetime.now()).days)

    with col2:
        sprint_projects = filtered_projects[
            filtered_projects["Status"].isin(["In Progress", "Review", "Testing"])
        ]
        completed_points = sprint_projects[sprint_projects["Status"] == "Testing"][
            "Story_Points"
        ].sum()
        total_points = sprint_projects["Story_Points"].sum()
        st.metric("Sprint Progress", f"{completed_points}/{total_points} pts")
        st.metric("Completion Rate", f"{(completed_points / total_points * 100):.1f}%")

    with col3:
        velocity = np.random.randint(45, 65)
        st.metric("Team Velocity", f"{velocity} pts/sprint")
        st.metric("Burndown Trend", "📈 On Track")

    # Sprint burndown chart
    days = list(range(15))  # 2-week sprint
    ideal_burndown = [total_points - (total_points / 14 * day) for day in days]
    actual_burndown = [
        total_points - (total_points / 14 * day) + np.random.uniform(-5, 5)
        for day in days
    ]

    fig_burndown = go.Figure()
    fig_burndown.add_trace(
        go.Scatter(
            x=days, y=ideal_burndown, name="Ideal Burndown", line=dict(dash="dash")
        )
    )
    fig_burndown.add_trace(
        go.Scatter(
            x=days, y=actual_burndown, name="Actual Burndown", line=dict(width=3)
        )
    )
    fig_burndown.update_layout(
        title="Sprint Burndown Chart",
        xaxis_title="Days",
        yaxis_title="Story Points Remaining",
    )
    st.plotly_chart(fig_burndown, width="stretch")

# Project actions
st.subheader("⚡ Project Actions")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("➕ Create New Project", use_container_width=True):
        st.success("New project creation form opened")

with col2:
    if st.button("📊 Generate Report", use_container_width=True):
        st.info("Project status report generated")

with col3:
    if st.button("🔄 Sync with Jira", use_container_width=True):
        st.success("Synchronization with Jira completed")

with col4:
    if st.button("📧 Send Updates", use_container_width=True):
        st.success("Status updates sent to stakeholders")

# Detailed project table
st.subheader("📊 Project Details")

# Add selection capability
selected_projects = st.dataframe(
    filtered_projects[
        [
            "Project_ID",
            "Title",
            "Status",
            "Priority",
            "Team",
            "Assignee",
            "Progress",
            "Days_Remaining",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

# Risk analysis
st.subheader("⚠️ Risk Analysis")

col1, col2 = st.columns(2)

with col1:
    # High-risk projects
    high_risk = filtered_projects[
        (filtered_projects["Days_Remaining"] < 7) | (filtered_projects["Progress"] < 50)
    ]

    st.markdown("**🚨 High-Risk Projects**")
    for _, project in high_risk.head(5).iterrows():
        risk_reason = "Overdue" if project["Days_Remaining"] < 0 else "Behind Schedule"
        st.markdown(f"**{project['Project_ID']}** - {project['Title']}")
        st.markdown(f"Risk: {risk_reason} | Progress: {project['Progress']}%")
        st.markdown("---")

with col2:
    # Blocked projects
    st.markdown("**🚧 Blocked Projects**")
    blocked_projects = [
        {
            "id": "PRJ-008",
            "title": "Security Audit",
            "blocker": "Waiting for security team",
        },
        {
            "id": "PRJ-012",
            "title": "Inventory System",
            "blocker": "Database schema approval",
        },
        {
            "id": "PRJ-015",
            "title": "Quality Assurance",
            "blocker": "Test environment setup",
        },
    ]

    for project in blocked_projects:
        st.markdown(f"**{project['id']}** - {project['title']}")
        st.markdown(f"Blocker: {project['blocker']}")
        st.markdown("---")

# Recent activity feed
st.subheader("📈 Recent Project Activity")

activities = [
    {"time": "10 min ago", "user": "Alice", "action": "Moved PRJ-003 to Testing"},
    {
        "time": "30 min ago",
        "user": "Bob",
        "action": "Updated progress on PRJ-007 to 75%",
    },
    {"time": "1 hour ago", "user": "Charlie", "action": "Created new task in PRJ-011"},
    {
        "time": "2 hours ago",
        "user": "Diana",
        "action": "Completed PRJ-002: User Authentication",
    },
    {"time": "3 hours ago", "user": "Eve", "action": "Assigned PRJ-014 to Frank"},
]

for activity in activities:
    st.markdown(f"**{activity['time']}** - {activity['user']}: {activity['action']}")

# Footer
st.markdown("---")
st.markdown(
    "**Project Management Board** | Last Updated: "
    + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)
