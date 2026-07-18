@echo off
setlocal EnableExtensions

echo Stopping local services on ports 8000, 5173 and 5174...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$connections = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue); $stopped = @{}; foreach ($connection in $connections) { if ($connection.LocalPort -in @(8000,5173,5174) -and -not $stopped.ContainsKey($connection.OwningProcess)) { Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue; $stopped[$connection.OwningProcess] = $true } }"
echo Local demo stop request completed.
exit /b 0
