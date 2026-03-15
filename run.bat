@echo off
echo Starting SF3:3rd Strike Character Editor...
echo.

:: Check if uv is available
where uv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] uv not found. Installing uv...
    pip install uv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install uv. Please install manually:
        echo   pip install uv
        echo   or: winget install astral-sh.uv
        pause
        exit /b 1
    )
)

echo [INFO] Syncing dependencies with uv...
uv sync
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to sync dependencies.
    pause
    exit /b 1
)

echo [INFO] Starting Character Editor...
uv run python run_character_editor.py

pause
