@echo off
set /p config_name="Enter the config file name: "
set /p start_sep="Enter the start separator: "
set /p end_sep="Enter the end separator: "
set /p model_name="Enter the model name: "

if "%model_name%"=="" (
    echo Error: Model name is required.
    exit /b
)

(
    echo {
    echo     "temperature": 0.1,
    echo     "max_tokens": 1024,
    echo     "start_sep": "%start_sep%",
    echo     "end_sep": "%end_sep%",
    echo     "model": "%model_name%"
    echo }
) > configs\%config_name%.json
echo Configuration saved to configs\%config_name%.json
