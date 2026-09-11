#!/bin/sh
set -eu
cd /app
python scripts/validate.py
python scripts/index.py --out "${TOPONYM_DB:-/app/knowledge/registry.db}"
exec python scripts/serve.py
