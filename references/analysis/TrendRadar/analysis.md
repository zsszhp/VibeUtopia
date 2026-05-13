# TrendRadar 深度分析

## 关键实现细节

### 数据源配置 (config/config.yaml)

**热榜源（11个平台）**：
```yaml
platforms:
  enabled: true
  sources:
    - id: "toutiao"              # 今日头条
    - id: "baidu"                # 百度热搜
    - id: "wallstreetcn-hot"     # 华尔街见闻
    - id: "thepaper"             # 澎湃新闻
    - id: "bilibili-hot-search"  # B站热搜
    - id: "cls-hot"              # 财联社
    - id: "ifeng"                # 凤凰网
    - id: "tieba"                # 贴吧
    - id: "weibo"                # 微博
    - id: "douyin"               # 抖音
    - id: "zhihu"                # 知乎
```

**RSS源**：
```yaml
rss:
  freshness_filter:
    enabled: true
    max_age_days: 1
  feeds:
    - id: "hacker-news"
      name: "Hacker News"
      url: "https://hnrss.org/frontpage"
    - id: "yahoo-finance"
      name: "雅虎财经"
      url: "https://finance.yahoo.com/news/rssindex"
```

### 热榜数据抓取 (crawler/fetcher.py)

- **API端点**：`https://newsnow.busiyi.world/api/s?id={platform_id}&latest`
- **核心类**：`DataFetcher`
  - `fetch_data(id_info, max_retries=2)` → 单平台抓取，内置指数退避重试
  - `crawl_websites(ids_list, request_interval=100)` → 批量抓取，请求间隔100ms
- **响应格式**：`{ "status": "success|cache", "items": [{ "title", "url", "mobileUrl" }] }`
- **数据结构**：按平台分组，每个标题追踪排名变化时间线
  ```python
  results[platform_id][title] = {
      "ranks": [index],           # 排名位置列表
      "url": str,                 # 链接
      "mobileUrl": str,           # 移动端链接
  }
  ```

### 增量检测 (core/data.py)

- `detect_latest_new_titles()`：对比最新批次标题与历史标题，识别新上榜内容
- `title_info[source_id][title]` 包含：`first_time`, `last_time`, `count`, `ranks`, `rank_timeline`
- **排名变化追踪**：记录每个标题在每次抓取中的排名位置，形成时间线

### AI分析器 (ai/analyzer.py)

- **数据类**：`AIAnalysisResult`，包含5个核心分析维度：
  - `core_trends`：核心热点与舆情态势
  - `sentiment_controversy`：舆论风向与争议
  - `signals`：异动与弱信号
  - `rss_insights`：RSS深度洞察
  - `outlook_strategy`：研判与策略建议
- **核心类**：`AIAnalyzer`
  - 使用 LiteLLM 统一接口（配置格式：`provider/model_name`）
  - Prompt模板变量：`{report_mode}`, `{report_type}`, `{current_time}`, `{news_count}`, `{platforms}`, `{keywords}` 等
- **JSON解析**：3阶段降级策略
  1. 标准 `json.loads()`
  2. `json_repair` 库修复
  3. LLM重试修复JSON

### 时间线调度 (config/timeline.yaml)

4种预设调度模式：
- `always_on`：全天监控，有新内容即推送，无AI分析
- `morning_evening`（推荐）：全天推送 + 晚间AI汇总（20:00-22:00，`daily`模式）
- `office_hours`：工作日3段（晨报09-11/午报13-15/晚报17-19），周末自由模式
- `night_owl`：午后简报15-17 + 深夜汇总22-01

时间段配置结构：
```yaml
periods:
  evening_summary:
    name: "晚间汇总"
    start: "20:00"
    end: "22:00"
    analyze: true
    ai_mode: "daily"         # daily | current | incremental
    report_mode: "daily"
    once:
      analyze: true
      push: true
```

### 通知推送

支持10+渠道：飞书、钉钉、企业微信、Telegram、Email、ntfy、Bark、Slack、通用Webhook

## 精华与糟粕

| 类别 | 内容 | 说明 |
|------|------|------|
| **精华** | NewsNow API统一聚合 | 一个API覆盖11+平台，零维护成本 |
| **精华** | 增量检测+排名时间线 | 精确追踪热点生命周期 |
| **精华** | LiteLLM多模型接口 | 100+模型统一调用，自带fallback |
| **精华** | 时间线调度系统 | 灵活可配置，覆盖多种使用场景 |
| **精华** | 3阶段JSON解析降级 | 健壮的LLM输出处理 |
| **糟粕** | 依赖第三方代理API | NewsNow API不可控，可能下线 |
| **糟粕** | 仅标题级数据 | 无评论/情感/深度内容 |
| **糟粕** | 无事件关联 | 各平台热搜独立展示，无跨平台事件合并 |
| **糟粕** | 无因果推理 | 只描述"发生了什么"，不分析"为什么" |
| **糟粕** | 单向信息流 | 采集→分析→推送，无反馈闭环 |

## 改进项

| 改进项 | 改进方式 |
|--------|----------|
| 事件关联 | 新增LLM事件聚类，跨平台合并同一事件 |
| 因果推理 | 新增因果链推理模块 |
| 信号强度评估 | 新增多维度信号强度评分 |
| 深度内容 | 结合BettaFish的MindSpider深度爬取 |
