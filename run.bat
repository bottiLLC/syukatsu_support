@echo off
cd /d "%~dp0"

echo ===================================================
echo   App Launcher (Windows)
echo ===================================================
echo.

:: 1. Auto-detect and fix 'uv' command path
where uv >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    if exist "%LOCALAPPDATA%\bin\uv.exe" set "PATH=%LOCALAPPDATA%\bin;%PATH%"
)

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Package manager 'uv' not found.
    echo Please install uv by running the following command in PowerShell:
    echo powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    pause
    exit /b 1
)

:: 2. Auto-detect Python entry point
set "ENTRY_POINT="
if exist "app.py" set "ENTRY_POINT=app.py"
if not defined ENTRY_POINT (if exist "main.py" set "ENTRY_POINT=main.py")
if not defined ENTRY_POINT (if exist "src\app.py" set "ENTRY_POINT=src\app.py")

if not defined ENTRY_POINT (
    echo [ERROR] Python entry point (app.py / main.py / src\app.py) not found.
    echo.
    pause
    exit /b 1
)

echo [INFO] Entry point found: %ENTRY_POINT%

:: 3. Auto-create .venv and sync package dependencies
if not exist ".venv" (
    echo [INFO] Virtual environment (.venv) not found. Creating virtual environment...
    uv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment (.venv).
        echo.
        pause
        exit /b %errorlevel%
    )
    echo [INFO] Virtual environment created successfully.
)

if exist "pyproject.toml" (
    echo [INFO] Verifying and syncing package dependencies (uv sync)...
    uv sync
    if %errorlevel% neq 0 (
        echo [ERROR] Dependency sync (uv sync) failed.
        echo Please check your pyproject.toml configuration.
        echo.
        pause
        exit /b %errorlevel%
    )
)

:: 4. Launch App
echo.
echo [INFO] Launching App...
echo.

uv run python "%ENTRY_POINT%"

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Application stopped or encountered an error.
)

echo.
pause
