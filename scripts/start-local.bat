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
  echo Run: py -m venv .venv ^&^& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)
where npm.cmd >nul 2>nul || (
  echo ERROR: npm was not found on PATH.
  exit /b 1
)
if not exist "%ROOT%\apps\chat-web\node_modules" (
  echo ERROR: Chat Web dependencies are missing. Run npm install in apps\chat-web first.
  exit /b 1
)
if not exist "%ROOT%\apps\admin-web\node_modules" (
  echo ERROR: Admin Web dependencies are missing. Run npm install in apps\admin-web first.
  exit /b 1
)

echo Starting Hospital Assistant local demo in three terminals...
start "HospitalAssistant API" /D "%ROOT%" cmd /k ""%PYTHON%" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload"
start "HospitalAssistant Chat Web" /D "%ROOT%\apps\chat-web" cmd /k "npm.cmd run dev -- --host 127.0.0.1"
start "HospitalAssistant Admin Web" /D "%ROOT%\apps\admin-web" cmd /k "npm.cmd run dev -- --host 127.0.0.1 --port 5174"

echo API docs:  http://127.0.0.1:8000/api/v1/docs
echo Foundation: http://127.0.0.1:8000/v1/foundation/specialties
echo Chat Web:  http://127.0.0.1:5173
echo Admin Web: http://127.0.0.1:5174
echo Run scripts\smoke-local.bat after the services are ready.
exit /b 0
