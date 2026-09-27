#!/bin/sh
set -e

if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
    python -m app.seed
fi

exec "$@"
