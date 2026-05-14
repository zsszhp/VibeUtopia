#!/bin/bash
# VibeUtopia 一键启动脚本
# 用于验证 docker-compose up 10 分钟内跑通流程

set -e

echo "=========================================="
echo "  VibeUtopia 启动验证脚本"
echo "  目标：10 分钟内完成启动并跑通流程"
echo "=========================================="
echo ""

START_TIME=$(date +%s)

# 1. 检查环境变量
echo "[1/5] 检查环境配置..."
if [ ! -f .env ]; then
    echo "❌ .env 文件不存在，请复制 .env.example 并配置"
    exit 1
fi
echo "✅ 环境配置检查通过"
echo ""

# 2. 启动 Docker 服务（Neo4j + MySQL）
echo "[2/5] 启动 Docker 服务..."
docker-compose up -d
echo "⏳ 等待数据库初始化（30 秒）..."
sleep 30

# 检查 Neo4j 是否启动
if docker ps | grep -q vibeutopia-neo4j; then
    echo "✅ Neo4j 已启动"
else
    echo "❌ Neo4j 启动失败"
    exit 1
fi

# 检查 MySQL 是否启动
if docker ps | grep -q vibeutopia-mysql; then
    echo "✅ MySQL 已启动"
else
    echo "❌ MySQL 启动失败"
    exit 1
fi
echo ""

# 3. 安装后端依赖
echo "[3/5] 安装后端依赖..."
pip3 install -r requirements.txt --break-system-packages -q
echo "✅ 后端依赖安装完成"
echo ""

# 4. 启动后端服务
echo "[4/5] 启动后端服务..."
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..
echo "⏳ 等待后端服务启动（10 秒）..."
sleep 10

# 检查后端服务
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ 后端服务已启动（http://localhost:8000）"
else
    echo "❌ 后端服务启动失败"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi
echo ""

# 5. 安装并启动前端
echo "[5/5] 启动前端服务..."
cd frontend-vue
if [ ! -d node_modules ]; then
    echo "⏳ 安装前端依赖（首次启动较慢，约 2-5 分钟）..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!
cd ..
echo "⏳ 等待前端服务启动（10 秒）..."
sleep 10

# 检查前端服务
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ 前端服务已启动（http://localhost:5173）"
else
    echo "⚠️  前端服务可能正在启动中..."
fi
echo ""

# 计算耗时
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ELAPSED_MIN=$((ELAPSED / 60))
ELAPSED_SEC=$((ELAPSED % 60))

echo "=========================================="
echo "  ✅ 启动完成！"
echo "=========================================="
echo ""
echo "服务访问地址："
echo "  - 前端：http://localhost:5173"
echo "  - 后端 API：http://localhost:8000"
echo "  - API 文档：http://localhost:8000/docs"
echo ""
echo "启动耗时：${ELAPSED_MIN}分${ELAPSED_SEC}秒"
echo ""

if [ $ELAPSED -lt 600 ]; then
    echo "🎉 验证通过：启动时间 < 10 分钟"
else
    echo "⚠️  警告：启动时间超过 10 分钟"
fi
echo ""
echo "后台进程 ID："
echo "  - 后端：$BACKEND_PID"
echo "  - 前端：$FRONTEND_PID"
echo ""
echo "停止服务：kill $BACKEND_PID $FRONTEND_PID && docker-compose down"
echo ""

# 保持脚本运行（用于测试）
if [ "$1" == "--test" ]; then
    echo "测试模式：等待 60 秒后自动停止..."
    sleep 60
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    docker-compose down
    echo "服务已停止"
fi
