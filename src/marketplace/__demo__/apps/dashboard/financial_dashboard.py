"""
Financial Dashboard Interface
Multi-use: Treasurer, Financial Controller, Accountant, CFO
Tools: Financial metrics, cash flow, P&L, balance sheet, budget tracking
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

st.set_page_config(page_title="Financial Dashboard", page_icon="📊", layout="wide")

# Configure port for this interface
if __name__ == "__main__":
    import os
    os.environ["STREAMLIT_SERVER_PORT"] = "8502"

# Sidebar role selector
st.sidebar.header("👤 Role & Permissions")
user_role = st.sidebar.selectbox(
    "Select Your Role",
    ["Treasurer", "Financial Controller", "Accountant", "CFO"]
)

# Role-based access control
role_permissions = {
    "Treasurer": ["cash_flow", "investments", "banking", "liquidity"],
    "Financial Controller": ["budgets", "forecasts", "variance", "projects"],
    "Accountant": ["transactions", "reconciliation", "journal_entries", "compliance"],
    "CFO": ["all"]  # Full access
}

current_permissions = role_permissions.get(user_role, [])
if "all" in current_permissions:
    current_permissions = ["cash_flow", "investments", "banking", "liquidity", "budgets", "forecasts", "variance", "projects", "transactions", "reconciliation", "journal_entries", "compliance"]

st.sidebar.markdown(f"**Access Level:** {user_role}")
st.sidebar.markdown(f"**Permissions:** {len(current_permissions)} modules")

# Time period selector
time_period = st.sidebar.selectbox(
    "Time Period",
    ["Current Month", "Last 3 Months", "YTD", "Last 12 Months"]
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
st.title("📊 Financial Dashboard")
st.markdown("**Multi-Role Financial Analysis & Reporting**")

# Sample financial data
@st.cache_data
def load_financial_data():
    dates = pd.date_range(start=datetime.now()-timedelta(days=365), end=datetime.now(), freq='D')
    
    # Cash flow data
    cash_data = pd.DataFrame({
        'Date': dates,
        'Operating_Cash': np.random.normal(10000, 3000, len(dates)).cumsum(),
        'Investing_Cash': np.random.normal(-2000, 1000, len(dates)).cumsum(),
        'Financing_Cash': np.random.normal(1000, 500, len(dates)).cumsum()
    })
    
    # P&L data
    monthly_dates = pd.date_range(start=datetime.now()-timedelta(days=365), end=datetime.now(), freq='ME')
    pnl_data = pd.DataFrame({
        'Month': monthly_dates,
        'Revenue': np.random.normal(500000, 50000, len(monthly_dates)),
        'COGS': np.random.normal(-200000, 20000, len(monthly_dates)),
        'Operating_Expenses': np.random.normal(-150000, 15000, len(monthly_dates)),
        'EBITDA': lambda x: x['Revenue'] + x['COGS'] + x['Operating_Expenses']
    })
    pnl_data['EBITDA'] = pnl_data['Revenue'] + pnl_data['COGS'] + pnl_data['Operating_Expenses']
    
    return cash_data, pnl_data

cash_data, pnl_data = load_financial_data()

# Key metrics row
col1, col2, col3, col4 = st.columns(4)

with col1:
    current_cash = cash_data['Operating_Cash'].iloc[-1]
    st.metric("Cash Position", f"${current_cash:,.0f}", f"{np.random.uniform(-5, 10):.1f}%")

with col2:
    monthly_revenue = pnl_data['Revenue'].iloc[-1]
    st.metric("Monthly Revenue", f"${monthly_revenue:,.0f}", f"{np.random.uniform(-2, 8):.1f}%")

with col3:
    monthly_ebitda = pnl_data['EBITDA'].iloc[-1]
    st.metric("Monthly EBITDA", f"${monthly_ebitda:,.0f}", f"{np.random.uniform(-10, 15):.1f}%")

with col4:
    ebitda_margin = (monthly_ebitda / monthly_revenue) * 100
    st.metric("EBITDA Margin", f"{ebitda_margin:.1f}%", f"{np.random.uniform(-2, 3):.1f}%")

# Role-specific sections
if "cash_flow" in current_permissions:
    st.subheader("💰 Cash Flow Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Cash flow trend
        fig_cash = go.Figure()
        fig_cash.add_trace(go.Scatter(x=cash_data['Date'], y=cash_data['Operating_Cash'], 
                                     name='Operating Cash', line=dict(color='green', width=3)))
        fig_cash.add_trace(go.Scatter(x=cash_data['Date'], y=cash_data['Investing_Cash'], 
                                     name='Investing Cash', line=dict(color='blue', width=3)))
        fig_cash.add_trace(go.Scatter(x=cash_data['Date'], y=cash_data['Financing_Cash'], 
                                     name='Financing Cash', line=dict(color='orange', width=3)))
        
        fig_cash.update_layout(title="Cash Flow Trends", xaxis_title="Date", yaxis_title="Cash ($)")
        st.plotly_chart(fig_cash, use_container_width=True)
    
    with col2:
        # Cash flow breakdown
        latest_flows = {
            'Operating': cash_data['Operating_Cash'].iloc[-1] - cash_data['Operating_Cash'].iloc[-30],
            'Investing': cash_data['Investing_Cash'].iloc[-1] - cash_data['Investing_Cash'].iloc[-30],
            'Financing': cash_data['Financing_Cash'].iloc[-1] - cash_data['Financing_Cash'].iloc[-30]
        }
        
        fig_breakdown = px.bar(x=list(latest_flows.keys()), y=list(latest_flows.values()),
                              title="30-Day Cash Flow by Category",
                              color=list(latest_flows.values()),
                              color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_breakdown, use_container_width=True)

if "budgets" in current_permissions:
    st.subheader("📋 Budget vs Actual")
    
    # Mock budget data
    budget_categories = ['Revenue', 'COGS', 'Marketing', 'Sales', 'R&D', 'Admin']
    budget_data = pd.DataFrame({
        'Category': budget_categories,
        'Budget': [500000, -200000, -50000, -40000, -80000, -30000],
        'Actual': [monthly_revenue, pnl_data['COGS'].iloc[-1], -45000, -42000, -75000, -32000]
    })
    budget_data['Variance'] = budget_data['Actual'] - budget_data['Budget']
    budget_data['Variance_Pct'] = (budget_data['Variance'] / abs(budget_data['Budget'])) * 100
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_budget = px.bar(budget_data, x='Category', y=['Budget', 'Actual'],
                           title="Budget vs Actual Comparison", barmode='group')
        st.plotly_chart(fig_budget, use_container_width=True)
    
    with col2:
        # Variance analysis
        fig_variance = px.bar(budget_data, x='Category', y='Variance_Pct',
                             title="Budget Variance (%)",
                             color='Variance_Pct',
                             color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_variance, use_container_width=True)

if "projects" in current_permissions:
    st.subheader("🎯 Project Financial Tracking")
    
    # Mock project data
    projects = pd.DataFrame({
        'Project': ['Product Launch', 'System Upgrade', 'Market Expansion', 'Cost Reduction'],
        'Budget': [200000, 150000, 300000, 100000],
        'Spent': [180000, 120000, 250000, 85000],
        'Remaining': [20000, 30000, 50000, 15000],
        'Status': ['On Track', 'Under Budget', 'At Risk', 'Complete']
    })
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_projects = px.bar(projects, x='Project', y=['Budget', 'Spent'],
                             title="Project Budget Utilization", barmode='group')
        st.plotly_chart(fig_projects, use_container_width=True)
    
    with col2:
        # Project status
        status_colors = {'On Track': 'green', 'Under Budget': 'blue', 'At Risk': 'orange', 'Complete': 'gray'}
        for _, project in projects.iterrows():
            color = status_colors.get(project['Status'], 'black')
            utilization = (project['Spent'] / project['Budget']) * 100
            st.markdown(f"**{project['Project']}**")
            st.markdown(f"<span style='color: {color}'>{project['Status']}</span> - {utilization:.1f}% utilized", unsafe_allow_html=True)
            st.progress(utilization / 100)
            st.markdown("---")

if "reconciliation" in current_permissions:
    st.subheader("🔍 Account Reconciliation Status")
    
    # Mock reconciliation data
    accounts = ['Cash - Operating', 'Cash - Savings', 'Accounts Receivable', 'Accounts Payable', 'Inventory']
    reconciliation_status = pd.DataFrame({
        'Account': accounts,
        'Last_Reconciled': pd.date_range(start=datetime.now()-timedelta(days=5), periods=5, freq='D'),
        'Status': np.random.choice(['Reconciled', 'Pending', 'Discrepancy'], 5),
        'Variance': np.random.uniform(-5000, 5000, 5)
    })
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Status overview
        for _, account in reconciliation_status.iterrows():
            status_color = {'Reconciled': 'green', 'Pending': 'orange', 'Discrepancy': 'red'}.get(account['Status'], 'gray')
            st.markdown(f"**{account['Account']}**")
            st.markdown(f"<span style='color: {status_color}'>{account['Status']}</span> | Last: {account['Last_Reconciled'].strftime('%Y-%m-%d')}", unsafe_allow_html=True)
            if account['Variance'] != 0:
                st.markdown(f"Variance: ${account['Variance']:,.0f}")
            st.markdown("---")
    
    with col2:
        # Reconciliation actions
        st.markdown("**⚡ Quick Actions**")
        if st.button("🔄 Reconcile All", use_container_width=True):
            st.success("Reconciliation process initiated")
        
        if st.button("📊 Variance Report", use_container_width=True):
            st.info("Generating variance analysis...")
        
        if st.button("🚨 Flag Discrepancies", use_container_width=True):
            st.warning("Discrepancies flagged for review")

# Financial alerts
st.subheader("🚨 Financial Alerts")

alerts = [
    {"type": "warning", "message": "Cash flow projection shows potential shortfall in 45 days"},
    {"type": "info", "message": "Q3 budget review scheduled for next week"},
    {"type": "success", "message": "All bank accounts reconciled successfully"},
    {"type": "error", "message": "Accounts payable aging report shows overdue items"}
]

for alert in alerts:
    if alert["type"] == "warning":
        st.warning(alert["message"])
    elif alert["type"] == "info":
        st.info(alert["message"])
    elif alert["type"] == "success":
        st.success(alert["message"])
    elif alert["type"] == "error":
        st.error(alert["message"])

# Footer
st.markdown("---")
st.markdown(f"**Financial Dashboard** | Role: {user_role} | Last Updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
