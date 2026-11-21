@echo off
rem AIBody companion app starter (version 40). Double-click this file; it lives in the repository's "companion" folder.
rem The VaM folder (the one with VaM.exe) is found in this order:
rem   1. the first argument, e.g. start_companion.bat "D:\VaM"
rem   2. the file vam_root.txt next to this file (written by step 4)
rem   3. a parent folder of this file that has AddonPackages and Saves (when the repository sits inside the VaM folder)
rem   4. asked once in this window and saved to vam_root.txt
setlocal
cd /d "%~dp0"
set "VAMROOT=%~1"
if defined VAMROOT goto found
if exist "%~dp0vam_root.txt" set /p VAMROOT=<"%~dp0vam_root.txt"
if defined VAMROOT goto found
set "DIR=%~dp0."
:up
for %%P in ("%DIR%") do set "DIR=%%~fP"
if exist "%DIR%\AddonPackages\" if exist "%DIR%\Saves\" set "VAMROOT=%DIR%"
if defined VAMROOT goto found
for %%P in ("%DIR%\..") do set "PARENT=%%~fP"
if /i "%PARENT%"=="%DIR%" goto ask
set "DIR=%PARENT%"
goto up
:ask
echo AIBody: the VaM folder was not found next to this file.
set /p VAMROOT=Enter your VaM folder (the folder with VaM.exe, e.g. D:\VaM): 
if not defined VAMROOT goto fail
> "%~dp0vam_root.txt" echo %VAMROOT%
:found
set "VAMROOT=%VAMROOT:"=%"
if not exist "%VAMROOT%\" (
  echo AIBody: the folder "%VAMROOT%" does not exist. Fix or delete vam_root.txt and start again.
  goto fail
)
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
echo AIBody companion app: VaM folder "%VAMROOT%". Keep this window open while VaM runs.
%PY% -m aibody_companion --vam-root "%VAMROOT%"
if errorlevel 1 goto fail
goto end
:fail
echo.
echo AIBody: the companion app did not start or stopped with an error (see the lines above).
echo Python 3.10 or newer is needed (python.org); for the microphone: python -m pip install -r requirements.txt
pause
:end
endlocal
