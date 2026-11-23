-- The X "Recent Tweets" app is a remote module's now (#1423): its id goes from
-- naas_abi_marketplace.applications.x:x_proxy (the engine module) to
-- remote/applications.x:x_proxy. The rows that name it follow, so the one-time
-- move of the app toggles into policies (services/iam/policy_tree) grants the new
-- app where it has not run yet. IAM's own names are moved at start
-- (services/iam/module_moves). Where a workspace already holds both rows, its row
-- of the new id is kept. The id before the rename to x_proxy
-- (naas_abi_marketplace.applications.x:x) is left: nothing has mapped it since.
DELETE FROM app_configs
WHERE app_id = 'naas_abi_marketplace.applications.x:x_proxy'
  AND workspace_id IN (
    SELECT workspace_id FROM app_configs WHERE app_id = 'remote/applications.x:x_proxy'
  );
UPDATE app_configs
SET app_id = 'remote/applications.x:x_proxy'
WHERE app_id = 'naas_abi_marketplace.applications.x:x_proxy';
-- A workspace's catalog seed (JSON, its "apps" list) names apps the same way.
UPDATE workspaces
SET catalog_seed = REPLACE(
    catalog_seed,
    '"naas_abi_marketplace.applications.x:x_proxy"',
    '"remote/applications.x:x_proxy"'
)
WHERE catalog_seed LIKE '%"naas_abi_marketplace.applications.x:x_proxy"%';
