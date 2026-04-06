#!/bin/bash

read -p "Enter the config file name: " config_name
read -p "Enter the start separator: " start_sep
read -p "Enter the end separator: " end_sep
read -p "Enter the model name: " model_name

if [ -z "$model_name" ]; then
    echo "Error: Model name is required."
    exit 1
fi

cat > configs/"$config_name".json << EOF
{
    "temperature": 0.1,
    "max_tokens": 1024,
    "start_sep": "$start_sep",
    "end_sep": "$end_sep",
    "model": "$model_name"
}
EOF
echo "Configuration saved to configs/$config_name.json"
