#!/bin/bash
# Antikythera AI Engine Configuration Helper
# This script helps you configure environment variables for AI providers

CONFIG_FILE="$HOME/.antikythera/ai_config.json"
VAULT_DIR="$HOME/.antikythera/vault"

echo "=============================================="
echo "Antikythera AI Engine Configuration Guide"
echo "=============================================="
echo ""
echo "Configuration File Location:"
echo "   $CONFIG_FILE"
echo ""
echo "Vault Directory (for encrypted secrets):"
echo "   $VAULT_DIR"
echo ""
echo "=============================================="
echo "Environment Variables Reference"
echo "=============================================="
echo ""

# Check if config exists
if [ -f "$CONFIG_FILE" ]; then
    echo "Configuration file exists: $CONFIG_FILE"
    echo "Configured Models:"
    cat "$CONFIG_FILE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('models', {})
    for model_id, config in models.items():
        api_key_env = config.get('api_key_env', 'None (no key required)')
        config_note = config.get('config_note', '')
        print(f'  - {model_id}')
        print(f'    API Key Env Var: {api_key_env}')
        if config_note:
            print(f'    Note: {config_note}')
        print()
except Exception as e:
    print(f'Error parsing config: {e}')
"
else
    echo "No configuration file found yet"
    echo "It will be created automatically when you configure your first model"
    echo ""
fi

echo "=============================================="
echo "How to Set Environment Variables"
echo "=============================================="
echo ""
echo "Option 1: Shell Profile (Recommended for Development)"
echo "----------------------------------------------------"
echo "Add to your ~/.zshrc, ~/.bashrc, or ~/.profile:"
echo ""
echo "  # NVIDIA NIM"
echo '  export NVIDIA_API_KEY="your-key-here"'
echo ""
echo "  # Google Gemma"  
echo '  export GOOGLE_API_KEY="your-key-here"'
echo ""
echo "  # IBM Bob"
echo '  export IBM_BOB_API_KEY="your-key-here"'
echo ""
echo "  # Ollama (optional, only if your instance requires auth)"
echo '  export OLLAMA_API_KEY="your-key-here"'
echo ""
echo "Then reload your shell:"
echo "  source ~/.zshrc  # or ~/.bashrc"
echo ""

echo "Option 2: Project .env File"
echo "----------------------------------------------------"
echo "Create a .env file in your project root:"
echo ""
echo "  NVIDIA_API_KEY=your-n...HERE"
echo "  GOOGLE_API_KEY=your-g...HERE"
echo "  IBM_BOB_API_KEY=your-i...HERE"
echo ""
echo "Note: The backend needs to load this file. Add to your startup script:"
echo "  export \$(grep -v '^#' .env | xargs)"
echo ""

echo "Option 3: Custom Environment Variable Names"
echo "----------------------------------------------------"
echo "You can customize the environment variable name for each model"
echo "via the AI Engine Settings UI or API:"
echo ""
echo "  POST /api/ai-engine/update-model"
echo '  {'
echo '    "model_id": "nvidia-nemotron",'
echo '    "api_key_env": "MY_CUSTOM_NVIDIA_KEY"'
echo '  }'
echo ""

echo "=============================================="
echo "Current Environment Variable Status"
echo "=============================================="
echo ""

check_var() {
    local var_name=$1
    local var_value=${!var_name}
    if [ -n "$var_value" ]; then
        echo "OK: $var_name is set"
    else
        echo "MISSING: $var_name is NOT set"
    fi
}

check_var "NVIDIA_API_KEY"
check_var "GOOGLE_API_KEY"
check_var "IBM_BOB_API_KEY"
check_var "OLLAMA_API_KEY"

echo ""
echo "=============================================="
echo "Quick Commands"
echo "=============================================="
echo ""
echo "Check if Ollama is running:"
echo "  curl http://localhost:11434/api/tags"
echo ""
echo "Test NVIDIA NIM connection:"
echo "  curl -H 'Authorization: Bearer \$NVIDIA_API_KEY' https://integrate.api.nvidia.com/v1/models"
echo ""
echo "View current configuration:"
echo "  curl http://localhost:8006/api/ai-engine/config"
echo ""
echo "=============================================="
echo ""
echo "Tip: After setting environment variables, restart the Antikythera backend!"
echo ""