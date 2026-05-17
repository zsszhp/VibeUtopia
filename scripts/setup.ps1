# VibeUtopia Windows 环境一键配置脚本
# 使用方法: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  VibeUtopia 环境配置 (Windows)" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# ---- 1. 检查 Python ----
Write-Host ""
Write-Host "[1/7] 检查 Python 环境..." -ForegroundColor Yellow
$pythonCmd = $null
try {
    $pyVer = python --version 2>&1
    $pythonCmd = "python"
    Write-Host "  OK $pyVer" -ForegroundColor Green
} catch {
    try {
        $pyVer = python3 --version 2>&1
        $pythonCmd = "python3"
        Write-Host "  OK $pyVer" -ForegroundColor Green
    } catch {
        Write-Host "  X 未找到 Python。请先安装 Python 3.10+" -ForegroundColor Red
        Write-Host "    下载: https://www.python.org/downloads/" -ForegroundColor Gray
        exit 1
    }
}

# ---- 2. 创建虚拟环境 ----
Write-Host ""
Write-Host "[2/7] 创建虚拟环境..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "  ! .venv 已存在，跳过创建" -ForegroundColor DarkYellow
} else {
    & $pythonCmd -m venv .venv
    Write-Host "  OK 虚拟环境已创建: .venv\" -ForegroundColor Green
}

# 激活虚拟环境
& ".venv\Scripts\Activate.ps1"
Write-Host "  OK 虚拟环境已激活" -ForegroundColor Green

# ---- 3. 升级 pip ----
Write-Host ""
Write-Host "[3/7] 升级 pip..." -ForegroundColor Yellow
pip install --upgrade pip setuptools wheel -q 2>$null
Write-Host "  OK pip 已升级" -ForegroundColor Green

# ---- 4. 安装 Python 依赖 ----
Write-Host ""
Write-Host "[4/7] 安装 Python 依赖 (requirements.txt)..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt -q 2>$null
    Write-Host "  OK Python 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  ! requirements.txt 未找到" -ForegroundColor DarkYellow
}

# ---- 5. 检查 Docker ----
Write-Host ""
Write-Host "[5/7] 检查 Docker 环境..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    $dockerOk = $true
    Write-Host "  OK Docker 已安装且正在运行" -ForegroundColor Green
} catch {
    try {
        $null = docker --version 2>&1
        Write-Host "  ! Docker 已安装但服务未运行，请启动 Docker Desktop" -ForegroundColor DarkYellow
    } catch {
        Write-Host "  ! Docker 未安装。数据库将使用 SQLite 降级方案。" -ForegroundColor DarkYellow
        Write-Host "    下载: https://www.docker.com/products/docker-desktop" -ForegroundColor Gray
    }
}

# ---- 6. 启动数据库 ----
Write-Host ""
Write-Host "[6/7] 配置数据库..." -ForegroundColor Yellow
if ($dockerOk) {
    if (Test-Path "docker-compose.yml") {
        docker compose up -d 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK MySQL + Neo4j 已通过 Docker Compose 启动" -ForegroundColor Green
            Write-Host "    MySQL: localhost:3306 (vibe_user/vibe_password)" -ForegroundColor Gray
            Write-Host "    Neo4j:  localhost:7687 (neo4j/vibeutopia2024)" -ForegroundColor Gray
            Write-Host "    Neo4j Browser: http://localhost:7474" -ForegroundColor Gray
        } else {
            Write-Host "  ! Docker Compose 启动失败，将使用 SQLite 降级方案" -ForegroundColor DarkYellow
        }
    }
} else {
    Write-Host "  ! 使用 SQLite 降级方案" -ForegroundColor DarkYellow
    Write-Host "    如需使用 MySQL + Neo4j，请安装 Docker Desktop 后运行: docker compose up -d" -ForegroundColor Gray
}

# ---- 7. 配置 .env ----
Write-Host ""
Write-Host "[7/7] 配置环境变量..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item .env.example .env
        Write-Host "  OK .env 已创建（从 .env.example 复制）" -ForegroundColor Green
        Write-Host "  ! 请编辑 .env 文件，填入你的 LLM API Key" -ForegroundColor DarkYellow
        Write-Host "    notepad .env" -ForegroundColor Gray
    }
} else {
    Write-Host "  OK .env 已存在" -ForegroundColor Green
}

# ---- 完成 ----
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  配置完成！" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步：" -ForegroundColor White
Write-Host "  1. 编辑 .env 填入 LLM API Key:  notepad .env" -ForegroundColor White
Write-Host "  2. 一键启动:  powershell -ExecutionPolicy Bypass -File scripts\start.ps1" -ForegroundColor White
Write-Host ""
