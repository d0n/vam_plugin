#!/usr/bin/env bash
# Strict sandbox scan + single-plugin check + C# 6 compile check of the AIBody plugin (see tools/check_plugin.py).
set -euo pipefail
exec python3 "$(dirname "$0")/check_plugin.py" "$@"
