#!/bin/bash

# Restart = stop + start. start_antikythera.sh owns env loading (user ~/.antikythera/.env,
# then project .env, then ~/.antikythera/.ai_env) and already runs stop_antikythera.sh as its
# first step, so this wrapper delegates to it instead of duplicating that logic (O9).
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Restarting Antikythera (stop, then start)..."
exec "$ROOT_DIR/start_antikythera.sh"
