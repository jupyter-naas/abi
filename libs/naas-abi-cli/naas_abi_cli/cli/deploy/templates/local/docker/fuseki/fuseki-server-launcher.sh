#!/bin/bash
# Starts Fuseki 5.6 against a FUSEKI_BASE that may have been created by the
# older Fuseki 5.1 image (an existing fuseki_data volume was).
#
# Shiro, as configured by a 5.1-era shiro.ini, stores the logged-in subject in
# an HTTP session. Fuseki 5.6 runs without a servlet session manager, so every
# authenticated request (SPARQL update, /data, /$/compact, /$/backup) fails
# with HTTP 500 "IllegalStateException: No SessionManager". HTTP Basic auth
# needs no session, so turn session storage off in shiro.ini, once and in
# place, keeping the users and URL rules as they are.
set -euo pipefail

shiro="${FUSEKI_BASE:-/fuseki}/shiro.ini"
setting='securityManager.subjectDAO.sessionStorageEvaluator.sessionStorageEnabled = false'

if [ -f "$shiro" ] && ! grep -q '^securityManager\.subjectDAO\.sessionStorageEvaluator\.sessionStorageEnabled' "$shiro"; then
  if ! grep -q '^\[main\]' "$shiro"; then
    echo "fuseki-server: $shiro has no [main] section; cannot add the Shiro session setting Fuseki 5.6 needs" >&2
    exit 1
  fi
  tmp="$shiro.tmp.$$"
  sed "/^\[main\]/a # Added for Fuseki 5.6: HTTP Basic needs no session (see fuseki-server launcher)\n$setting" "$shiro" > "$tmp"
  mv "$tmp" "$shiro"
  echo "fuseki-server: added Shiro session setting to $shiro"
fi

exec /jena-fuseki/fuseki-server.dist "$@"
