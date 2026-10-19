@echo off
setlocal
for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
uv run --project "%PROJECT_ROOT%" uvicorn ink_ai_discord.main:app --app-dir "%PROJECT_ROOT%\src" --host 127.0.0.1 --port 8080
