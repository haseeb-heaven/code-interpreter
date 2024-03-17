#!/bin/bash

read -p "Enter the config file name: " config_name
read -p "Enter the start separator: " start_sep
read -p "Enter the end separator: " end_sep
read -p "Enter skip_first_line (True/False): " skip_first_line
read -p "Enter the model name: " model_name

if [ -z "$model_name" ]; then
    echo "Error: Model name is required."
    exit 1
fi

cat > configs/"$config_name".config << EOF

# The temperature parameter controls the randomness of the model's output. Lower values make the output more deterministic.
temperature = 0.1

# The maximum number of new tokens that the model can generate.
max_tokens = 1024

# The start separator for the generated code.
start_sep = $start_sep

# The end separator for the generated code.
end_sep = $end_sep

# If True, the first line of the generated text will be skipped.
skip_first_line = $skip_first_line

# The model used for generating the code.
HF_MODEL = $model_name
EOF
