# Account Reconciliation - Standard Operating Procedure

## 🎯 Purpose
Multi-account reconciliation system for Treasurer, Accountant, Financial Controller, and Auditor collaboration.

## 👥 User Roles & Responsibilities

### Treasurer
- **Primary Focus:** Bank account reconciliation, cash management
- **Responsibilities:** Daily cash reconciliation, liquidity monitoring
- **Authority:** Approve bank transfers, resolve cash discrepancies

### Accountant
- **Primary Focus:** Transaction matching, detailed reconciliation
- **Responsibilities:** Process reconciliations, investigate variances
- **Authority:** Make journal entries, flag discrepancies

### Financial Controller
- **Primary Focus:** Oversight, approval, variance analysis
- **Responsibilities:** Review reconciliations, approve adjustments
- **Authority:** Approve significant variances, policy decisions

### Auditor
- **Primary Focus:** Compliance, audit trails, risk assessment
- **Responsibilities:** Review controls, validate processes
- **Authority:** Request documentation, recommend improvements

## 🚀 How to Run

```bash
# Navigate to reconciliation folder
cd src/domain-experts/user-interfaces/reconciliation

# Start the interface
streamlit run account_reconciliation.py

# Access in browser
open http://localhost:8501
```

## 📋 Daily Reconciliation Process

### Step 1: Initial Setup (5 minutes)
1. Select account type from sidebar (Bank Accounts, Credit Cards, etc.)
2. Choose reconciliation period (Current Month recommended for daily)
3. Review summary metrics at top of dashboard

### Step 2: Account Status Review (10 minutes)
1. **Check Summary Metrics:**
   - Total Variance (target: <$1,000)
   - Reconciled Accounts (target: 80%+)
   - Pending Reviews (monitor queue)
   - Discrepancies (investigate immediately)

2. **Priority Review:**
   - Focus on accounts with highest absolute variance
   - Address red status items first
   - Review aging of outstanding items

### Step 3: Detailed Analysis (20 minutes)
1. **Account Reconciliation Table:**
   - Green background: Reconciled ✅
   - Yellow background: Minor variance (<$1,000)
   - Red background: Significant discrepancy (>$1,000)

2. **Outstanding Items Analysis:**
   - Review pie chart for item type distribution
   - Check aging scatter plot for old items
   - Prioritize items >7 days outstanding

### Step 4: Action Items (15 minutes)
1. **Auto-Match Transactions:** Run for efficiency
2. **Flag Discrepancies:** Mark items needing investigation
3. **Generate Reports:** Create documentation
4. **Mark as Reconciled:** Complete processed accounts

## 🔄 Reconciliation Workflow

### Phase 1: Data Import (9:00 AM)
- **Status:** ✅ Complete
- **Action:** Bank statements automatically imported
- **Responsibility:** System/Accountant

### Phase 2: Auto-Matching (9:15 AM)
- **Status:** ✅ Complete  
- **Action:** System matches obvious transactions
- **Responsibility:** System/Accountant verification

### Phase 3: Manual Review (9:30 AM)
- **Status:** 🔄 In Progress
- **Action:** Review unmatched items
- **Responsibility:** Accountant (primary), Treasurer (cash accounts)

### Phase 4: Investigation (10:00 AM)
- **Status:** ⏳ Pending
- **Action:** Research discrepancies
- **Responsibility:** Accountant investigates, escalate to Controller

### Phase 5: Management Approval (11:00 AM)
- **Status:** ⏳ Pending
- **Action:** Approve adjustments >$500
- **Responsibility:** Financial Controller approval required

### Phase 6: Final Reconciliation (11:30 AM)
- **Status:** ⏳ Pending
- **Action:** Complete and document reconciliation
- **Responsibility:** Accountant finalizes, Treasurer reviews cash

## 📊 Understanding the Data

### Account Status Colors
- **Green:** Reconciled - no action needed
- **Orange:** Pending - normal processing
- **Red:** Discrepancy - immediate attention required
- **Blue:** Under Review - investigation in progress

### Outstanding Items Types
- **Outstanding Checks:** Issued but not cleared
- **Deposits in Transit:** Deposited but not posted
- **Bank Charges:** Fees not yet recorded
- **Wire Transfers:** Large transfers in process

### Variance Thresholds
- **$0:** Perfect reconciliation
- **<$1,000:** Acceptable variance (yellow)
- **>$1,000:** Significant discrepancy (red)
- **>$5,000:** Critical variance (escalate immediately)

## ⚠️ Exception Handling

### High Priority Discrepancies
1. **Variance >$5,000:**
   - Immediately notify Financial Controller
   - Document investigation steps
   - Escalate to Treasurer if cash-related

2. **Items >14 Days Outstanding:**
   - Research original transaction
   - Contact bank if necessary
   - Consider write-off procedures

3. **Recurring Variances:**
   - Identify root cause
   - Implement process improvements
   - Update reconciliation procedures

### Escalation Matrix
| Variance Amount | Action Required | Approval Level |
|----------------|-----------------|----------------|
| <$100 | Accountant resolves | None |
| $100-$500 | Document and resolve | Supervisor review |
| $500-$5,000 | Investigation required | Controller approval |
| >$5,000 | Immediate escalation | Treasurer + Controller |

## 📈 Performance Metrics

### Daily Targets
- **Reconciliation Completion:** 95% by 12:00 PM
- **Variance Resolution:** <$1,000 total variance
- **Outstanding Items:** <5 items >7 days old
- **Processing Time:** <60 minutes total

### Weekly Targets
- **Perfect Reconciliations:** 80% of accounts
- **Average Resolution Time:** <2 hours for discrepancies
- **Process Improvements:** 1 enhancement per week
- **Training Updates:** Review procedures weekly

## 🔍 Quality Control Checklist

### Before Starting Reconciliation
- [ ] Bank statements downloaded and verified
- [ ] Previous day reconciliation completed
- [ ] Outstanding items list updated
- [ ] System access confirmed

### During Reconciliation
- [ ] All accounts reviewed for variances
- [ ] Outstanding items aged and prioritized
- [ ] Discrepancies documented with evidence
- [ ] Approvals obtained for adjustments

### After Reconciliation
- [ ] All variances resolved or documented
- [ ] Reports generated and distributed
- [ ] Next day preparation completed
- [ ] Process improvements noted

## 🚨 Emergency Procedures

### Critical Discrepancy (>$10,000)
1. **Immediate Actions:**
   - Stop all related transactions
   - Notify Treasurer and Controller immediately
   - Document all evidence
   - Secure relevant documentation

2. **Investigation Protocol:**
   - Form investigation team
   - Review all related transactions
   - Contact external parties if needed
   - Prepare detailed report

3. **Resolution Process:**
   - Implement corrective actions
   - Update procedures to prevent recurrence
   - Communicate resolution to stakeholders
   - Document lessons learned

### System Failures
1. **Backup Procedures:**
   - Switch to manual reconciliation
   - Use backup data sources
   - Document manual processes
   - Notify IT support immediately

## 📞 Contact Information

### Internal Contacts
- **Treasurer:** ext. 1001 (cash/liquidity issues)
- **Financial Controller:** ext. 1002 (approvals/policy)
- **Accounting Manager:** ext. 1003 (process questions)
- **IT Support:** ext. 2000 (system issues)

### External Contacts
- **Bank Relationship Manager:** Direct line for urgent issues
- **External Auditor:** For compliance questions
- **System Vendor:** For technical support

## 📚 Reference Documents
- Bank Reconciliation Policy (Document #FIN-001)
- Chart of Accounts (Document #FIN-002)
- Approval Authority Matrix (Document #FIN-003)
- Emergency Contact List (Document #ADM-001)
