@echo off
setlocal EnableDelayedExpansion

REM Change to script directory
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Test system Python first for tkinter support
echo Testing system Python for tkinter support...
python -c "import tkinter; root = tkinter.Tk(); root.destroy(); print('System Python tkinter: OK')" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ SYSTEM PYTHON TKINTER ERROR!
    echo Your system Python installation is missing tkinter support.
    echo.
    echo SOLUTION: Please reinstall Python from python.org with tkinter support.
    echo Make sure to check "tcl/tk and IDLE" during installation.
    echo.
    pause
    goto :eof
)

echo ✅ System Python has working tkinter support.

REM Create venv with system Python (force system Python to avoid version conflicts)
if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment with system Python...
  python -m venv venv
  if %ERRORLEVEL% NEQ 0 (
    echo ❌ Failed to create virtual environment!
    pause
    goto :eof
  )
) else (
  REM Check if existing venv has tkinter issues
  echo Testing existing virtual environment...
  venv\Scripts\python.exe -c "import tkinter; root = tkinter.Tk(); root.destroy(); print('VEnv tkinter: OK')" >nul 2>&1
  if %ERRORLEVEL% NEQ 0 (
    echo ❌ Existing virtual environment has tkinter issues.
    echo This often happens with Python 3.13 or version conflicts.
    echo Recreating virtual environment with system Python...
    
    REM Remove problematic venv
    rmdir /s /q "venv"
    echo ✅ Removed problematic virtual environment.
    
    REM Create new venv with system Python
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
      echo ❌ Failed to recreate virtual environment!
      pause
      goto :eof
    )
    echo ✅ Recreated virtual environment with system Python.
  ) else (
    echo ✅ Existing virtual environment works fine.
  )
)

echo Upgrading pip and installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip >nul
venv\Scripts\python.exe -m pip install -r requirements.txt >nul

REM Final test to ensure everything works
echo Testing virtual environment tkinter...
venv\Scripts\python.exe -c "import tkinter; root = tkinter.Tk(); root.destroy(); print('Final tkinter test: OK')" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Virtual environment still has tkinter issues.
    echo Falling back to system Python...
    echo.
    echo Installing requests for system Python...
    python -m pip install requests >nul 2>&1
    
    echo Launching with system Python...
    python app.py %*
    goto :eof
)

echo ✅ All tests passed - launching GUI...

REM Pass along any arguments (drag-and-drop path appears as %1)
echo Launching Gitea Management Application...
echo.
echo The GUI window should appear shortly.
echo This terminal window will remain open for logging output.
echo You can minimize this window once the GUI appears.
echo.

REM Launch GUI without console window using pythonw and exit immediately
if exist "venv\Scripts\pythonw.exe" (
    start "" venv\Scripts\pythonw.exe app.py %*
) else (
    start "" venv\Scripts\python.exe app.py %*
)
exit

endlocal