#!/bin/bash
# VibeUtopia 环境一键配置脚本
# 使用方法: bash setup.sh
# 支持: macOS / Linux (Ubuntu 22.04+)

set -e

echo "========================================="
echo "  VibeUtopia 环境配置"
echo "========================================="

# ---- 1. 检查 Python ----
echo ""
echo "[1/7] 检查 Python 环境..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "❌ 未找到 Python。请先安装 Python 3.10+"
    echo "   macOS: brew install python@3.12"
    echo "   Ubuntu: sudo apt install python3.12 python3.12-venv"
    exit 1
fi

PYTHON_VERSION=$($PYTHON --version 2>&1)
echo "✅ $PYTHON_VERSION"

# ---- 2. 创建虚拟环境 ----
echo ""
echo "[2/7] 创建虚拟环境..."
if [ -d ".venv" ]; then
    echo "⚠️  .venv 已存在，跳过创建"
else
    $PYTHON -m venv .venv
    echo "✅ 虚拟环境已创建: .venv/"
fi

# 激活虚拟环境
source .venv/bin/activate
echo "✅ 虚拟环境已激活"

# ---- 3. 升级 pip ----
echo ""
echo "[3/7] 升级 pip..."
pip install --upgrade pip setuptools wheel -q
echo "✅ pip 已升级"

# ---- 4. 安装 Python 依赖 ----
echo ""
echo "[4/7] 安装 Python 依赖 (requirements.txt)..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
    echo "✅ Python 依赖安装完成"
else
    echo "⚠️  requirements.txt 未找到"
fi

# ---- 5. 检查 Docker ----
echo ""
echo "[5/7] 检查 Docker 环境..."
if command -v docker &>/dev/null; then
    echo "✅ Docker 已安装"
    if docker info &>/dev/null; then
        echo "✅ Docker 服务正在运行"
        DOCKER_OK=true
    else
        echo "⚠️  Docker 服务未运行。请启动 Docker 后重试。"
        DOCKER_OK=false
    fi
else
    echo "⚠️  Docker 未安装。数据库将使用 SQLite 降级方案。"
    DOCKER_OK=false
fi

# ---- 6. 启动数据库 ----
echo ""
echo "[6/7] 配置数据库..."

if [ "$DOCKER_OK" = true ]; then
    if [ -f "docker-compose.yml" ]; then
        docker-compose up -d 2>/dev/null
        echo "✅ MySQL + Neo4j 已通过 Docker Compose 启动"
        echo "   MySQL: localhost:3306 (vibe_user/vibe_password)"
        echo "   Neo4j: localhost:7687 (neo4j/vibeutopia2024)"
        echo "   Neo4j Browser: http://localhost:7474"
    fi
else
    echo "⚠️  使用 SQLite 降级方案"
    echo "   如需使用 MySQL + Neo4j，请安装 Docker 后运行: docker-compose up -d"
fi

# ---- 7. 配置 .env ----
echo ""
echo "[7/7] 配置环境变量..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ .env 已创建（从 .env.example 复制）"
        echo "⚠️  请编辑 .env 文件，填入你的 LLM API Key"
        echo "   vi .env  # 或任意编辑器"
    fi
else
    echo "✅ .env 已存在"
fi

# ---- 完成 ----
echo ""
echo "========================================="
echo "  配置完成！"
echo "========================================="
echo ""
echo "下一步："
echo "  1. 编辑 .env 填入 LLM API Key"
echo "  2. 激活虚拟环境: source .venv/bin/activate"
echo "  3. 启动后端: uvicorn backend.main:app --reload"
echo "  4. 浏览器打开: http://localhost:8000/docs"
echo ""
echo "前端（可选）："
echo "  cd frontend && npm install && npm run dev"
echo ""
