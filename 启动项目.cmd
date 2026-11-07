@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1
where uv >nul 2>nul
if not errorlevel 1 goto run
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    goto run
)
echo uv was not found. Install it from https://docs.astral.sh/uv/getting-started/installation/
echo Then close this window and start again.
pause
popd
exit /b 1
:run
uv run --locked python app.py --open %*
set "launch_result=%ERRORLEVEL%"
if not "%launch_result%"=="0" pause
popd
exit /b %launch_result%
