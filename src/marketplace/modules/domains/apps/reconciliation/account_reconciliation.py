"""
Account Reconciliation Interface
Multi-use: Treasurer, Accountant, Financial Controller, Auditor
Tools: Bank reconciliation, transaction matching, variance analysis, audit trails
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Account Reconciliation", page_icon="🔍", layout="wide")

# Configure port for this interface

if __name__ == "__main__":
    import os
    os.environ["STREAMLIT_SERVER_PORT"] = "8501"

# Sidebar controls
st.sidebar.header("🔧 Reconciliation Controls")
account_type = st.sidebar.selectbox(
    "Account Type",
    ["All Accounts", "Bank Accounts", "Credit Cards", "Investment Accounts", "Receivables", "Payables"]
)

reconciliation_period = st.sidebar.selectbox(
    "Reconciliation Period",
    ["Current Month", "Last Month", "Custom Range"]
)

if reconciliation_period == "Custom Range":
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(datetime.now() - timedelta(days=30), datetime.now())
    )

# SOP Section in Sidebar
st.sidebar.markdown("---")
if st.sidebar.button("📖 View SOP", use_container_width=True):
    st.session_state.page = "sop"
    st.rerun()

# Initialize session state
if 'page' not in st.session_state:
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
        with open(sop_path, 'r', encoding='utf-8') as f:
            sop_content = f.read()
        st.markdown(sop_content)
    except FileNotFoundError:
        st.error("SOP.md file not found. Please ensure the SOP file exists in the same directory as this interface.")
    except Exception as e:
        st.error(f"Error loading SOP: {str(e)}")
    
    st.stop()  # Stop execution here for SOP page

# Main Dashboard Page
st.title("🔍 Account Reconciliation Center")
st.markdown("**Multi-Account Reconciliation & Variance Analysis**")

# Sample reconciliation data
@st.cache_data
def load_reconciliation_data():
    # Account balances
    accounts = {
        'Chase Operating': {'book': 245000, 'bank': 243500, 'variance': -1500, 'status': 'Pending'},
        'Wells Savings': {'book': 850000, 'bank': 850000, 'variance': 0, 'status': 'Reconciled'},
        'BofA Investment': {'book': 1200000, 'bank': 1205000, 'variance': 5000, 'status': 'Discrepancy'},
        'Amex Corporate': {'book': -15000, 'bank': -15200, 'variance': -200, 'status': 'Pending'},
        'Accounts Receivable': {'book': 180000, 'bank': 175000, 'variance': -5000, 'status': 'Under Review'}
    }
    
    # Outstanding items
    outstanding_items = pd.DataFrame({
        'Date': pd.date_range(start=datetime.now()-timedelta(days=15), periods=8, freq='2D'),
        'Description': ['Check #1234', 'Wire Transfer', 'ACH Deposit', 'Check #1235', 
                       'Direct Deposit', 'Bank Fee', 'Interest Payment', 'Check #1236'],
        'Amount': [2500, -15000, 8000, 1200, 25000, -25, 150, 3200],
        'Type': ['Outstanding Check', 'Outstanding Transfer', 'Deposit in Transit', 'Outstanding Check',
                'Deposit in Transit', 'Bank Charge', 'Bank Credit', 'Outstanding Check'],
        'Days_Outstanding': [12, 8, 5, 10, 3, 1, 2, 7]
    })
    
    return accounts, outstanding_items

accounts_data, outstanding_items = load_reconciliation_data()

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

total_variance = sum([acc['variance'] for acc in accounts_data.values()])
reconciled_count = sum([1 for acc in accounts_data.values() if acc['status'] == 'Reconciled'])
pending_count = sum([1 for acc in accounts_data.values() if acc['status'] == 'Pending'])
discrepancy_count = sum([1 for acc in accounts_data.values() if acc['status'] == 'Discrepancy'])

with col1:
    st.metric("Total Variance", f"${total_variance:,.0f}", 
              "🟢" if abs(total_variance) < 1000 else "🟡" if abs(total_variance) < 5000 else "🔴")

with col2:
    st.metric("Reconciled Accounts", reconciled_count, f"of {len(accounts_data)}")

with col3:
    st.metric("Pending Reviews", pending_count, "⏳")

with col4:
    st.metric("Discrepancies", discrepancy_count, "🚨" if discrepancy_count > 0 else "✅")

# Account reconciliation status
st.subheader("📊 Account Reconciliation Status")

col1, col2 = st.columns([2, 1])

with col1:
    # Create reconciliation dataframe
    recon_df = pd.DataFrame({
        'Account': list(accounts_data.keys()),
        'Book_Balance': [acc['book'] for acc in accounts_data.values()],
        'Bank_Balance': [acc['bank'] for acc in accounts_data.values()],
        'Variance': [acc['variance'] for acc in accounts_data.values()],
        'Status': [acc['status'] for acc in accounts_data.values()]
    })
    
    # Variance chart
    fig_variance = px.bar(recon_df, x='Account', y='Variance',
                         title="Account Variances",
                         color='Variance',
                         color_continuous_scale='RdYlGn',
                         color_continuous_midpoint=0)
    fig_variance.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_variance, use_container_width=True)

with col2:
    st.markdown("**🎯 Reconciliation Priority**")
    
    # Sort by absolute variance for priority
    priority_accounts = sorted(accounts_data.items(), key=lambda x: abs(x[1]['variance']), reverse=True)
    
    for account, data in priority_accounts[:5]:
        status_color = {
            'Reconciled': 'green',
            'Pending': 'orange', 
            'Discrepancy': 'red',
            'Under Review': 'blue'
        }.get(data['status'], 'gray')
        
        st.markdown(f"**{account}**")
        st.markdown(f"<span style='color: {status_color}'>{data['status']}</span>", unsafe_allow_html=True)
        st.markdown(f"Variance: ${data['variance']:,}")
        st.markdown("---")

# Detailed reconciliation table
st.subheader("📋 Detailed Account Analysis")

# Style the dataframe
def style_variance(val):
    if val == 0:
        return 'background-color: lightgreen'
    elif abs(val) < 1000:
        return 'background-color: lightyellow'
    else:
        return 'background-color: lightcoral'

def style_status(val):
    colors = {
        'Reconciled': 'background-color: lightgreen',
        'Pending': 'background-color: lightyellow',
        'Discrepancy': 'background-color: lightcoral',
        'Under Review': 'background-color: lightblue'
    }
    return colors.get(val, '')

styled_df = recon_df.style.map(style_variance, subset=['Variance']).map(style_status, subset=['Status'])
st.dataframe(styled_df, use_container_width=True)

# Outstanding items analysis
st.subheader("⏰ Outstanding Items")

col1, col2 = st.columns(2)

with col1:
    # Outstanding items by type
    type_counts = outstanding_items['Type'].value_counts()
    fig_types = px.pie(values=type_counts.values, names=type_counts.index,
                      title="Outstanding Items by Type")
    st.plotly_chart(fig_types, use_container_width=True)

with col2:
    # Aging analysis
    fig_aging = px.scatter(outstanding_items, x='Days_Outstanding', y='Amount',
                          color='Type', size=abs(outstanding_items['Amount']),
                          title="Outstanding Items Aging",
                          hover_data=['Description'])
    st.plotly_chart(fig_aging, use_container_width=True)

# Outstanding items table
st.markdown("**📝 Outstanding Items Detail**")
outstanding_display = outstanding_items.copy()
outstanding_display['Amount'] = outstanding_display['Amount'].apply(lambda x: f"${x:,.0f}")

# Color code by age
def color_age(val):
    if val <= 3:
        return 'color: green'
    elif val <= 7:
        return 'color: orange'
    else:
        return 'color: red'

styled_outstanding = outstanding_display.style.map(color_age, subset=['Days_Outstanding'])
st.dataframe(styled_outstanding, use_container_width=True)

# Reconciliation actions
st.subheader("⚡ Reconciliation Actions")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🔄 Auto-Match Transactions", use_container_width=True):
        st.success("Auto-matching initiated for all accounts")

with col2:
    if st.button("📊 Generate Reconciliation Report", use_container_width=True):
        st.info("Comprehensive reconciliation report generated")

with col3:
    if st.button("🚨 Flag All Discrepancies", use_container_width=True):
        st.warning("All discrepancies flagged for management review")

with col4:
    if st.button("✅ Mark as Reconciled", use_container_width=True):
        st.success("Selected accounts marked as reconciled")

# Reconciliation workflow
st.subheader("🔄 Reconciliation Workflow")

workflow_steps = [
    {"step": "1. Import Bank Statements", "status": "✅ Complete", "time": "09:00 AM"},
    {"step": "2. Auto-Match Transactions", "status": "✅ Complete", "time": "09:15 AM"},
    {"step": "3. Review Unmatched Items", "status": "🔄 In Progress", "time": "09:30 AM"},
    {"step": "4. Investigate Discrepancies", "status": "⏳ Pending", "time": "10:00 AM"},
    {"step": "5. Management Approval", "status": "⏳ Pending", "time": "11:00 AM"},
    {"step": "6. Final Reconciliation", "status": "⏳ Pending", "time": "11:30 AM"}
]

for step in workflow_steps:
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"**{step['step']}**")
    with col2:
        status_color = "green" if "✅" in step['status'] else "orange" if "🔄" in step['status'] else "gray"
        st.markdown(f"<span style='color: {status_color}'>{step['status']}</span>", unsafe_allow_html=True)
    with col3:
        st.markdown(step['time'])

# Recent reconciliation activity
st.subheader("📈 Recent Activity")

activities = [
    {"time": "5 min ago", "user": "Sarah (Treasurer)", "action": "Reconciled Wells Savings account"},
    {"time": "15 min ago", "user": "Mike (Accountant)", "action": "Flagged $5,000 discrepancy in BofA Investment"},
    {"time": "1 hour ago", "user": "Lisa (Controller)", "action": "Approved reconciliation for Chase Operating"},
    {"time": "2 hours ago", "user": "System", "action": "Auto-matched 47 transactions"},
    {"time": "3 hours ago", "user": "John (Auditor)", "action": "Reviewed outstanding items aging report"}
]

for activity in activities:
    st.markdown(f"**{activity['time']}** - {activity['user']}: {activity['action']}")

# Footer
st.markdown("---")
st.markdown("**Account Reconciliation Center** | Last Updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
