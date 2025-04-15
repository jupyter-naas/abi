# Ontology Agent Use Case Documentation

## Overview
The ontology agent (Abi) helps users manage and interact with an organizational knowledge graph. It can handle various operations including adding people, skills, relationships, and events.

## Key Capabilities

### 1. Managing Skills
- Add new skills to the ontology
- Associate skills with people
- Search for existing skills

Example:
```python
# Adding skills
You: "Add skill 'Excel', 'Product Owner', 'Python'"
# The agent will:
# 1. Search for existing skills
# 2. Add missing skills to the ontology
# 3. Return URIs for the new skills

# Associating skills with people
You: "Add these skills to Florent"
# The agent will:
# 1. Search for the person
# 2. Link the skills to the person's record
```

### 2. Managing People
- Add new people to the ontology
- Record employment information
- Track relationships and interactions

Example:
```python
# Adding employment information
You: "I am Florent and I work for Naas since 2021"
# The agent will:
# 1. Search for the company
# 2. Create an employment record
# 3. Link the person to the company

# Recording interactions
You: "I spoke with Jeremy Ravenel and Maxime Jublou today"
# The agent will:
# 1. Add people if they don't exist
# 2. Create a meeting event
# 3. Link all participants
```

### 3. Recording Facts and Preferences
- Store personal preferences
- Add factual information
- Link entities with properties

Example:
```python
You: "Add the fact that Maxime Jublou likes tartiflette"
# The agent will:
# 1. Use appropriate ontology classes
# 2. Create a record of the preference
# 3. Link the person to the preference
```

## Best Practices

1. **Providing Complete Information**
   - Use full names for people (first and last name)
   - Include dates when relevant
   - Specify relationships clearly

2. **Searching Before Adding**
   - The agent automatically searches for existing records
   - Prevents duplicate entries
   - Maintains data consistency

3. **Verification**
   - The agent confirms actions taken
   - Provides URIs for new entries
   - Reports success or failure of operations

## Common Use Cases

1. **Team Member Onboarding**
   ```python
   # Add new team member
   "Add person John Smith"
   # Add their skills
   "Add skills 'JavaScript', 'React' to John Smith"
   # Record employment
   "John Smith works for Naas since 2023"
   ```

2. **Recording Meetings**
   ```python
   # Document a meeting
   "I had a meeting with Alice Jones and Bob Wilson today"
   # Add context if needed
   "The meeting was about project planning"
   ```

3. **Skill Management**
   ```python
   # Add new skills
   "Add skill 'Machine Learning'"
   # Associate with team members
   "Add this skill to Sarah Brown"
   ```

## Error Handling

The agent will:
- Search for existing records before adding new ones
- Request clarification when information is ambiguous
- Provide feedback on actions taken
- Report any issues or limitations encountered

## Future Enhancements

The ontology agent is continuously evolving. Planned improvements include:
- Enhanced relationship tracking
- More detailed event recording
- Advanced search capabilities
- Additional property types
- Improved context understanding

## Support

For questions or issues:
- Provide clear, complete information
- Include relevant URIs when referencing existing records
- Specify the desired outcome
