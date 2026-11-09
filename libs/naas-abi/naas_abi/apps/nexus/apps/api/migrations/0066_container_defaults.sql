-- Each organization and workspace has an IAM access policy ("<X> access") and two
-- groups whose members follow the roles held there ("<X> members", "<X> admins").
-- IAM holds them; this table says which they are, by the container's IAM name
-- (services/iam/container_defaults.py).
CREATE TABLE IF NOT EXISTS container_defaults (
    container VARCHAR(512) PRIMARY KEY,
    access_policy_id VARCHAR(64),
    members_group_id VARCHAR(64),
    admins_group_id VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
