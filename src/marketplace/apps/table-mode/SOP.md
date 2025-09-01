# Table Mode - Standard Operating Procedure

## 🎯 Purpose
The Table Mode interface provides structured data visualization and manipulation capabilities with advanced filtering, sorting, editing, and export functionality.

## 🚀 How to Run
```bash
cd src/core/user-interfaces/table-mode
streamlit run table_interface.py
```
Access at: http://localhost:8522

## 👥 User Roles
- **Data Analysts:** Exploring and analyzing datasets
- **Business Users:** Reviewing reports and metrics
- **Administrators:** Managing system data
- **Developers:** Integrating table functionality

## 📋 Daily Operations

### Morning Setup (5 minutes)
1. **Select Data Source:** Choose between sample data, CSV upload, or database
2. **Configure View Mode:** Select appropriate table view for your task
3. **Set Display Options:** Customize table appearance and pagination
4. **Apply Initial Filters:** Set up basic filters for your focus area

### Core Workflow
1. **Load Data:** Import or connect to your data source
2. **Apply Filters:** Use search and filter controls to focus on relevant data
3. **Analyze Data:** Review summary metrics and visualizations
4. **Manipulate Data:** Edit, sort, or reorganize as needed
5. **Export Results:** Download filtered data or generate reports

## 🎯 View Modes

### Standard Table
- **Use Case:** General data viewing and analysis
- **Features:** Sorting, filtering, pagination
- **Best For:** Large datasets, read-only analysis

### Editable Grid
- **Use Case:** Data entry and modification
- **Features:** In-line editing, change tracking
- **Best For:** Data maintenance, corrections, updates

### Summary View
- **Use Case:** High-level overview and aggregation
- **Features:** Grouped data, calculated totals
- **Best For:** Executive reporting, trend analysis

### Pivot Table
- **Use Case:** Multi-dimensional data analysis
- **Features:** Dynamic grouping, cross-tabulation
- **Best For:** Complex analysis, business intelligence

## 🔍 Filtering & Search

### Text Search
- **Global Search:** Searches across all visible columns
- **Case Insensitive:** Finds partial matches
- **Real-time:** Updates results as you type

### Column Filters
- **Category Filter:** Filter by specific categories
- **Status Filter:** Filter by record status
- **Date Range:** Filter by date periods
- **Custom Filters:** Add filters for any column

### Advanced Filtering
- **Multiple Criteria:** Combine multiple filters
- **Exclude Filters:** Show everything except specified criteria
- **Saved Filters:** Store frequently used filter combinations

## 📊 Data Analysis Features

### Summary Metrics
- **Total Records:** Count of filtered records
- **Calculated Totals:** Sum, average, min, max values
- **Progress Tracking:** Completion rates and percentages
- **Custom Metrics:** Domain-specific calculations

### Visualizations
- **Distribution Charts:** See data patterns at a glance
- **Progress Histograms:** Understand completion status
- **Category Breakdowns:** Pie charts for categorical data
- **Trend Analysis:** Time-based visualizations

### Column Management
- **Show/Hide Columns:** Customize visible data
- **Reorder Columns:** Arrange data for optimal viewing
- **Column Sorting:** Sort by any column, multiple criteria
- **Column Totals:** Show calculated totals per column

## 📄 Pagination & Performance

### Page Size Options
- **10 rows:** Quick scanning, minimal scrolling
- **25 rows:** Standard view for most use cases
- **50 rows:** Detailed analysis with context
- **100 rows:** Power user view for extensive data
- **All rows:** Complete dataset view (use carefully)

### Performance Optimization
- **Lazy Loading:** Load data as needed
- **Efficient Filtering:** Client-side filtering for speed
- **Caching:** Store frequently accessed data
- **Progressive Loading:** Show data while loading more

## 💾 Export & Integration

### Export Formats
- **CSV:** Universal format for data exchange
- **Excel:** Rich formatting and formulas
- **JSON:** Structured data for APIs
- **PDF:** Formatted reports for sharing

### Export Options
- **Filtered Data:** Export only visible/filtered records
- **All Data:** Export complete dataset
- **Selected Columns:** Export specific data fields
- **Formatted Reports:** Include charts and summaries

### Integration Capabilities
- **API Endpoints:** Connect to external data sources
- **Database Connections:** Direct database integration
- **File Uploads:** CSV, Excel, JSON import
- **Real-time Updates:** Live data synchronization

## ⚙️ Configuration Options

### Display Settings
- **Row Numbers:** Show/hide index column
- **Column Totals:** Display calculated totals
- **Highlight Changes:** Visual indicators for edits
- **Compact View:** Reduce spacing for more data

### Interaction Settings
- **Edit Mode:** Enable/disable data editing
- **Multi-select:** Allow multiple row selection
- **Drag & Drop:** Enable row reordering
- **Keyboard Navigation:** Arrow key navigation

### Performance Settings
- **Cache Duration:** How long to store data
- **Refresh Interval:** Automatic data updates
- **Batch Size:** Records loaded per request
- **Memory Limits:** Maximum data in memory

## 🚨 Best Practices

### Data Management
1. **Regular Exports:** Backup important filtered views
2. **Validate Edits:** Review changes before saving
3. **Use Filters Wisely:** Start broad, then narrow down
4. **Monitor Performance:** Watch for slow operations

### Analysis Workflow
1. **Start with Summary:** Review high-level metrics first
2. **Progressive Filtering:** Apply filters incrementally
3. **Use Visualizations:** Charts reveal patterns quickly
4. **Document Findings:** Export key insights

### Performance Optimization
- **Limit Data Size:** Use pagination for large datasets
- **Efficient Filters:** Apply most selective filters first
- **Cache Results:** Save frequently used views
- **Regular Cleanup:** Clear old cached data

## 🔧 Troubleshooting

### Common Issues
- **Slow Loading:** Reduce page size, add filters
- **Memory Errors:** Use pagination, clear cache
- **Export Failures:** Check data size, format compatibility
- **Filter Problems:** Clear filters, refresh data

### Performance Issues
- **Large Datasets:** Use server-side filtering
- **Complex Calculations:** Pre-calculate when possible
- **Multiple Users:** Implement proper caching
- **Real-time Updates:** Balance frequency vs performance

## 📈 Advanced Features

### Bulk Operations
- **Batch Editing:** Modify multiple records at once
- **Bulk Delete:** Remove multiple records
- **Mass Updates:** Apply changes to filtered data
- **Import/Merge:** Combine datasets

### Collaboration Features
- **Shared Views:** Save and share filter configurations
- **Comments:** Add notes to specific records
- **Change Tracking:** Audit trail for modifications
- **User Permissions:** Control access levels

### Automation
- **Scheduled Exports:** Automatic report generation
- **Alert Rules:** Notifications for data changes
- **Workflow Integration:** Connect to business processes
- **API Access:** Programmatic data manipulation

## 🎯 Integration Guidelines

### For Developers
- Customize column definitions for domain data
- Implement domain-specific filters and calculations
- Add custom export formats and destinations
- Integrate with existing data sources and APIs

### For Business Users
- Create saved filter sets for common analyses
- Use summary views for executive reporting
- Export data for external analysis tools
- Set up alerts for important data changes

---

*This SOP ensures effective use of the Table Mode interface for data analysis, management, and reporting across all ABI modules.*
