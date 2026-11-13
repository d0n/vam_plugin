#!/usr/bin/env bash
# Sandbox scan + C# 6 compile check of both plugins (see tools/check_plugin.py).
set -euo pipefail
exec python3 "$(dirname "$0")/check_plugin.py" "$@"
