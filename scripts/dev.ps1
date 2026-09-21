$ErrorActionPreference = "Stop"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\backend'; uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --workers 1"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\..\frontend'; npm run dev"
