@echo off
set /p config_name="Enter the config file name: "
set /p start_sep="Enter the start separator: "
set /p end_sep="Enter the end separator: "
set /p skip_first_line="Enter skip_first_line (True/False): "
set /p model_name="Enter the model name: "

if "%model_name%"=="" (
    echo Error: Model name is required.
    exit /b
)

(
    echo # The temperature parameter controls the randomness of the model's output. Lower values make the output more deterministic.
    echo temperature = 0.1
    echo # The maximum number of new tokens that the model can generate.
    echo max_tokens = 1024
    echo # The start separator for the generated code.
    echo start_sep = %start_sep%
    echo # The end separator for the generated code.
    echo end_sep = %end_sep%
    echo # If True, the first line of the generated text will be skipped.
    echo skip_first_line = %skip_first_line%
    echo # The model used for generating the code.
    echo HF_MODEL = '%model_name%'
) > configs\%config_name%.config
