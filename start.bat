@echo off
chcp 65001 >nul
echo ========================================
echo   VibeUtopia - 启动中...
echo ========================================
echo.

:: 检查 .env 文件
if not exist ".env" (
    echo [警告] 未找到 .env 文件，正在从 .env.example 复制...
    copy .env.example .env
    echo [重要] 请编辑 .env 文件，填入你的 API Key
    echo.
)

:: 激活 py310 虚拟环境
echo [1/3] 激活 conda py310 环境...
call conda activate py310
if errorlevel 1 (
    echo [错误] 无法激活 py310 环境，请确认 conda 已安装
    pause
    exit /b 1
)

:: 创建数据目录
if not exist "data" mkdir data

:: 启动后端
echo [2/3] 启动后端服务 (FastAPI on port 8000)...
start "VibeUtopia-Backend" cmd /k "conda activate py310 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: 启动前端
echo [3/3] 启动前端界面 (Streamlit on port 8501)...
start "VibeUtopia-Frontend" cmd /k "conda activate py310 && streamlit run frontend/app.py --server.port 8501"

echo.
echo ========================================
echo   启动完成！
echo   后端 API: http://localhost:8000
echo   前端界面: http://localhost:8501
echo   API 文档: http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键退出此窗口（服务将继续运行）...
pause >nul
