$conns = netstat -ano | findstr ":8000" | findstr "LISTENING"
foreach ($line in $conns) {
    $procId = ($line -split '\s+')[-1]
    taskkill /PID $procId /F 2>$null
}
uvicorn api.main:app --host 0.0.0.0 --port 8000