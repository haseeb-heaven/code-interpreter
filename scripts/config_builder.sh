#!/bin/bash
# Append a new [models.<name>] entry to configs/models.toml.
# The single-file TOML registry replaced the old configs/<name>.json layout.

read -p "Enter the model key (table name, e.g. my-custom-model): " model_key
read -p "Enter the litellm model id (e.g. groq/llama-3.1-8b-instant): " model_name
read -p "Enter the provider (blank to auto-detect from model id): " provider
read -p "Enter the api_base (blank if not a custom OpenAI-compatible endpoint): " api_base

if [ -z "$model_key" ] || [ -z "$model_name" ]; then
    echo "Error: model key and model id are required."
    exit 1
fi

REGISTRY="configs/models.toml"
if [ ! -f "$REGISTRY" ]; then
    echo "Error: $REGISTRY not found. Run this from the repo root."
    exit 1
fi

{
    echo ""
    echo "[models.\"$model_key\"]"
    echo "model = \"$model_name\""
    if [ -n "$provider" ]; then
        echo "provider = \"$provider\""
    fi
    if [ -n "$api_base" ]; then
        echo "api_base = \"$api_base\""
    fi
    echo "temperature = 0.1"
    echo "max_tokens = 4096"
    echo "tier = \"paid\""
} >> "$REGISTRY"

echo "Appended [models.\"$model_key\"] to $REGISTRY"
