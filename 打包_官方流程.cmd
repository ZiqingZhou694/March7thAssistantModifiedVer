@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 goto cd_failed

set "PY=C:\Users\jing7\Documents\Codex\venv3145\Scripts\python.exe"
set "OFFICIAL_FULL=C:\Users\jing7\Documents\Codex\Applications\March7thAssistant\March7thAssistant_full"

if not exist "%PY%" goto python_missing

echo [1/6] Running Silver Wolf tests...
"%PY%" -m pytest -q tests\test_tasks\test_currency_wars_bond.py
if errorlevel 1 goto failed

echo [2/6] Building Assistant and m7a...
"%PY%" -m PyInstaller --workpath ".\build" --distpath ".\dist" ".\March7th Assistant.spec" -y
if errorlevel 1 goto failed

echo [3/6] Building Launcher...
"%PY%" -m PyInstaller --workpath ".\build" --distpath ".\dist" ".\March7th Launcher.spec" -y
if errorlevel 1 goto failed

echo [4/6] Building Updater...
"%PY%" -m PyInstaller --workpath ".\build" --distpath ".\dist\March7thAssistant" ".\March7th Updater.spec" -y
if errorlevel 1 goto failed

echo [5/6] Merging official release layout...
xcopy ".\dist\March7th Assistant\*" ".\dist\March7thAssistant\" /E /I /Y >nul
if errorlevel 1 goto failed
xcopy ".\dist\March7th Launcher\*" ".\dist\March7thAssistant\" /E /I /Y >nul
if errorlevel 1 goto failed
xcopy ".\assets\*" ".\dist\March7thAssistant\assets\" /E /I /Y >nul
if errorlevel 1 goto failed
copy /Y ".\README.md" ".\dist\March7thAssistant\README.md" >nul
if errorlevel 1 goto failed
copy /Y ".\assets\agent\AGENTS.md" ".\dist\March7thAssistant\AGENTS.md" >nul
if errorlevel 1 goto failed
if exist "%OFFICIAL_FULL%\3rdparty" xcopy "%OFFICIAL_FULL%\3rdparty\*" ".\dist\March7thAssistant\3rdparty\" /E /I /Y >nul

rem PyInstaller may collect an incompatible ICU 78 alias from PATH.
rem Qt6Core loads it first and March7th Launcher exits before creating logs.
if exist ".\dist\March7thAssistant\libraries\icuuc.dll" del /F /Q ".\dist\March7thAssistant\libraries\icuuc.dll"
if exist ".\dist\March7thAssistant\libraries\icudt78.dll" del /F /Q ".\dist\March7thAssistant\libraries\icudt78.dll"

echo [6/6] Removing intermediate build folders...
if exist ".\dist\March7th Assistant" rmdir /S /Q ".\dist\March7th Assistant"
if exist ".\dist\March7th Launcher" rmdir /S /Q ".\dist\March7th Launcher"

echo.
echo BUILD COMPLETE:
echo %CD%\dist\March7thAssistant
pause
exit /b 0

:python_missing
echo Python 3.14.5 build environment was not found:
echo %PY%
pause
exit /b 1

:cd_failed
echo Failed to enter the source directory.
pause
exit /b 1

:failed
echo.
echo BUILD FAILED. Exit code: %ERRORLEVEL%
pause
exit /b %ERRORLEVEL%
