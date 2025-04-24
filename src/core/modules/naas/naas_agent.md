# Naas Agent

## Description

The Naas Agent is a core agent responsible for managing and interacting with Naas workspaces and services. It provides a natural language interface for creating, managing, and interacting with Naas workspaces, plugins, ontologies, storage, and more using an o3-mini model.

## Capabilities

- **Workspace Management**: Create, retrieve, update, and delete Naas workspaces.
- **Plugin Management**: Add, retrieve, update, and delete plugins within workspaces.
- **Ontology Management**: Create, retrieve, update, and delete ontologies.
- **User Management**: Invite users to workspaces, manage user roles and permissions.
- **Secret Management**: Store, retrieve, update, and delete secrets.
- **Storage Management**: Create and manage storage spaces, upload and manage assets.

## Use Cases

### Workspace Management

#### Create Workspace
Create a new Naas workspace with customization options.

Examples:
- "Create a new workspace called 'Data Science Projects'"
- "Create a workspace named 'Marketing Analytics' with primary color #48DD82"

#### Retrieve Workspaces
Get information about existing workspaces.

Examples:
- "Show me all my workspaces"
- "What's my personal workspace ID?"
- "Get details for workspace with ID ABC123"

#### Update Workspace
Modify an existing workspace's settings.

Examples:
- "Update workspace ABC123 with a new name 'Client Projects'"
- "Change the logo for workspace ABC123"

#### Delete Workspace
Remove a workspace.

Examples:
- "Delete workspace ABC123"
- "Remove the workspace named 'Old Project'"

### Plugin Management

#### Create Plugin
Add a new plugin to a workspace.

Examples:
- "Add a new plugin to workspace ABC123"
- "Create a chatbot plugin in my personal workspace"

#### Retrieve Plugins
List plugins in a workspace.

Examples:
- "Show me all plugins in workspace ABC123"
- "Get details about plugin XYZ789 in workspace ABC123"

#### Update Plugin
Modify an existing plugin.

Examples:
- "Update the configuration for plugin XYZ789 in workspace ABC123"
- "Change the settings of my chatbot plugin"

#### Delete Plugin
Remove a plugin from a workspace.

Examples:
- "Delete plugin XYZ789 from workspace ABC123"
- "Remove the chatbot plugin from my personal workspace"

### Ontology Management

#### Create Ontology
Add a new ontology to a workspace.

Examples:
- "Create a new ontology named 'Finance' in workspace ABC123"
- "Add a domain-level ontology called 'Marketing Terms' to my personal workspace"

#### Retrieve Ontologies
List ontologies in a workspace.

Examples:
- "Show me all ontologies in workspace ABC123"
- "Get details about ontology ONT456 in workspace ABC123"

#### Update Ontology
Modify an existing ontology.

Examples:
- "Update the source for ontology ONT456 in workspace ABC123"
- "Make ontology 'Marketing Terms' public"

#### Delete Ontology
Remove an ontology from a workspace.

Examples:
- "Delete ontology ONT456 from workspace ABC123"
- "Remove the 'Finance' ontology from my personal workspace"

### User Management

#### Invite User
Add a new user to a workspace.

Examples:
- "Invite user@example.com to workspace ABC123 as a member"
- "Add john@company.com as an admin to my personal workspace"

#### Manage Users
View and update user information.

Examples:
- "Show me all users in workspace ABC123"
- "Change user UID123 role to admin in workspace ABC123"
- "Remove user UID123 from workspace ABC123"

### Secret Management

#### Create Secret
Store sensitive information securely.

Examples:
- "Create a new secret called 'API_KEY' with value 'abcdef123456'"
- "Store my database password as a secret"

#### Manage Secrets
View, update, and delete secrets.

Examples:
- "Show me all my secret names"
- "Update the value of secret SID123"
- "Delete secret 'OLD_API_KEY'"

### Storage Management

#### Create Storage
Set up a new storage space.

Examples:
- "Create a new storage called 'images' in workspace ABC123"
- "Set up storage for document files in my personal workspace"

#### Upload Assets
Store files in Naas storage.

Examples:
- "Upload a file to 'images' storage in workspace ABC123"
- "Store this image as a public asset in my documents storage"

#### Manage Storage
View storage information and contents.

Examples:
- "List all storage in workspace ABC123"
- "Show me all files in the 'images' storage with prefix 'avatars/'" 