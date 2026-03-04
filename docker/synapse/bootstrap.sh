#!/bin/sh
set -e

if [ ! -f /data/homeserver.yaml ]; then
  /start.py generate
  cat >> /data/homeserver.yaml <<'EOF'

# Local development overrides
enable_registration: true
enable_registration_without_verification: true
cors_allowed_origins:
  - "http://localhost:8080"
  - "http://127.0.0.1:8080"
  - "http://localhost"
  - "http://127.0.0.1"
EOF
fi

exec /start.py
