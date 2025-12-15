@echo off

REM -----------------------------------------------------------
REM EXPECTED ARGUMENTS:
REM   %1 = PYTHON_VERSION_ENV
REM   %2 = DAI_VERSION
REM   %3 = DAI_NODES_VERSION
REM   %4 = PLATFORM
REM   %5 = STRICT_MODE
REM   %6 = ROOT_DIR
REM   %7 = LOG_LEVEL
REM -----------------------------------------------------------

if "%4"=="" (
    echo Usage: run_tests.cmd PYTHON_VERSION PLATFORM STRICT_MODE ROOT_DIR LOG_LEVEL DAI_VERSION DAI_NODES_VERSION
    exit /b 1
)

set PYTHON_VERSION_ENV=%1
set PLATFORM=%2
set STRICT_MODE=%3
set ROOT_DIR=%4
set LOG_LEVEL=%5
set DAI_VERSION=%6
set DAI_NODES_VERSION=%7

echo ==========================================
echo Running tests with:
echo   PYTHON_VERSION_ENV = %PYTHON_VERSION_ENV%
echo   PLATFORM            = %PLATFORM%
echo   STRICT_MODE         = %STRICT_MODE%
echo   ROOT_DIR            = %ROOT_DIR%
echo   LOG_LEVEL           = %LOG_LEVEL%
echo   DAI_VERSION         = %DAI_VERSION%
echo   DAI_NODES_VERSION   = %DAI_NODES_VERSION%
echo ==========================================

echo Creating virtual environment...
python -m venv .venv

if errorlevel 1 (
    echo Failed to create virtual environment
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat
adb root
pip install -r tests/requirements.txt

echo Running tests...

pytest -v -r a --log-cli-level=%LOG_LEVEL% --log-file=out.log --color=yes ^
    --depthai-version=%DAI_VERSION% ^
    --depthai-nodes-version=%DAI_NODES_VERSION% ^
    --environment-variables=DEPTHAI_PLATFORM=%PLATFORM% ^
    --platform=%PLATFORM% ^
    --python-version=%PYTHON_VERSION_ENV% ^
    --strict-mode=%STRICT_MODE% ^
    --root-dir %ROOT_DIR% ^
    -q "%~dp0test_examples_peripheral.py"