$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\backend"
try {
  uvicorn app.main:app --host 127.0.0.1 --port 8765 --workers 1
}
finally {
  Pop-Location
}
