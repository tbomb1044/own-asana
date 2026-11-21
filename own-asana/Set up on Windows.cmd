@echo off
setlocal EnableExtensions
title own-asana - set up
cd /d "%~dp0"

call :findpython
if defined PYEXE goto run

echo.
echo own-asana needs one free helper program called Python, and it is not on
echo this computer yet. Windows can fetch it from python.org with its own
echo installer (winget). It installs for your Windows login only and does not
echo need an administrator.
echo.
choice /C YN /M "Install Python now"
if errorlevel 2 goto nopython
where winget >nul 2>&1
if errorlevel 1 goto nowinget
winget install --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :findpython
if defined PYEXE goto run
echo.
echo Python was installed but this window cannot see it yet.
echo Close this window, then double-click this file again.
goto end

:run
"%PYEXE%" %PYARG% -I -B "program\run_setup.py"
goto end

:nopython
echo.
echo Stopped. Nothing was changed. own-asana cannot run without Python.
goto end

:nowinget
echo.
echo This computer does not have Windows' installer (winget), so Python could
echo not be fetched. Nothing was changed. Ask for help with installing Python.
goto end

:end
echo.
pause
exit /b 0

:findpython
set "PYEXE="
set "PYARG="
py -3 -I "program\check_python.py" >nul 2>&1
if not errorlevel 1 set "PYEXE=py"
if defined PYEXE set "PYARG=-3"
if defined PYEXE exit /b 0
python -I "program\check_python.py" >nul 2>&1
if not errorlevel 1 set "PYEXE=python"
if defined PYEXE exit /b 0
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
exit /b 0
