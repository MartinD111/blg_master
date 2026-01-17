@echo off
echo Checking for Python...
where python
if %ERRORLEVEL% NEQ 0 (
    echo Python not found in PATH. Checking common locations...
    if exist "C:\Python39\python.exe" (
        set PYTHON="C:\Python39\python.exe"
    ) else if exist "C:\Python310\python.exe" (
        set PYTHON="C:\Python310\python.exe"
    ) else if exist "C:\Python311\python.exe" (
        set PYTHON="C:\Python311\python.exe"
    ) else if exist "C:\Python312\python.exe" (
        set PYTHON="C:\Python312\python.exe"
    ) else (
        echo Could not find Python. Please install Python or add it to your PATH.
        pause
        exit /b 1
    )
) else (
    set PYTHON=python
)

echo Found Python: %PYTHON%
echo Installing requirements...
%PYTHON% -m pip install -r requirements.txt

echo Starting Application...
%PYTHON% app.py
pause
