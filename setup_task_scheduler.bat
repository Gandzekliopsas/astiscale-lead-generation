@echo off
:: AstiScale Lead Generation — Windows Task Scheduler Setup
:: Run this file as Administrator to schedule daily lead generation at 08:00

set TASK_NAME=AstiScale_LeadGeneration
set PYTHON_PATH=python
set SCRIPT_PATH=%~dp0scheduler.py

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   AstiScale Lead Generation — Task Setup     ║
echo  ╚══════════════════════════════════════════════╝
echo.
echo Creating Windows Task Scheduler task...
echo Task: %TASK_NAME%
echo Script: %SCRIPT_PATH%
echo Schedule: Every day at 08:00
echo.

:: Delete old task if exists
schtasks /delete /tn "%TASK_NAME%" /f 2>nul

:: Create new task — runs daily at 08:00
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" ^
  /sc daily ^
  /st 08:00 ^
  /ru "%USERNAME%" ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo  SUCCESS: Task created!
    echo  Lead generation will run every day at 08:00.
    echo  Results saved in: %~dp0output\leads\
    echo.
) else (
    echo.
    echo  ERROR: Failed to create task.
    echo  Try running this file as Administrator.
    echo.
)

pause
