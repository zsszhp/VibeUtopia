# VibeUtopia Windows 一键启动脚本（开发环境版）
# 使用方法: powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# 停止服务: Ctrl+C 或关闭此窗口

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  VibeUtopia 一键启动 (Windows)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ---- 检查 Docker ----
$hasDocker = $false
try {
    $null = docker compose version 2>&1
    $hasDocker = $true
    Write-Host "  OK Docker Compose 可用" -ForegroundColor Green
} catch {
    Write-Host "  ! Docker Compose 不可用，将使用简化启动模式" -ForegroundColor DarkYellow
}
Write-Host ""

# ---- 检查 .env ----
Write-Host "[1/4] 检查环境配置..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  ! .env 文件不存在，从 .env.example 复制..." -ForegroundColor DarkYellow
    if (Test-Path ".env.example") {
        Copy-Item .env.example .env
        Write-Host "  OK .env 已创建，请填入 API Key 后重新运行" -ForegroundColor Green
    }
    Write-Host "  ! 请编辑 .env 填入 LLM API Key: notepad .env" -ForegroundColor DarkYellow
    Write-Host ""
}
Write-Host "  OK 环境配置检查通过" -ForegroundColor Green
Write-Host ""

# ---- 启动后端 ----
Write-Host "[2/4] 启动后端服务..." -ForegroundColor Yellow

$pythonCmd = $null
try { $null = python --version 2>&1; $pythonCmd = "python" } catch {
    try { $null = python3 --version 2>&1; $pythonCmd = "python3" } catch {
        Write-Host "  X Python 未安装" -ForegroundColor Red
        exit 1
    }
}

# 检查是否在虚拟环境中
$inVenv = $env:VIRTUAL_ENV -ne ""
if (-not $inVenv -and (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "  激活虚拟环境..." -ForegroundColor Gray
    & ".venv\Scripts\Activate.ps1"
}

# 检查依赖
$hasFastapi = $false
try { $null = python -c "import fastapi" 2>&1; $hasFastapi = $true } catch {}
if (-not $hasFastapi) {
    Write-Host "  安装后端依赖..." -ForegroundColor Gray
    pip install -r requirements.txt -q 2>$null
}

Write-Host "  启动 FastAPI 后端（端口 8000）..." -ForegroundColor White

# 设置 PYTHONPATH 让 uvicorn 能找到 backend 模块
$env:PYTHONPATH = $ProjectRoot

$backendJob = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" `
    -PassThru -NoNewWindow -WorkingDirectory $ProjectRoot

Write-Host "  等待后端启动（10 秒）..." -ForegroundColor Gray
Start-Sleep -Seconds 10

try {
    $null = Invoke-WebRequest -Uri "http://localhost:8000/docs" -TimeoutSec 3 -UseBasicParsing 2>$null
    Write-Host "  OK 后端服务已启动：http://localhost:8000" -ForegroundColor Green
    Write-Host "    API 文档：http://localhost:8000/docs" -ForegroundColor Gray
} catch {
    Write-Host "  ! 后端可能正在启动中..." -ForegroundColor DarkYellow
}
Write-Host ""

# ---- 启动前端 ----
Write-Host "[3/4] 启动前端服务..." -ForegroundColor Yellow
$frontendDir = Join-Path $ProjectRoot "src\frontend"

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "  安装前端依赖（首次约 2-5 分钟）..." -ForegroundColor Gray
    Push-Location $frontendDir
    npm install --silent 2>$null
    Pop-Location
}

Write-Host "  启动 Vite 开发服务器（端口 3000）..." -ForegroundColor White

$frontendJob = Start-Process -FilePath "npm" `
    -ArgumentList "run", "dev" `
    -PassThru -NoNewWindow -WorkingDirectory $frontendDir

Write-Host "  等待前端启动（8 秒）..." -ForegroundColor Gray
Start-Sleep -Seconds 8

try {
    $null = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 3 -UseBasicParsing 2>$null
    Write-Host "  OK 前端服务已启动：http://localhost:3000" -ForegroundColor Green
} catch {
    Write-Host "  ! 前端可能正在启动中..." -ForegroundColor DarkYellow
}
Write-Host ""

# ---- 总结 ----
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  服务已启动" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "访问地址：" -ForegroundColor White
Write-Host "  前端：http://localhost:3000" -ForegroundColor White
Write-Host "  后端 API：http://localhost:8000" -ForegroundColor White
Write-Host "  API 文档：http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "后台进程：" -ForegroundColor White
Write-Host "  后端 PID: $($backendJob.Id)" -ForegroundColor Gray
Write-Host "  前端 PID: $($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""

if ($hasDocker) {
    Write-Host "Docker 服务：" -ForegroundColor White
    Write-Host "  Neo4j Browser: http://localhost:7474" -ForegroundColor Gray
    Write-Host "  MySQL: localhost:3306" -ForegroundColor Gray
    Write-Host "  停止：docker compose down" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "停止服务：" -ForegroundColor White
Write-Host "  关闭此窗口，或按 Ctrl+C 后执行：" -ForegroundColor Gray
Write-Host "  Stop-Process -Id $($backendJob.Id),$($frontendJob.Id) -Force" -ForegroundColor Gray
Write-Host ""

# ---- 保持窗口运行 ----
Write-Host "按 Ctrl+C 停止所有服务..." -ForegroundColor DarkYellow
try {
    while ($true) {
        Start-Sleep -Seconds 5
        if ($backendJob.HasExited) {
            Write-Host "! 后端进程已退出" -ForegroundColor Red
            break
        }
        if ($frontendJob.HasExited) {
            Write-Host "! 前端进程已退出" -ForegroundColor Red
            break
        }
    }
} finally {
    Write-Host "正在停止服务..." -ForegroundColor Yellow
    try { Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue } catch {}
    try { Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue } catch {}
    Write-Host "服务已停止" -ForegroundColor Green
}
