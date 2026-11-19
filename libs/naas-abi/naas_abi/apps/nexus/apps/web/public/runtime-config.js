// Overwritten at container start (docker-entrypoint.sh). Elsewhere the inline
// config of app/layout.tsx, from the server's environment, stands: `abi dev up`
// and the Docker stack set NEXUS_API_URL there.
window.__NEXUS_RUNTIME_CONFIG__ = window.__NEXUS_RUNTIME_CONFIG__ || {};
