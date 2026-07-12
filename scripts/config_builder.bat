@echo off
setlocal enabledelayedexpansion
rem Append a new [models.<name>] entry to configs\models.toml.
rem The single-file TOML registry replaced the old configs\<name>.json layout.

set /p model_key="Enter the model key (table name, e.g. my-custom-model): "
set /p model_name="Enter the litellm model id (e.g. groq/llama-3.1-8b-instant): "
set /p provider="Enter the provider (blank to auto-detect from model id): "
set /p api_base="Enter the api_base (blank if not a custom OpenAI-compatible endpoint): "

if "%model_key%"=="" (
    echo Error: model key is required.
    exit /b 1
)
if "%model_name%"=="" (
    echo Error: model id is required.
    exit /b 1
)

set REGISTRY=configs\models.toml
if not exist "%REGISTRY%" (
    echo Error: %REGISTRY% not found. Run this from the repo root.
    exit /b 1
)

(
    echo.
    echo [models."%model_key%"]
    echo model = "%model_name%"
    if not "%provider%"=="" echo provider = "%provider%"
    if not "%api_base%"=="" echo api_base = "%api_base%"
    echo temperature = 0.1
    echo max_tokens = 4096
    echo tier = "paid"
) >> "%REGISTRY%"

echo Appended [models."%model_key%"] to %REGISTRY%
