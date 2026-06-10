# Agnes AI 图像生成接入指南

> 本文档说明如何在 VibeUtopia 中接入 Agnes AI 的图像生成模型。

## 概述

Agnes AI 提供 OpenAI 兼容的图像生成 API，支持文生图和图生图两种模式。VibeUtopia 已将其集成到多模型路由系统中，可通过配置文件一键启用。

| 模型 | 用途 | 模式 |
|------|------|------|
| `agnes-image-2.1-flash` | 纯文生图 | t2i |
| `agnes-image-2.0-flash` | 图生图/图片编辑/多图合成 | img2img |
| `agnes-2.0-flash` | 文本对话 | text |

## 快速接入

### 1. 获取 API Key

访问 [platform.agnes-ai.com](https://platform.agnes-ai.com/) 注册并创建 API Key，无需绑定银行卡，无限期免费。

### 2. 配置环境变量

在项目根目录 `.env` 文件中添加：

```bash
AGNES_API_KEY=sk-your-api-key-here
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
AGNES_MODEL=agnes-2.0-flash
```

> 多 Key 支持：用逗号分隔多个 Key，如 `AGNES_API_KEY=key1,key2,key3`，系统自动轮换。

### 3. 配置模型路由

`data/config/model_config.yaml` 中已预置 Agnes 配置，填入 API Key 后自动生效：

```yaml
providers:
  agnes:
    name: "Agnes AI"
    api_key_env: "AGNES_API_KEY"
    base_url: "https://apihub.agnes-ai.com/v1"
    models:
      - id: "agnes-image-2.1-flash"
        tier: advanced
        vision: false
        text: false
        image_gen: true
        image_mode: "t2i"      # 纯文生图
      - id: "agnes-image-2.0-flash"
        tier: standard
        vision: false
        text: false
        image_gen: true
        image_mode: "img2img"  # 图生图/图片编辑
      - id: "agnes-2.0-flash"
        tier: standard
        vision: false
        text: true
```

### 4. 动态覆盖（可选）

可通过 `.env` 覆盖默认配置，无需修改 YAML：

```bash
AGNES_BASE_URL=https://custom-proxy.example.com/v1  # 代理地址
AGNES_MODEL=agnes-image-2.1-flash                     # 强制指定模型
```

## API 使用

### 文生图

```bash
curl -X POST http://localhost:8000/api/v3/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "一只可爱的柴犬在樱花树下睡觉，温暖的阳光",
    "size": "1024x1024",
    "image_mode": "t2i"
  }'
```

### 图生图

```bash
curl -X POST http://localhost:8000/api/v3/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "改成水彩画风格",
    "size": "1024x768",
    "image_mode": "img2img",
    "image_urls": ["https://example.com/photo.png"]
  }'
```

### 指定模型

```bash
curl -X POST http://localhost:8000/api/v3/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "赛博朋克风格的城市夜景",
    "size": "1024x1024",
    "image_mode": "t2i",
    "model": "agnes-image-2.1-flash"
  }'
```

### 查看可用模型

```bash
curl http://localhost:8000/api/v3/image/models
```

## Python 代码调用

```python
from backend.services.llm_client import call_image_gen

# 文生图
result = await call_image_gen(
    prompt="一只可爱的柴犬在樱花树下睡觉",
    size="1024x1024",
    image_mode="t2i",
)
print(result["images"][0]["url"])

# 图生图
result = await call_image_gen(
    prompt="改成水彩画风格",
    size="1024x768",
    image_mode="img2img",
    image_urls=["https://example.com/photo.png"],
)
```

## API 响应格式

```json
{
  "task_id": "uuid",
  "model": "agnes-image-2.1-flash",
  "provider": "agnes",
  "images": [
    {
      "url": "https://storage.googleapis.com/...",
      "revised_prompt": "A cute Shiba Inu sleeping under cherry blossom trees..."
    }
  ]
}
```

## 路由机制

图像生成调用遵循与文本/视觉模型相同的路由策略：

1. **自动路由**：根据 `image_mode` 选择对应模型（t2i → agnes-image-2.1-flash，img2img → agnes-image-2.0-flash）
2. **Fallback**：指定模式无可用模型时，自动降级到其他图像生成模型
3. **Key 轮换**：多 Key 时自动轮换，限流(429)后标记冷却，冷却结束自动回切
4. **并发控制**：图像生成并发限制为 3（`_image_gen_semaphore`）

## 注意事项

- 纯文生图（t2i）模型**不支持** `response_format` 参数，不要传 `extra_body`
- 图生图（img2img）模型需要通过 `extra_body` 传递 `tags: ["img2img"]` 和参考图片
- 中文 prompt 完全支持，无需翻译为英文
- 图像生成超时为 60 秒（比文本调用的 30 秒更长）
- API 兼容 OpenAI Images API 格式（`/images/generations`）

## 参考链接

- [Agnes AI 官方文档](https://agnes-ai.com/doc/agnes-image-21-flash)
- [Agnes AI 平台](https://platform.agnes-ai.com/)
