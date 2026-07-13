@echo off
setlocal

rem Keep this launcher ASCII-only. Some versions of cmd.exe misparse UTF-8 batch files.
set "SCRIPT=%~dp0deploy.ps1"
set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%SCRIPT%" (
    echo [ERROR] deploy.ps1 was not found next to deploy.bat.
    echo Please extract the complete patch package before running it.
    pause
    exit /b 10
)

if not exist "%PS_EXE%" (
    echo [ERROR] Windows PowerShell was not found.
    pause
    exit /b 11
)

"%PS_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
set "RESULT=%ERRORLEVEL%"

echo.
pause
exit /b %RESULT%
