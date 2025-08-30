# Domain Expert User Interfaces

Multi-role GUI patterns for domain experts built with Streamlit. These interfaces enable cross-functional collaboration where multiple domain experts can access shared tools and data.

## 🏗️ Architecture

Each interface is designed as a **reusable pattern** that multiple domain experts can use:

- **Role-based access control** - Different permissions based on user role
- **Cross-functional data sharing** - Financial Controller can access Treasurer's data
- **Multi-use workflows** - Same interface serves different expert needs
- **Collaborative features** - Activity feeds show actions by different roles

## 📋 Available Interfaces

### 1. Financial Dashboard (`dashboard/`)
**Multi-use:** Treasurer, Financial Controller, Accountant, CFO
- Cash flow analysis and tracking
- Budget vs actual comparisons
- Project financial tracking
- Account reconciliation status
- Role-based permissions and data access

### 2. Account Reconciliation (`reconciliation/`)
**Multi-use:** Treasurer, Accountant, Financial Controller, Auditor
- Multi-account reconciliation (bank, credit, investment)
- Variance analysis and visualization
- Outstanding items aging analysis
- Workflow management and approvals
- Cross-role collaboration tracking

### 3. Project Management Board (`project-board/`)
**Multi-use:** Project Manager, Software Engineer, DevOps Engineer, Product Manager
- Kanban board views
- Timeline and Gantt charts
- Resource allocation and capacity planning
- Sprint planning and burndown charts
- Risk analysis and blocked projects

### 4. Scheduling & Calendar (`calendar/`)
**Multi-use:** Project Manager, HR Manager, Sales Rep, Account Executive, Community Manager
- Multi-view calendars (week, month, day, agenda)
- Resource booking (rooms, equipment)
- Meeting scheduling and management
- Calendar analytics and utilization
- Role-specific scheduling needs

## 🚀 Quick Start

### Prerequisites
```bash
# Install dependencies
pip install streamlit pandas plotly numpy
```

### Running an Interface

1. **Navigate to interface directory:**
```bash
cd src/domain-experts/user-interfaces/[interface-name]
```

2. **Run the Streamlit app:**
```bash
streamlit run [interface-file].py
```

3. **Access in browser:**
Open `http://localhost:8501`

### Example Commands

```bash
# Account Reconciliation (Port 8501)
cd src/domain-experts/user-interfaces/reconciliation
streamlit run account_reconciliation.py
# Access: http://localhost:8501

# Financial Dashboard (Port 8502)
cd src/domain-experts/user-interfaces/dashboard
streamlit run financial_dashboard.py
# Access: http://localhost:8502

# Project Management Board (Port 8503)
cd src/domain-experts/user-interfaces/project-board
streamlit run project_management.py
# Access: http://localhost:8503

# Scheduling Interface (Port 8504)
cd src/domain-experts/user-interfaces/calendar
streamlit run scheduling_interface.py
# Access: http://localhost:8504
```

### Running Multiple Interfaces Simultaneously

You can run all interfaces at the same time since they use different ports:

```bash
# Terminal 1
cd src/domain-experts/user-interfaces/reconciliation && streamlit run account_reconciliation.py

# Terminal 2  
cd src/domain-experts/user-interfaces/dashboard && streamlit run financial_dashboard.py

# Terminal 3
cd src/domain-experts/user-interfaces/project-board && streamlit run project_management.py

# Terminal 4
cd src/domain-experts/user-interfaces/calendar && streamlit run scheduling_interface.py
```

**Access URLs:**
- Account Reconciliation: http://localhost:8501
- Financial Dashboard: http://localhost:8502  
- Project Management: http://localhost:8503
- Scheduling Center: http://localhost:8504

## 📖 How to Use

### Role Selection
Most interfaces include a role selector in the sidebar:
- Choose your domain expert role (Treasurer, Project Manager, etc.)
- Interface adapts permissions and available features
- Data visibility changes based on role

### Navigation
- **Sidebar Controls:** Filters, date ranges, role selection
- **Main Dashboard:** Key metrics and visualizations
- **Action Buttons:** Quick operations and workflows
- **Detail Tables:** Comprehensive data views with styling

### Cross-Functional Usage Examples

#### Financial Controller accessing Treasurer data:
1. Open Financial Dashboard
2. Select "Financial Controller" role
3. Access cash flow data from Treasurer's reconciliation
4. Review project-based financial tracking
5. Approve budget variances

#### Project Manager using shared calendar:
1. Open Scheduling Interface
2. Select "Project Manager" role
3. View team availability and resource bookings
4. Schedule project meetings and deadlines
5. Track project milestone dates

## 🔧 Customization

### Adding New Roles
1. Update role selector in sidebar:
```python
user_role = st.sidebar.selectbox(
    "Your Role",
    ["Existing Role", "New Role"]
)
```

2. Add role-based permissions:
```python
role_permissions = {
    "New Role": ["permission1", "permission2"]
}
```

3. Implement role-specific features:
```python
if "permission1" in current_permissions:
    # Role-specific functionality
```

### Modifying Data Sources
Replace mock data functions with real data connections:
```python
@st.cache_data
def load_real_data():
    # Connect to your database/API
    # Return pandas DataFrame
    pass
```

### Styling and Branding
- Modify color schemes in plotly charts
- Update page configuration and titles
- Add company logos and branding elements

## 🎯 Interface Patterns

### Multi-Role Access Pattern
```python
# Role-based data filtering
if user_role == "Treasurer":
    data = get_treasury_data()
elif user_role == "Financial Controller":
    data = get_controller_data()
```

### Cross-Functional Data Sharing
```python
# Shared data access across roles
treasury_data = load_treasury_data()  # Treasurer creates
controller_view = filter_for_controller(treasury_data)  # Controller accesses
```

### Collaborative Activity Tracking
```python
activities = [
    {"user": "Sarah (Treasurer)", "action": "Reconciled account"},
    {"user": "Mike (Controller)", "action": "Approved variance"}
]
```

## 🛠️ Development

### Adding New Interfaces
1. Create new folder: `src/domain-experts/user-interfaces/[pattern-name]/`
2. Create main interface file: `[pattern-name]_interface.py`
3. Follow existing patterns for:
   - Role selection
   - Data loading
   - Multi-column layouts
   - Action buttons
   - Activity feeds

### Testing
```bash
# Test interface locally
streamlit run interface_file.py

# Check for errors in terminal
# Verify all charts and tables render correctly
# Test role switching functionality
```

## 📊 Data Requirements

### Expected Data Formats
- **Pandas DataFrames** for tabular data
- **Date columns** in datetime format
- **Numeric columns** for calculations and charts
- **Categorical columns** for filtering and grouping

### Sample Data Structure
```python
# Financial data example
financial_data = pd.DataFrame({
    'Date': pd.date_range('2024-01-01', periods=30),
    'Amount': np.random.normal(10000, 2000, 30),
    'Category': ['Revenue', 'Expense', 'Investment'],
    'Status': ['Confirmed', 'Pending', 'Approved']
})
```

## 🔒 Security Considerations

- **Role-based access control** implemented in UI layer
- **Data filtering** based on user permissions
- **Audit trails** for all user actions
- **Session management** for multi-user environments

## 📈 Performance Tips

- Use `@st.cache_data` for expensive data operations
- Implement data pagination for large datasets
- Optimize plotly charts for rendering speed
- Consider data sampling for initial views

## 🤝 Contributing

1. Follow existing interface patterns
2. Maintain multi-role compatibility
3. Include comprehensive documentation
4. Test across different user roles
5. Ensure responsive design for various screen sizes

## 📞 Support

For questions about specific interfaces or adding new patterns, refer to the individual interface files for detailed implementation examples.
