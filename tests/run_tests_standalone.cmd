@echo off

REM ==============================================================================
REM EXPECTED ARGUMENTS:
REM   %1 = PYTHON_VERSION_ENV      (e.g. 3.12)
REM   %2 = DAI_VERSION             (e.g. 3.2.0)
REM   %3 = DAI_NODES_VERSION       (e.g. 0.3.6)
REM   %4 = PLATFORM                (e.g. rvc4)
REM   %5 = DEVICE_PASSWORD         ("" allowed)
REM   %6 = LOCAL_STATIC_REGISTRY   ("" allowed)
REM   %7 = ROOT_DIR                (e.g. .)
REM   %8 = LOG_LEVEL               (e.g. INFO)
REM ==============================================================================

if "%4"=="" (
    echo Usage:
    echo   run_tests_standalone.cmd PYTHON_VERSION_ENV DAI_VERSION DAI_NODES_VERSION PLATFORM DEVICE_PASSWORD LOCAL_STATIC_REGISTRY ROOT_DIR LOG_LEVEL
    exit /b 1
)

set PYTHON_VERSION_ENV=%1
set DAI_VERSION=%2
set DAI_NODES_VERSION=%3
set PLATFORM=%4
set DEVICE_PASSWORD=%5
set LOCAL_STATIC_REGISTRY=%6
set ROOT_DIR=%7
set LOG_LEVEL=%8

echo ==========================================
echo Running standalone tests with:
echo   PYTHON_VERSION_ENV = %PYTHON_VERSION_ENV%
echo   DAI_VERSION         = %DAI_VERSION%
echo   DAI_NODES_VERSION   = %DAI_NODES_VERSION%
echo   PLATFORM            = %PLATFORM%
echo   DEVICE_PASSWORD     = %DEVICE_PASSWORD%
echo   LOCAL_STATIC_REG    = %LOCAL_STATIC_REGISTRY%
echo   ROOT_DIR            = %ROOT_DIR%
echo   LOG_LEVEL           = %LOG_LEVEL%
echo ==========================================

REM ==============================================================================
REM oakctl self-update (best-effort)
REM ==============================================================================

echo Updating oakctl if available...
where oakctl >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%v in ('oakctl version') do set "OAK_VER=%%v"
    if defined OAK_VER (
        oakctl self-update -v %OAK_VER%
    ) else (
        echo Could not determine oakctl version, skipping self-update.
    )
) else (
    echo oakctl not found, skipping self-update.
)

echo Creating virtual environment...
python -m venv .venv

if errorlevel 1 (
    echo Failed to create virtual environment
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat

pip install -r tests/requirements.txt

adb root 

REM ==============================================================================
REM Run tests
REM ==============================================================================

echo Running tests...

pytest -v -r a --log-cli-level=%LOG_LEVEL% --log-file=out.log --color=yes ^
    --depthai-version=%DAI_VERSION% ^
    --depthai-nodes-version=%DAI_NODES_VERSION% ^
    --environment-variables=DEPTHAI_PLATFORM=%PLATFORM% ^
    --platform=%PLATFORM% ^
    --python-version=%PYTHON_VERSION_ENV% ^
    --device-password=%DEVICE_PASSWORD% ^
    --local-static-registry=%LOCAL_STATIC_REGISTRY% ^
    --root-dir "%ROOT_DIR%" ^
    -q "%~dp0test_examples_standalone.py"