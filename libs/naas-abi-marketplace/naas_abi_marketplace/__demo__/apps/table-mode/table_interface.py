"""
Table Mode Interface Pattern
Structured grid view of data with sorting, filtering, and editing capabilities
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import os

st.set_page_config(page_title="Table Mode", page_icon="📊", layout="wide")

# Configure port for this interface
if __name__ == "__main__":
    os.environ["STREAMLIT_SERVER_PORT"] = "8522"

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

    if st.button("← Back to Table"):
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

# Main Table Interface
st.title("📊 Table Mode Interface")
st.markdown("**Structured Data Grid with Advanced Filtering & Analysis**")

# Sidebar controls
st.sidebar.header("🔧 Table Configuration")

# Data Source Selection
data_source = st.sidebar.selectbox(
    "Data Source", ["Sample Data", "Upload CSV", "Database Connection", "API Endpoint"]
)

# Table View Options
view_mode = st.sidebar.selectbox(
    "View Mode", ["Standard Table", "Editable Grid", "Summary View", "Pivot Table"]
)

# Display Options
st.sidebar.markdown("### 🎨 Display Options")
show_index = st.sidebar.checkbox("Show Row Numbers", value=True)
show_totals = st.sidebar.checkbox("Show Column Totals", value=False)
highlight_changes = st.sidebar.checkbox("Highlight Changes", value=True)
compact_view = st.sidebar.checkbox("Compact View", value=False)

# Pagination
st.sidebar.markdown("### 📄 Pagination")
page_size = st.sidebar.selectbox("Rows per Page", [10, 25, 50, 100, "All"], index=1)


# Sample data generation
@st.cache_data
def load_sample_data():
    np.random.seed(42)
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=90), end=datetime.now(), freq="D"
    )

    data = []
    categories = ["Sales", "Marketing", "Engineering", "Support", "Operations"]
    statuses = ["Active", "Pending", "Completed", "Cancelled"]
    priorities = ["High", "Medium", "Low"]

    for i in range(200):
        data.append(
            {
                "ID": f"REC-{1000 + i}",
                "Date": np.random.choice(dates),
                "Category": np.random.choice(categories),
                "Title": f"Task {i + 1}: {np.random.choice(['Analysis', 'Development', 'Review', 'Planning', 'Implementation'])}",
                "Status": np.random.choice(statuses),
                "Priority": np.random.choice(priorities),
                "Assigned_To": f"User {np.random.randint(1, 20)}",
                "Progress": np.random.randint(0, 101),
                "Budget": np.random.randint(1000, 50000),
                "Hours_Spent": np.random.randint(1, 100),
                "Due_Date": pd.Timestamp(np.random.choice(dates))
                + timedelta(days=np.random.randint(1, 30)),
            }
        )

    return pd.DataFrame(data)


# Load data based on source
if data_source == "Sample Data":
    df = load_sample_data()
elif data_source == "Upload CSV":
    uploaded_file = st.sidebar.file_uploader("Choose CSV file", type="csv")
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    else:
        df = load_sample_data()
        st.info("Using sample data. Upload a CSV file to use your own data.")
else:
    df = load_sample_data()
    st.info(f"{data_source} not implemented yet. Using sample data.")

# Filtering Section
st.markdown("### 🔍 Filters & Search")

col1, col2, col3, col4 = st.columns(4)

with col1:
    # Text search
    search_term = st.text_input("🔎 Search", placeholder="Search in all columns...")

with col2:
    # Category filter
    if "Category" in df.columns:
        categories = ["All"] + list(df["Category"].unique())
        selected_category = st.selectbox("Category", categories)

with col3:
    # Status filter
    if "Status" in df.columns:
        statuses = ["All"] + list(df["Status"].unique())
        selected_status = st.selectbox("Status", statuses)

with col4:
    # Date range filter
    if "Date" in df.columns:
        date_range = st.date_input(
            "Date Range",
            value=(df["Date"].min().date(), df["Date"].max().date()),
            min_value=df["Date"].min().date(),
            max_value=df["Date"].max().date(),
        )

# Apply filters
filtered_df = df.copy()

# Text search filter
if search_term:
    mask = (
        df.astype(str)
        .apply(lambda x: x.str.contains(search_term, case=False, na=False))
        .any(axis=1)
    )
    filtered_df = filtered_df[mask]

# Category filter
if "Category" in df.columns and selected_category != "All":
    filtered_df = filtered_df[filtered_df["Category"] == selected_category]

# Status filter
if "Status" in df.columns and selected_status != "All":
    filtered_df = filtered_df[filtered_df["Status"] == selected_status]

# Date range filter
if "Date" in df.columns and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[
        (filtered_df["Date"].dt.date >= start_date)
        & (filtered_df["Date"].dt.date <= end_date)
    ]

# Summary metrics
st.markdown("### 📊 Summary")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Records", len(filtered_df), delta=len(filtered_df) - len(df))

with col2:
    if "Budget" in filtered_df.columns:
        total_budget = filtered_df["Budget"].sum()
        st.metric("Total Budget", f"${total_budget:,}")

with col3:
    if "Progress" in filtered_df.columns:
        avg_progress = filtered_df["Progress"].mean()
        st.metric("Avg Progress", f"{avg_progress:.1f}%")

with col4:
    if "Status" in filtered_df.columns:
        completed = len(filtered_df[filtered_df["Status"] == "Completed"])
        completion_rate = (
            (completed / len(filtered_df) * 100) if len(filtered_df) > 0 else 0
        )
        st.metric("Completion Rate", f"{completion_rate:.1f}%")

# Table display
st.markdown("### 📋 Data Table")

# Column selection
if st.checkbox("🔧 Customize Columns"):
    available_columns = list(filtered_df.columns)
    selected_columns = st.multiselect(
        "Select columns to display",
        available_columns,
        default=available_columns[:8],  # Show first 8 columns by default
    )
    display_df = filtered_df[selected_columns]
else:
    display_df = filtered_df

# Pagination
if page_size != "All":
    assert isinstance(page_size, int), "page_size should be an int when not 'All'"
    page_size_int = page_size
    total_pages = len(display_df) // page_size_int + (
        1 if len(display_df) % page_size_int > 0 else 0
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        page_number = (
            st.selectbox(
                f"Page (1-{total_pages})",
                range(1, total_pages + 1),
                key="page_selector",
            )
            if total_pages > 0
            else 1
        )

    start_idx = (page_number - 1) * page_size_int
    end_idx = start_idx + page_size_int
    paginated_df = display_df.iloc[start_idx:end_idx]
else:
    paginated_df = display_df

# Display table based on view mode
if view_mode == "Standard Table":
    st.dataframe(
        paginated_df,
        use_container_width=True,
        hide_index=not show_index,
        height=400 if not compact_view else 300,
    )

elif view_mode == "Editable Grid":
    st.info("📝 Editable mode - Changes are highlighted but not persisted in this demo")
    edited_df = st.data_editor(
        paginated_df,
        use_container_width=True,
        hide_index=not show_index,
        height=400 if not compact_view else 300,
        key="editable_table",
    )

elif view_mode == "Summary View":
    # Group by category and show summary
    if "Category" in display_df.columns:
        summary = (
            display_df.groupby("Category")
            .agg(
                {
                    "ID": "count",
                    "Budget": "sum" if "Budget" in display_df.columns else "count",
                    "Progress": "mean" if "Progress" in display_df.columns else "count",
                }
            )
            .round(2)
        )
        summary.columns = ["Count", "Total Budget", "Avg Progress"]
        st.dataframe(summary, use_container_width=True)
    else:
        st.warning("Summary view requires a 'Category' column")

elif view_mode == "Pivot Table":
    if len(display_df) > 0:
        st.markdown("**Configure Pivot Table:**")
        col1, col2, col3 = st.columns(3)

        with col1:
            index_col = st.selectbox(
                "Row (Index)", display_df.columns, key="pivot_index"
            )
        with col2:
            if len(display_df.columns) > 1:
                columns_col = st.selectbox(
                    "Column", [None] + list(display_df.columns), key="pivot_columns"
                )
            else:
                columns_col = None
        with col3:
            numeric_cols = display_df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                values_col = st.selectbox("Values", numeric_cols, key="pivot_values")
            else:
                values_col = None

        if values_col:
            try:
                pivot_table = pd.pivot_table(
                    display_df,
                    index=index_col,
                    columns=columns_col,
                    values=values_col,
                    aggfunc="mean",
                    fill_value=0,
                )
                st.dataframe(pivot_table, use_container_width=True)
            except Exception as e:
                st.error(f"Error creating pivot table: {str(e)}")
        else:
            st.warning("Please select a numeric column for values")

# Data visualization
if len(filtered_df) > 0:
    st.markdown("### 📈 Quick Visualizations")

    viz_col1, viz_col2 = st.columns(2)

    with viz_col1:
        # Category distribution
        if "Category" in filtered_df.columns:
            category_counts = filtered_df["Category"].value_counts()
            fig_pie = px.pie(
                values=category_counts.values,
                names=category_counts.index,
                title="Distribution by Category",
            )
            st.plotly_chart(fig_pie, width="stretch")

    with viz_col2:
        # Progress distribution
        if "Progress" in filtered_df.columns:
            fig_hist = px.histogram(
                filtered_df, x="Progress", title="Progress Distribution", nbins=20
            )
            st.plotly_chart(fig_hist, width="stretch")

# Export options
st.markdown("### 💾 Export Data")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📥 Download CSV"):
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="💾 Download Filtered Data",
            data=csv,
            file_name=f"table_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

with col2:
    if st.button("📊 Download Excel"):
        # In a real implementation, this would create an Excel file
        st.info("Excel export would be implemented here")

with col3:
    if st.button("📋 Copy to Clipboard"):
        # In a real implementation, this would copy to clipboard
        st.info("Clipboard functionality would be implemented here")

# Advanced operations
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚡ Quick Actions")

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

if st.sidebar.button("📊 Generate Report"):
    st.sidebar.success("Report generation would be implemented here")

if st.sidebar.button("🔍 Advanced Search"):
    st.sidebar.info("Advanced search dialog would open here")

# Footer
st.markdown("---")
st.markdown(
    f"**Table Mode Interface** | Records: {len(filtered_df):,} | View: {view_mode} | Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
