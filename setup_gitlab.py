import os

BASE = r'C:\A\gitlab'

dc_content = """version: '3.8'

services:
  gitlab:
    image: gitlab/gitlab-ce:latest
    container_name: gitlab-server
    restart: unless-stopped
    hostname: gitlab.local
    environment:
      GITLAB_OMNIBUS_CONFIG: |
        external_url 'http://gitlab.local:8080'
        gitlab_rails['gitlab_shell_ssh_port'] = 2222
        gitlab_rails['time_zone'] = 'Asia/Shanghai'
        gitlab_rails['initial_root_password'] = 'Xk9mQ7vL2pW4nR8!'
        gitlab_rails['initial_root_password_confirmation'] = 'Xk9mQ7vL2pW4nR8!'
        gitlab_rails['gitlab_default_theme'] = 2
        puma['worker_processes'] = 2
        puma['max_threads'] = 2
        sidekiq['max_concurrency'] = 10
        postgresql['shared_buffers'] = "256MB"
        postgresql['max_connections'] = 200
        nginx['worker_processes'] = 2
        prometheus_monitoring['enable'] = false
        gitlab_rails['monitoring_whitelist'] = ['127.0.0.1']
    ports:
      - '8080:80'
      - '8443:443'
      - '2222:22'
    volumes:
      - C:/A/gitlab/config:/etc/gitlab
      - C:/A/gitlab/data:/var/opt/gitlab
      - C:/A/gitlab/logs:/var/log/gitlab
    shm_size: '256m'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80"]
      interval: 60s
      timeout: 30s
      retries: 10
      start_period: 120s

  gitlab-runner:
    image: gitlab/gitlab-runner:latest
    container_name: gitlab-runner
    restart: unless-stopped
    depends_on:
      gitlab:
        condition: service_healthy
    volumes:
      - C:/A/gitlab/runner:/etc/gitlab-runner
      - /var/run/docker.sock:/var/run/docker.sock
"""

with open(os.path.join(BASE, 'docker-compose.yml'), 'w', encoding='utf-8') as f:
    f.write(dc_content)
print('OK - docker-compose.yml')

start_script = r'''$ErrorActionPreference = "Stop"
$GitLabDir = "C:\A\gitlab"
Set-Location $GitLabDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  GitLab 服务器启动脚本 (Windows 11)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] 检查 Docker 环境..." -ForegroundColor Yellow
try {
    $null = docker info 2>&1
    Write-Host "  OK Docker 正在运行" -ForegroundColor Green
} catch {
    Write-Host "  X Docker 未运行，请先启动 Docker Desktop" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/4] 检查 hosts 文件..." -ForegroundColor Yellow
$hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
$hostsContent = Get-Content $hostsFile -ErrorAction SilentlyContinue
if ($hostsContent -match "gitlab.local") {
    Write-Host "  OK hosts 已配置 gitlab.local" -ForegroundColor Green
} else {
    Write-Host "  ! 需要添加 hosts 映射（需要管理员权限）" -ForegroundColor DarkYellow
    $addHosts = Read-Host "  是否自动添加 127.0.0.1 gitlab.local 到 hosts? (Y/n)"
    if ($addHosts -ne "n") {
        try {
            Add-Content -Path $hostsFile -Value "`n127.0.0.1 gitlab.local" -Force
            Write-Host "  OK hosts 已添加" -ForegroundColor Green
        } catch {
            Write-Host "  X 添加失败，请手动以管理员身份运行:" -ForegroundColor Red
            Write-Host "    Add-Content -Path `"$hostsFile`" -Value `"`n127.0.0.1 gitlab.local`"" -ForegroundColor Gray
        }
    }
}

Write-Host ""
Write-Host "[3/4] 拉取 GitLab 镜像（首次约 2-5 GB，请耐心等待）..." -ForegroundColor Yellow
docker compose pull

Write-Host ""
Write-Host "[4/4] 启动 GitLab 服务..." -ForegroundColor Yellow
docker compose up -d

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  GitLab 正在启动..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "首次启动约需 3-5 分钟，请耐心等待..." -ForegroundColor DarkYellow
Write-Host ""
Write-Host "访问信息：" -ForegroundColor White
Write-Host "  Web 地址：http://gitlab.local:8080" -ForegroundColor White
Write-Host "  HTTPS：   https://gitlab.local:8443" -ForegroundColor White
Write-Host "  SSH 端口：2222" -ForegroundColor White
Write-Host ""
Write-Host "登录信息：" -ForegroundColor White
Write-Host "  用户名：  root" -ForegroundColor White
Write-Host "  密码：    Xk9mQ7vL2pW4nR8!" -ForegroundColor White
Write-Host ""
Write-Host "常用命令：" -ForegroundColor White
Write-Host "  查看状态：  docker compose ps" -ForegroundColor Gray
Write-Host "  查看日志：  docker compose logs -f gitlab" -ForegroundColor Gray
Write-Host "  停止服务：  .\gitlab-stop.ps1" -ForegroundColor Gray
Write-Host "  重启服务：  docker compose restart" -ForegroundColor Gray
Write-Host ""

Write-Host "等待 GitLab 就绪..." -ForegroundColor Yellow
$retries = 0
$maxRetries = 60
while ($retries -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://gitlab.local:8080" -TimeoutSec 5 -UseBasicParsing 2>$null
        if ($response.StatusCode -eq 200) {
            Write-Host ""
            Write-Host "  OK GitLab 已就绪！访问 http://gitlab.local:8080" -ForegroundColor Green
            break
        }
    } catch {}
    $retries++
    Write-Host "." -NoNewline -ForegroundColor Gray
    Start-Sleep -Seconds 10
}

if ($retries -eq $maxRetries) {
    Write-Host ""
    Write-Host "  ! GitLab 仍在启动中，请稍后手动检查 http://gitlab.local:8080" -ForegroundColor DarkYellow
    Write-Host "    查看日志: docker compose -f `"C:\A\gitlab\docker-compose.yml`" logs -f gitlab" -ForegroundColor Gray
}
'''

with open(os.path.join(BASE, 'gitlab-start.ps1'), 'w', encoding='utf-8-sig') as f:
    f.write(start_script)
print('OK - gitlab-start.ps1')

stop_script = r'''$GitLabDir = "C:\A\gitlab"
Set-Location $GitLabDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  停止 GitLab 服务器" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "正在停止 GitLab 服务..." -ForegroundColor Yellow
docker compose down

Write-Host ""
Write-Host "  OK GitLab 服务已停止" -ForegroundColor Green
Write-Host "  数据已保留在 C:\A\gitlab\data 目录中" -ForegroundColor Gray
Write-Host "  重新启动: .\gitlab-start.ps1" -ForegroundColor Gray
'''

with open(os.path.join(BASE, 'gitlab-stop.ps1'), 'w', encoding='utf-8-sig') as f:
    f.write(stop_script)
print('OK - gitlab-stop.ps1')

status_script = r'''$GitLabDir = "C:\A\gitlab"
Set-Location $GitLabDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  GitLab 服务器状态" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

docker compose ps

Write-Host ""
Write-Host "容器健康状态：" -ForegroundColor Yellow
$gitlabStatus = docker inspect --format='{{.State.Health.Status}}' gitlab-server 2>$null
$runnerStatus = docker inspect --format='{{.State.Status}}' gitlab-runner 2>$null

if ($gitlabStatus) {
    $color = if ($gitlabStatus -eq "healthy") { "Green" } else { "DarkYellow" }
    Write-Host "  GitLab:     $gitlabStatus" -ForegroundColor $color
} else {
    Write-Host "  GitLab:     未运行" -ForegroundColor Red
}

if ($runnerStatus) {
    Write-Host "  Runner:     $runnerStatus" -ForegroundColor Green
} else {
    Write-Host "  Runner:     未运行" -ForegroundColor DarkYellow
}

Write-Host ""
Write-Host "资源使用：" -ForegroundColor Yellow
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" gitlab-server 2>$null
'''

with open(os.path.join(BASE, 'gitlab-status.ps1'), 'w', encoding='utf-8-sig') as f:
    f.write(status_script)
print('OK - gitlab-status.ps1')

print('\nAll files created in C:\\A\\gitlab\\')
