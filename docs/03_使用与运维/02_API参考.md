# API参考

> **文档定位**：使用与运维｜REST/WebSocket 接口定义与示例
> **所属目录**：`docs/03_使用与运维/`


> 版本：v3.2.0 | 基础路径：`http://localhost:8000`

## 目录

- [鉴权](#鉴权)
- [限流](#限流)
- [阶段1 核心端点](#阶段1-核心端点)
- [阶段3 V3 端点](#阶段3-v3-端点)
- [阶段5 新增端点](#阶段5-新增端点)
- [阶段6 新增端点](#阶段6-新增端点)
- [人生故事生成端点](#人生故事生成端点)
- [健康检查端点](#健康检查端点)
- [WebSocket 端点](#websocket-端点)
- [通用错误码](#通用错误码)

---

## 鉴权

所有 `/api/**` 与 `/ws/**` 端点支持可选 API Key 鉴权：

| 场景 | 行为 |
|------|------|
| 环境变量 `API_KEY` 已配置 | 请求必须携带 `X-API-Key: <key>` 或 `Authorization: Bearer <key>`，缺失/错误返回 `401` |
| `API_KEY` 未配置 | 本地开发放行；响应头返回 `X-API-Auth: disabled` 与 `X-API-Auth-Warning`（生产必须配置） |

- 比较为常量时间（`secrets.compare_digest`）。
- WebSocket 在握手阶段校验同名请求头，未通过直接关闭（code 1008）。
- 免鉴权探活：`/health`、`/healthz`、`/ready`（供 SLB/K8s 使用）；`/api/v1/health` 受鉴权保护。
- 生产环境必须配置强随机 `API_KEY`，示例请求头：`X-API-Key: <你的key>`。

---

## 限流

所有 `/api/**` 端点启用滑动窗口限流（单进程内存计数），按客户端 IP 计数：

| 项目 | 行为 |
|------|------|
| 配额 | 环境变量 `RATE_LIMIT_PER_MIN`（默认 `60`），每客户端每分钟最大请求数 |
| 窗口 | 滑动窗口 60 秒，窗口外的历史请求不计入 |
| 超限响应 | `429 Too Many Requests`，响应体 `{"detail": "<可读消息>"}`（含限额说明） |
| 豁免 | `/health`、`/healthz`、`/ready` 探活端点不受限流（供 SLB/K8s 使用） |
| 关闭限流 | `RATE_LIMIT_PER_MIN<=0` 表示不限流（仅测试/特殊场景） |

- `X-Forwarded-For` 首个地址优先作为客户端标识（反代场景），否则取直连 IP。
- 计数为**单进程内存**实现；多进程/多实例部署时各进程独立计数，如需全局限额需换共享存储。
- 超限响应与全局错误格式一致，前端通过 `response.data.detail` 取错误信息。

**429 响应示例：**

```json
{
  "detail": "请求过于频繁：每分钟最多 60 次（限流窗口 60 秒），请稍后重试"
}
```

**调用方建议：** 收到 429 后按指数退避重试；批量任务控制并发在配额以内。

---

## 阶段1 核心端点

基础路径：`/api/v1`

### 1. 提交内容预审

```
POST /api/v1/review
```

统一入口，支持文本/视频/混合三种输入模式。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | string | 否 | 输入模式：`text`/`video`/`mixed`，默认 `text` |
| `texts` | array | 否 | 文本内容列表 `[{type, content}]` |
| `video_files` | array | 否 | 上传后的视频文件路径列表 |
| `options` | object | 否 | 分析选项 |

**options 对象：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `depth` | string | 分析深度：`quick`/`standard`/`deep`/`large_scale` |
| `platforms` | array | 指定分析平台列表 |
| `enable_simulation` | boolean | 是否启用仿真推演 |

**请求示例：**

```json
{
  "mode": "text",
  "texts": [{"type": "text", "content": "待分析的内容文本..."}],
  "options": {
    "depth": "standard",
    "platforms": ["weibo", "douyin", "bilibili"],
    "enable_simulation": true
  }
}
```

**响应：**

```json
{
  "task_id": "uuid-string",
  "status": "processing",
  "estimated_depth": "标准分析",
  "estimated_duration_seconds": 180
}
```

---

### 2. 获取预审结果

```
GET /api/v1/review/{task_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务ID |

**响应（完成状态）：**

```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "overall_risk": 65,
  "risk_level": "orange",
  "method": "standard",
  "dimensions": [
    {
      "name": "价值观偏差",
      "score": 70,
      "severity": "high",
      "evidence": "具体证据描述",
      "evidence_source": {"type": "text", "content": "...", "location": "..."},
      "confidence": 0.85,
      "suggestion": "修改建议",
      "affected_groups": ["青少年", "女性"]
    }
  ],
  "platform_reactions": {
    "weibo": {"positive": 0.2, "neutral": 0.3, "negative": 0.5},
    "douyin": {"positive": 0.3, "neutral": 0.4, "negative": 0.3}
  },
  "signal_correlations": [
    {
      "signal_id": "sig_xxx",
      "title": "热点标题",
      "platform": "weibo",
      "correlation_score": 0.85,
      "risk_boost": 5.0
    }
  ],
  "confidence": 0.82,
  "uncertainty_sources": ["转写质量不佳"],
  "cross_effects": [
    {
      "dimensions": ["价值观偏差", "社会撕裂"],
      "description": "交叉效应描述",
      "combined_severity": "high"
    }
  ],
  "suggestions": [
    {
      "original": "原始文本",
      "suggestion": "建议修改为",
      "dimension": "价值观偏差"
    }
  ],
  "evidence_chains": [
    {
      "id": "chain_1",
      "source": "text",
      "content": "证据内容",
      "confidence": 0.9,
      "cross_validation": ["验证来源1"]
    }
  ],
  "confidence_breakdown": {
    "overall": 0.82,
    "factors": {
      "data_quality": 0.85,
      "consistency": 0.80,
      "evidence": 0.78,
      "platform_validation": 0.85
    }
  }
}
```

**风险等级对照：**

| 分数范围 | 等级 | 颜色 |
|----------|------|------|
| 0-25 | 低风险 | green |
| 26-55 | 中等风险 | yellow |
| 56-75 | 高风险 | orange |
| 76-100 | 极高风险 | red |

---

### 3. 获取分析进度

```
GET /api/v1/review/{task_id}/progress
```

**响应：**

```json
{
  "task_id": "uuid-string",
  "current_step": "assessment",
  "progress": 0.3,
  "detail": "正在进行风险评估...",
  "completed_dimensions": [],
  "remaining_dimensions": []
}
```

**步骤说明：**

| 步骤 | 说明 | 进度 |
|------|------|------|
| `understanding` | 理解内容 | 0.0 |
| `assessment` | 风险评估 | 0.3 |
| `signal` | 采集平台信号 | 0.5 |
| `simulation` | 推演平台反应 | 0.7 |
| `report` | 生成报告 | 0.9-1.0 |

---

### 4. 获取历史记录

```
GET /api/v1/history?page=1&per_page=20&risk_level=orange
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `page` | int | 页码，默认 1 |
| `per_page` | int | 每页条数，默认 20 |
| `risk_level` | string | 风险等级筛选：`green`/`yellow`/`orange`/`red` |

**响应：**

```json
{
  "total": 100,
  "items": [
    {
      "task_id": "uuid-string",
      "status": "completed",
      "created_at": "2026-05-15T10:00:00+00:00",
      "overall_risk": 65,
      "risk_level": "orange"
    }
  ]
}
```

---

### 5. LLM 计量汇总

```
GET /api/v1/metrics/summary?n=50
```

LLM 调用计量汇总（成本/耗时/失败率）。每次 LLM/VLM/图像生成调用会原子追加一条记录到 `data/metrics/llm_usage.jsonl`（含 model、prompt/completion tokens、耗时、成败）。

Query 参数：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| n | int | 50 | 最近 N 次分析（无 analysis_id 时退化为最近 N 条调用），上限 1000 |

响应示例：

```json
{
  "available": true,
  "window": 50,
  "window_unit": "analyses",
  "calls": 120,
  "failures": 3,
  "failure_rate": 0.025,
  "latency_ms": {"p50": 1200.5, "p90": 3400.2, "p99": 8100.0, "mean": 1650.3},
  "tokens": {"prompt": 120000, "completion": 48000, "usage_reported_calls": 118},
  "by_model": {"deepseek-chat": {"calls": 100, "failures": 2, "failure_rate": 0.02, "latency_ms": {"p50": 1100, "p90": 3000, "p99": 7000, "mean": 1500}}},
  "analyses": {"count": 20, "calls": 120, "failure_rate": 0.025, "latency_ms": {"p50": 1200.5, "p90": 3400.2, "p99": 8100.0, "mean": 1650.3}}
}
```

无任何调用记录时返回 `available=false`（`calls=0`、`failure_rate=null`、`latency_ms=null`），不报错。

---

### 6. 获取可用模型



```
GET /api/v1/models
```

**响应：**

```json
{
  "hardware_tier": "pro",
  "models": {
    "text_analysis": {
      "primary": "api-deepseek-pro",
      "fallback": "deepseek-chat"
    },
    "vision": {
      "primary": "local-qwen-vl-8b",
      "fallback": "glm-4v"
    },
    "audio": {
      "primary": "local-whisper-large",
      "fallback": "faster-whisper-local"
    },
    "ocr": {
      "primary": "qwen3-vl-plus-api",
      "fallback": "glm-ocr-api"
    },
    "agent_simulation": {
      "primary": "local-qwen-8b",
      "fallback": "qwen3-8b"
    }
  }
}
```

---

### 7. 上传文件

```
POST /api/v1/upload
```

**请求：** `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `file` | File | 视频文件 |

支持格式：mp4, mov, avi, webm，最大 100MB。

**响应：**

```json
{
  "file_path": "/path/to/uploaded/file.mp4",
  "file_name": "video.mp4",
  "file_size": 52428800
}
```

---

### 8. 人格生成

```
POST /api/v1/persona/generate
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `platform` | string | 否 | 平台名，默认 `bilibili` |
| `archetype` | string | 否 | 原型类型，默认 `主流用户` |
| `tier` | string | 否 | 生成层级 A/B/C，默认 `C` |
| `base_profile` | object | 否 | 基础人口统计信息 |

**响应：**

```json
{
  "tier": "C",
  "life_story": "人生故事文本...",
  "persona_7layers": {},
  "big_five": {
    "openness": 0.7,
    "conscientiousness": 0.5,
    "extraversion": 0.6,
    "agreeableness": 0.4,
    "neuroticism": 0.3
  },
  "quality_score": 0.85,
  "platform": "bilibili",
  "archetype": "主流用户"
}
```

---

### 9. 批量人格生成

```
POST /api/v1/persona/generate-batch
```

**请求体：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `platform` | string | 平台名 |
| `count` | int | 生成数量 |
| `tier_distribution` | object | 各层级数量 `{"A": 1, "B": 3, "C": 6}` |

---

### 10. 存储记忆

```
POST /api/v1/memory/store
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent 唯一标识 |
| `content` | string | 是 | 记忆内容 |
| `memory_type` | string | 否 | 类型：`observation`/`reflection`/`plan`，默认 `observation` |
| `importance` | float | 否 | 重要性 0-1，默认 0.5 |
| `tags` | array | 否 | 标签列表 |

---

### 11. 检索记忆

```
POST /api/v1/memory/retrieve
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent 唯一标识 |
| `query` | string | 是 | 查询文本 |
| `top_k` | int | 否 | 返回数量，默认 5 |

---

### 12. 获取记忆状态

```
GET /api/v1/memory/status
```

**响应：**

```json
{
  "chromadb_available": true,
  "total_memories": 1500,
  "agent_memories": {
    "agent_001": 120,
    "agent_002": 85
  }
}
```

---

## 阶段3 V3 端点

基础路径：`/api/v3`

### 多模态分析

#### 多模态内容分析

```
POST /api/v3/analyze-multimodal
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image_urls` | array | 是 | 图片 URL 列表 |
| `text_prompt` | string | 是 | 分析提示词 |
| `task_type` | string | 否 | 任务类型，默认 `multimodal_analysis` |
| `model_provider` | string | 否 | 指定模型厂商 |

**响应：**

```json
{
  "task_id": "uuid-string",
  "analysis": "分析结果文本",
  "model_used": "auto-routed",
  "confidence": 0.85
}
```

#### 上传图片分析

```
POST /api/v3/upload-image-analyze
```

**请求：** `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `image` | File | 图片文件 |
| `prompt` | string | 分析提示词 |

---

### 音频转写

```
POST /api/v3/transcribe-audio
```

**请求：** `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `audio_file` | File | 音频文件 |
| `speaker_separation` | boolean | 是否说话人分离，默认 true |

**响应：**

```json
{
  "task_id": "uuid-string",
  "text": "完整转写文本",
  "sentences": [
    {"text": "句子内容", "start": 0.0, "end": 2.5, "speaker": "SPEAKER_01"}
  ],
  "duration": 120.5,
  "language": "zh"
}
```

---

### 人格生成（V3）

#### 生成人格

```
POST /api/v3/generate-persona
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `platform` | string | 是 | 平台名称 |
| `archetype` | string | 是 | 原型类型 |
| `tier` | string | 否 | 生成层级 A/B/C，默认 C |
| `count` | int | 否 | 生成数量 1-10，默认 1 |

#### 批量生成人格

```
POST /api/v3/generate-persona-batch
```

**请求：** `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `platform` | string | 平台名 |
| `count` | int | 生成数量，默认 10 |
| `tier_distribution` | string | JSON 字符串，如 `'{"A": 1, "B": 3, "C": 6}'` |

---

### ChromaDB 向量检索

#### 检索记忆

```
POST /api/v3/retrieve-memory
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `query` | string | 是 | 查询文本 |
| `top_k` | int | 否 | 返回数量 1-50，默认 10 |

**响应：**

```json
{
  "memories": [...],
  "chromadb_used": true
}
```

#### 获取 Memory Stream 状态

```
GET /api/v3/memory-stream-status
```

#### 存储记忆

```
POST /api/v3/store-memory
```

**请求：** `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_id` | string | Agent ID |
| `content` | string | 记忆内容 |
| `memory_type` | string | 类型，默认 `observation` |
| `importance` | float | 重要性 0-1，默认 0.5 |
| `tags` | string | JSON 数组字符串，默认 `[]` |

---

### 模型路由控制

#### 获取最优模型路由

```
POST /api/v3/route-model
```

**请求体：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_type` | string | 任务类型，默认 `default` |
| `exclude_models` | array | 排除的模型列表 |

**响应：**

```json
{
  "provider": "aliyun",
  "model": "qwen-max",
  "tier": "standard",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
}
```

#### 列出可用模型

```
GET /api/v3/available-models
```

**响应：**

```json
{
  "providers": ["longcat", "deepseek", "aliyun"],
  "total_endpoints": 5
}
```

#### 设置模型覆盖

```
POST /api/v3/set-model-override
```

**请求：** `multipart/form-data`

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | 厂商名 |
| `model` | string | 模型名 |

---

### 硬件检测

#### 获取硬件信息

```
GET /api/v3/hardware-info
```

**响应：**

```json
{
  "gpu_available": true,
  "gpu_name": "NVIDIA RTX 4090",
  "vram_total_gb": 24.0,
  "cpu_cores": 16,
  "memory_total_gb": 64.0,
  "recommended_tier": "ultra"
}
```

#### 获取推荐模型

```
GET /api/v3/recommended-models
```

---

### 模型状态监控

#### 获取模型 Key 池状态

```
GET /api/v3/model-status
```

#### 测试 LLM 调用

```
GET /api/v3/llm-test?prompt=你好&task_type=default
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `prompt` | string | 测试提示词 |
| `task_type` | string | 任务类型 |

---

### 报告质量优化

#### 优化风险报告

```
POST /api/v3/optimize-report
```

**请求体：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `report` | object | 原始风险报告 |

**响应：**

```json
{
  "optimized_report": {...},
  "actionability_score": 0.85
}
```

#### 获取风险等级定义

```
GET /api/v3/risk-levels
```

#### 获取风险维度列表

```
GET /api/v3/risk-dimensions
```

---

## 阶段5 新增端点

### 规模化仿真

#### 设置仿真规模

```
POST /api/v3/simulation/scale
```

**请求体：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `level` | string | 规模级别：`lightweight`/`standard`/`deep`/`massive` |
| `overrides` | object | 自定义配置覆盖 |

**响应：**

```json
{
  "level": "standard",
  "level_label": "标准仿真",
  "total_agents": 50,
  "equivalent_individuals": 50000,
  "estimated_duration_min": 3.0,
  "estimated_duration_max": 8.0,
  "estimated_cost_min": 0.5,
  "estimated_cost_max": 2.0,
  "group_agent_enabled": true,
  "tier_breakdown": {"A": 5, "B": 15, "C": 30}
}
```

#### 获取仿真规模级别

```
GET /api/v3/simulation/scale-levels
```

#### 验证仿真规模可行性

```
GET /api/v3/simulation/scale-feasibility?level=massive
```

---

### 批量分析

#### 提交批量分析

```
POST /api/v3/batch/submit
```

**请求体：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `contents` | array | 待分析内容列表 |
| `mode` | string | 分析模式：`quick`/`deep` |
| `batch_id` | string | 批次ID（可选） |

#### 获取批量分析状态

```
GET /api/v3/batch/{batch_id}/status
```

#### 获取批量分析结果

```
GET /api/v3/batch/{batch_id}/results
```

#### 获取批量分析缓存统计

```
GET /api/v3/batch/cache-stats
```

---

### 极化预警

#### 获取极化预警

```
GET /api/v3/polarization/warning?polarization_index=0.7&trend=rising
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `polarization_index` | float | 极化指数 |
| `trend` | string | 趋势：`rising`/`stable`/`falling` |

#### 获取极化预警等级定义

```
GET /api/v3/polarization/levels
```

---

### 回测增强

#### 运行回测一致性检查

```
POST /api/v3/backtest/consistency?case_id=bt_10&run_count=3
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `case_id` | string | 案例ID，默认 `bt_10` |
| `run_count` | int | 运行次数，默认 3 |

#### 生成 V2 vs MVP 对比报告

```
POST /api/v3/backtest/v2-vs-mvp?enable_consistency=true
```

---

## 阶段6 新增端点

### 信号采集面板

#### 获取当前热榜

```
GET /api/v3/signals/hotlist?platform=weibo&limit=20
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `platform` | string | 平台筛选 |
| `limit` | int | 返回数量，默认 20 |

**响应：**

```json
{
  "hotlist": [
    {
      "signal_id": "sig_xxx",
      "title": "热点标题",
      "platform": "weibo",
      "rank": 1,
      "url": "https://...",
      "first_seen": "2026-05-15T08:00:00+00:00",
      "last_seen": "2026-05-15T10:00:00+00:00",
      "appearance_count": 5,
      "is_new": true,
      "category": "社会"
    }
  ],
  "total": 20
}
```

#### 获取检测到的事件

```
GET /api/v3/signals/events?status=active&limit=20
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | 事件状态筛选 |
| `limit` | int | 返回数量 |

#### 获取调度器状态

```
GET /api/v3/signals/scheduler/status
```

**响应：**

```json
{
  "is_running": true,
  "current_mode": "standard",
  "platform_count": 5
}
```

#### 启动调度器

```
POST /api/v3/signals/scheduler/start
```

**请求体：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | string | 调度模式：`realtime`/`standard`/`economy`/`manual` |

#### 停止调度器

```
POST /api/v3/signals/scheduler/stop
```

---

### 知识图谱可视化

#### 图谱概览

```
GET /api/v3/graph/overview
```

**响应：**

```json
{
  "connected": true,
  "node_count": 500,
  "edge_count": 1200,
  "community_count": 0,
  "labels": ["Person", "Event", "Organization"],
  "relationship_types": ["INFLUENCES", "TRIGGERS", "SUPPORTS"]
}
```

#### 实体详情

```
GET /api/v3/graph/entity/{entity_id}
```

**响应：**

```json
{
  "entity": {
    "entity_id": "xxx",
    "name": "实体名称",
    "entity_type": "Person"
  },
  "relations": [...]
}
```

#### 实体间路径查询

```
GET /api/v3/graph/paths?from_id=xxx&to_id=yyy&max_depth=5
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `from_id` | string | 起始实体ID |
| `to_id` | string | 目标实体ID |
| `max_depth` | int | 最大搜索深度 1-10，默认 5 |

**响应：**

```json
{
  "from_id": "xxx",
  "to_id": "yyy",
  "path": [
    {"step": 0, "node": {"entity_id": "xxx", "name": "..."}},
    {"step": 1, "node": {"entity_id": "mid", "name": "..."}},
    {"step": 2, "node": {"entity_id": "yyy", "name": "..."}}
  ],
  "found": true
}
```

#### 实体邻居

```
GET /api/v3/graph/neighbors/{entity_id}?depth=2&limit=50
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `depth` | int | 遍历深度，默认 1 |
| `limit` | int | 返回数量限制，默认 50 |

---

### 博主历史分析

#### 博主历史分析

```
GET /api/v3/blogger/{blogger_id}/history
```

**响应：**

```json
{
  "blogger_id": "blogger_001",
  "total_analyses": 15,
  "avg_risk_score": 45.2,
  "risk_level_distribution": {"green": 5, "yellow": 6, "orange": 3, "red": 1},
  "high_risk_dimensions": ["价值观偏差", "社会撕裂"],
  "risk_tolerance": "中等",
  "risk_pattern": "波动型",
  "trend_summary": "风险呈上升趋势",
  "dimension_changes": [
    {
      "dimension": "价值观偏差",
      "direction": "rising",
      "current_score": 65,
      "previous_score": 50,
      "change_rate": 0.3,
      "trend_description": "该维度风险持续上升"
    }
  ],
  "trend_data": [...],
  "prediction": "预计下期风险将维持在中等水平",
  "confidence": 0.75
}
```

#### 博主风险画像

```
GET /api/v3/blogger/{blogger_id}/risk-profile
```

---

### 竞品对比

```
POST /api/v3/competitor/compare
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `blogger_id` | string | 是 | 博主ID |
| `competitor_ids` | array | 是 | 竞品ID列表 |
| `field_name` | string | 否 | 所属领域 |

**响应：**

```json
{
  "blogger_id": "blogger_001",
  "competitor_ids": ["comp_001", "comp_002"],
  "field_name": "科技评测",
  "dimension_comparisons": [
    {
      "dimension": "价值观偏差",
      "blogger_score": 45,
      "competitor_score": 35,
      "field_average": 40,
      "relative_position": "above_average",
      "advantage": false,
      "gap_value": 10
    }
  ],
  "strengths": ["内容质量较高"],
  "weaknesses": ["价值观风险偏高"],
  "overall_risk_rank": 3,
  "total_in_field": 10,
  "risk_position": "中上",
  "summary": "对比分析摘要",
  "error": null
}
```

---

### 反事实仿真

```
POST /api/v3/counterfactual/simulate
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 是 | 原始文案 |
| `risk_items` | array | 是 | 风险项列表 |
| `strategy_type` | string | 否 | 修改策略：`delete`/`replace`/`soften`/`rephrase`，默认 `soften` |

**响应：**

```json
{
  "result_id": "cf_xxx",
  "original_text": "原始文案...",
  "modified_text": "修改后文案...",
  "strategy": {
    "strategy_type": "soften",
    "target_sentence": "目标句子",
    "modified_sentence": "修改后句子",
    "description": "策略描述"
  },
  "before": {
    "overall_risk_score": 70,
    "risk_level": "orange",
    "dimension_scores": {"价值观偏差": 75, "社会撕裂": 60}
  },
  "after": {
    "overall_risk_score": 45,
    "risk_level": "yellow",
    "dimension_scores": {"价值观偏差": 50, "社会撕裂": 40}
  },
  "comparisons": [
    {
      "dimension": "价值观偏差",
      "before_score": 75,
      "after_score": 50,
      "change": -25,
      "change_direction": "down"
    }
  ],
  "overall_improvement": 25,
  "recommendation": "建议采用 soften 策略修改该句",
  "error": null
}
```

---

### 决策辅助

```
POST /api/v3/decision/advise
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 否 | 任务ID |
| `risk_report` | object | 是 | 风险评估报告 |

**响应：**

```json
{
  "report_id": "da_xxx",
  "task_id": "uuid-string",
  "advice": {
    "advice_type": "conditional_release",
    "advice_label": "条件发布",
    "confidence": 0.85,
    "overall_risk_score": 65,
    "risk_level": "orange",
    "modification_priorities": [
      {
        "priority": 1,
        "dimension": "价值观偏差",
        "sentence": "需要修改的句子",
        "severity": "high",
        "suggested_action": "建议修改为...",
        "estimated_risk_reduction": 15,
        "effort": "low"
      }
    ],
    "estimated_final_risk": 40,
    "estimated_risk_reduction": 25,
    "key_risk_factors": ["价值观偏差", "社会撕裂"],
    "reasoning": "决策推理过程..."
  },
  "risk_summary": "风险摘要",
  "recommendations": ["建议1", "建议2"],
  "created_at": "2026-05-15T10:00:00+00:00"
}
```

---

## 人生故事生成端点

基础路径：`/api/v1/story`

### 生成人生故事

```
POST /api/v1/story/generate
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户 ID |
| `persona_data` | object | 是 | 完整人格画像 |
| `include_scenes` | boolean | 否 | 是否生成场景故事，默认 true |
| `include_analysis` | boolean | 否 | 是否包含心理分析，默认 true |

**响应：**

```json
{
  "task_id": "story_user001_20260515100000",
  "status": "processing",
  "message": "人生故事生成任务已启动",
  "estimated_time": 45
}
```

### 获取人生故事

```
GET /api/v1/story/{user_id}
```

### 获取人生时间线

```
GET /api/v1/story/{user_id}/timeline
```

### 获取场景故事列表

```
GET /api/v1/story/{user_id}/scenes
```

### 获取完整人生故事

```
GET /api/v1/story/{user_id}/full
```

### 模拟人格演化

```
POST /api/v1/story/{user_id}/evolve
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户 ID |
| `event_ids` | array | 是 | 触发事件 ID 列表 |
| `simulate_years` | int | 否 | 模拟年数，默认 10 |

---

## 健康检查端点

### 存活探针

```
GET /health
GET /api/v1/health
```

两个路径等价，返回：

```json
{"status": "ok", "service": "vibeutopia", "version": "0.5.0"}
```

### 就绪探针

```
GET /ready
```

检查数据库连接。正常返回 `{"status": "ok", "checks": {"database": "ok"}}`；数据库不可用返回 HTTP 503。

---

## WebSocket 端点

### 仿真状态推送

```
WS /ws/simulation/{sim_id}
```

**客户端可发送控制指令：**

```json
{"action": "pause"}
{"action": "resume"}
```

### 预审分析进度推送

```
WS /ws/review/{task_id}
```

**服务端推送消息类型：**

#### 步骤更新

```json
{
  "type": "step_update",
  "task_id": "uuid-string",
  "step": "assessment",
  "progress": 0.3,
  "detail": "正在进行风险评估...",
  "completed_dimensions": [],
  "remaining_dimensions": []
}
```

#### 风险预警

```json
{
  "type": "risk_alert",
  "task_id": "uuid-string",
  "dimension": "价值观偏差",
  "score": 80,
  "severity": "high",
  "evidence": "证据描述"
}
```

#### 分析完成

```json
{
  "type": "review_complete",
  "task_id": "uuid-string",
  "risk_level": "orange",
  "overall_risk": 65,
  "dimensions_count": 7
}
```

---

## 通用错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 422 | 请求体校验失败（detail 为可读字符串） |
| 500 | 服务器内部错误（detail 统一为"服务器内部错误"，不外泄内部堆栈） |
| 503 | 服务不可用（如 Neo4j 未连接、`/ready` 探针未通过） |

**错误响应格式（全局统一）：**

```json
{
  "detail": "错误描述信息"
}
```

所有 4xx/5xx 响应均使用 `{"detail": "<字符串>"}` 格式，前端通过 `response.data.detail` 取错误信息。未处理异常的 500 响应不包含内部堆栈；完整堆栈仅记录在服务端日志。
