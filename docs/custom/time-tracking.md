# BOB Project Time Tracking & Estimation

This document provides guidelines for time tracking and effort estimation for all BOB Project team members. Consistent time tracking is essential for project visibility, resource allocation, and continuous improvement of our estimation process.

## Time Tracking Principles

The BOB Project follows these time tracking principles:

1. **Accuracy**: Track time as accurately as possible to build reliable historical data
2. **Consistency**: Use the same approach across the entire team
3. **Transparency**: Time data is visible to all team members
4. **Simplicity**: The tracking process should be straightforward and not overly time-consuming

## Issue Estimation Process

### When to Estimate

All issues should be estimated during these key events:

- During weekly planning meetings (for new issues)
- During backlog refinement sessions
- Upon issue creation (rough estimate)
- Before an issue is assigned to a team member (refined estimate)

### Estimation Units

- All estimates should be in **hours** of expected effort
- For issues expected to take more than 16 hours, consider breaking them into smaller issues

### Estimation Method

The BOB Project uses a collaborative estimation approach:

1. The issue creator provides an initial estimate based on their understanding
2. During planning/refinement meetings, team members discuss the issue and reach consensus
3. For complex issues, use Planning Poker technique with hour-based values (1, 2, 4, 8, 16)
4. Consider both complexity and uncertainty when providing estimates

### Adding Estimates to Issues

When creating or updating a GitHub issue:

1. Add the estimated hours in the issue description using the format: `Estimate: X hours` (maybe use a field in the issue description, TBD)
2. Use the GitHub time tracking extension to log estimates in the time tracking field
3. For issues with multiple tasks, break down estimates in a checklist format:
   ```
   - [ ] Task 1 (2 hours)
   - [ ] Task 2 (3 hours)
   - [ ] Task 3 (1 hour)
   ```

## Time Logging Process

### When to Log Time

Team members should log time:

- **Daily**: At the end of each workday
- **Per Issue**: When switching between different issues
- **Per Activity**: When switching between different activities on the same issue

### How to Log Time

To log time spent on an issue:

1. Add a comment to the GitHub issue with the time spent using the format: `/spent Xh`
2. Include a brief description of the work completed in the same comment
3. If the time spent differs significantly from the estimate, add an explanation

Example:
```
/spent 2h
Implemented the knowledge graph query interface and added unit tests.
```

### Time Tracking Categories

When logging time, categorize your effort using labels:

- **Development**: Coding, testing, and implementation
- **Research**: Investigating technologies, approaches, or solutions
- **Documentation**: Creating or updating documentation
- **Review**: Code reviews, design reviews, documentation reviews
- **Meeting**: Team discussions, planning sessions, demos
- **Support**: Helping other team members, responding to questions


### Team Time Reports

Team leads and project managers can access consolidated time reports:

1. Weekly time reports are automatically generated every Friday
2. Reports show time spent per team member, issue, and category
3. Comparison between estimated and actual time is highlighted

## Best Practices

- **Be Consistent**: Log time regularly using the same methodology
- **Be Specific**: Include meaningful details about what was accomplished
- **Be Honest**: Accurately report time spent, even if it exceeds estimates
- **Learn and Adjust**: Use historical data to improve future estimates
- **Minimum Granularity**: Don't track time in increments smaller than 30 minutes
- **Maximum Task Size**: Break down tasks larger than 8 hours into smaller, trackable units

## Common Scenarios

### Interrupted Work

If your work on an issue is interrupted:
1. Log the time spent so far
2. When returning to the issue, continue tracking from where you left off

### Collaborative Work

When multiple people work on the same issue simultaneously:
1. Each person logs their own time separately
2. Mention collaboration in the comments: `"Paired with @username"`

### Meetings Related to Issues

For meetings specific to an issue:
1. Log the meeting time against that issue
2. Include "[Meeting]" in the time tracking comment

### General Meetings

For general project meetings not tied to a specific issue:
1. Log time against the designated "Team Meetings" issue
2. Include the meeting topic in your comment

## Monthly Time Analysis

At the end of each month, the project team will:

1. Review actual vs. estimated time for completed issues
2. Identify patterns and areas for improvement
3. Adjust estimation approaches based on historical data
4. Share insights with the team to improve future estimations

By following these time tracking and estimation guidelines, we ensure transparency and accountability while continuously improving our project management processes. 