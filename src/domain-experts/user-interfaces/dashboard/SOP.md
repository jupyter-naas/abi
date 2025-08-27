# Financial Dashboard - Standard Operating Procedure

## 🎯 Purpose
Multi-role financial analysis dashboard for Treasurer, Financial Controller, Accountant, and CFO collaboration.

## 👥 User Roles & Access

### Treasurer
- **Primary Focus:** Cash flow management, liquidity analysis
- **Access:** Cash flow trends, bank reconciliation status, investment tracking
- **Actions:** Monitor daily cash position, review liquidity ratios

### Financial Controller  
- **Primary Focus:** Budget oversight, project financials, variance analysis
- **Access:** Budget vs actual, project tracking, cross-departmental financials
- **Actions:** Approve budget variances, review project spend, forecast analysis

### Accountant
- **Primary Focus:** Transaction details, reconciliation, compliance
- **Access:** Account reconciliation, transaction logs, audit trails
- **Actions:** Process reconciliations, flag discrepancies, maintain records

### CFO
- **Primary Focus:** Strategic overview, executive reporting
- **Access:** All modules and data (full permissions)
- **Actions:** Strategic decisions, executive reporting, risk assessment

## 🚀 How to Run

```bash
# Navigate to dashboard folder
cd src/domain-experts/user-interfaces/dashboard

# Start the interface
streamlit run financial_dashboard.py

# Access in browser
open http://localhost:8502
```

## 📋 Step-by-Step Usage

### 1. Initial Setup
1. Select your role from sidebar dropdown
2. Choose time period (Current Month, Last 3 Months, YTD, Last 12 Months)
3. Review your access permissions displayed in sidebar

### 2. Dashboard Overview
- **Top Metrics:** Cash Position, Monthly Revenue, EBITDA, EBITDA Margin
- **Color Coding:** Green (good), Yellow (caution), Red (attention needed)
- **Trend Indicators:** Percentage changes from previous period

### 3. Cash Flow Analysis (Treasurer/CFO Access)
- **Left Chart:** Operating, Investing, Financing cash flow trends
- **Right Chart:** 30-day cash flow breakdown by category
- **Usage:** Monitor cash position, identify cash flow patterns

### 4. Budget vs Actual (Controller/CFO Access)
- **Left Chart:** Budget vs Actual comparison by category
- **Right Chart:** Variance percentage analysis
- **Usage:** Track budget performance, identify over/under spending

### 5. Project Financial Tracking (Controller/CFO Access)
- **Left Chart:** Project budget utilization
- **Right Panel:** Project status with utilization percentages
- **Usage:** Monitor project spend, identify at-risk projects

### 6. Account Reconciliation Status (Accountant/All Roles)
- **Left Panel:** Account reconciliation status by account
- **Right Panel:** Quick reconciliation actions
- **Usage:** Track reconciliation progress, identify discrepancies

## ⚡ Quick Actions Guide

### Daily Operations (Treasurer)
1. Check cash position metric
2. Review cash flow trends
3. Monitor liquidity alerts
4. Verify bank reconciliation status

### Weekly Reviews (Financial Controller)
1. Analyze budget variances
2. Review project financial status
3. Approve significant variances
4. Update financial forecasts

### Monthly Close (Accountant)
1. Complete all account reconciliations
2. Review variance reports
3. Process journal entries
4. Generate compliance reports

### Executive Review (CFO)
1. Review all key metrics
2. Analyze financial trends
3. Assess risk indicators
4. Prepare board reports

## 🔍 Data Interpretation

### Metric Colors
- **Green:** Performance within acceptable range
- **Yellow:** Caution - monitor closely
- **Red:** Action required - investigate immediately

### Chart Types
- **Line Charts:** Trends over time
- **Bar Charts:** Comparisons between categories
- **Pie Charts:** Proportional breakdowns
- **Progress Bars:** Completion percentages

## 🚨 Alert Management

### Financial Alerts Priority
1. **Error (Red):** Immediate action required
2. **Warning (Yellow):** Monitor and plan action
3. **Info (Blue):** Informational updates
4. **Success (Green):** Positive confirmations

### Escalation Process
1. **Level 1:** Accountant investigates and resolves
2. **Level 2:** Financial Controller reviews and approves
3. **Level 3:** Treasurer implements cash management actions
4. **Level 4:** CFO makes strategic decisions

## 📊 Reporting Schedule

### Daily Reports
- Cash position summary
- Critical alerts review
- Reconciliation status

### Weekly Reports  
- Budget variance analysis
- Project financial updates
- Cash flow projections

### Monthly Reports
- Complete financial dashboard export
- Executive summary preparation
- Compliance documentation

## 🔧 Troubleshooting

### Common Issues
1. **Data not loading:** Check date range selection
2. **Charts not displaying:** Refresh browser, check data filters
3. **Permission errors:** Verify role selection matches your access level
4. **Slow performance:** Reduce date range, clear browser cache

### Support Contacts
- **Technical Issues:** IT Support
- **Data Questions:** Finance Team Lead  
- **Access Problems:** System Administrator
- **Process Questions:** Finance Manager

## 📈 Best Practices

### Data Accuracy
- Verify data sources daily
- Cross-reference with source systems
- Report discrepancies immediately
- Maintain audit trails

### Collaboration
- Use role-specific views appropriately
- Document significant findings
- Communicate alerts promptly
- Share insights across teams

### Security
- Log out when finished
- Don't share login credentials
- Report suspicious activity
- Follow data privacy guidelines
