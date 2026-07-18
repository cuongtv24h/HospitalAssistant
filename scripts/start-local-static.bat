@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if not exist "%ROOT%\.env" (
  echo ERROR: .env is missing. Copy .env.example and configure local values first.
  exit /b 1
)
if not exist "%PYTHON%" (
  echo ERROR: Local virtual environment is missing.
  exit /b 1
)
if not exist "%ROOT%\apps\chat-web\dist\index.html" (
  echo ERROR: Chat Web build is missing. Run npm run build in apps\chat-web first.
  exit /b 1
)
if not exist "%ROOT%\apps\admin-web\dist\index.html" (
  echo ERROR: Admin Web build is missing. Run npm run build in apps\admin-web first.
  exit /b 1
)

echo Starting static demo at http://127.0.0.1:8000 ...
start "HospitalAssistant API Static" /D "%ROOT%" cmd /k ""%PYTHON%" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000"
echo Chat:  http://127.0.0.1:8000/
echo Admin: http://127.0.0.1:8000/admin/
echo API:   http://127.0.0.1:8000/api/v1/docs
echo Run scripts\smoke-local-static.bat after the server is ready.
exit /b 0
