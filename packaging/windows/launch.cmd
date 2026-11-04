@echo off
setlocal
"%~dp0runtime\python.exe" -I "%~dp0launcher.py" %*
exit /b %ERRORLEVEL%
