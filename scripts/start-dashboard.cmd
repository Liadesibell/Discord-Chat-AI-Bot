@echo off
setlocal
for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
npm.cmd --prefix "%PROJECT_ROOT%\frontend" run dev
