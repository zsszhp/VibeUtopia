# BettaFish 深度分析

## 关键实现细节

### 4专职Agent架构

| Agent | 角色 | 工具集 | 数据源 |
|-------|------|--------|--------|
| **InsightEngine** | 私域数据挖掘 | MediaCrawlerDB(5个工具: search_hot_content, search_topic_globally, search_topic_by_date, get_comments_for_topic, search_topic_on_platform) + keyword_optimizer + multilingual_sentiment_analyzer | PostgreSQL/MySQL |
| **MediaEngine** | 多模态内容分析 | video_search + image_search + multimodal_understanding | 抖音/快手 |
| **QueryEngine** | 精准信息搜索 | web_search(国内+国际) | 互联网 |
| **ReportEngine** | 报告生成 | template_selector + layout_designer + chapter_generator | 其他3个Agent输出 |

**统一节点流水线**（所有分析Agent共享）：
```
ReportStructureNode → FirstSearchNode → FirstSummaryNode → ReflectionNode → ReflectionSummaryNode → ReportFormattingNode
```

- `ReportStructureNode`：生成报告大纲
- `FirstSearchNode`：生成搜索查询 + 选择工具
- `FirstSummaryNode`：生成初始段落摘要（触发ForumEngine新会话）
- `ReflectionNode`：基于论坛反馈生成反思搜索查询
- `ReflectionSummaryNode`：更新摘要（写入ForumEngine）
- `ReportFormattingNode`：格式化最终报告

### ForumEngine协作机制

**LogMonitor** (ForumEngine/monitor.py)：
```python
class LogMonitor:
    def __init__(self, log_dir="logs"):
        self.monitored_logs = {'insight': ..., 'media': ..., 'query': ...}
        self.agent_speeches_buffer: List[str] = []
        self.host_speech_threshold: int = 5  # 每5条Agent发言触发Host
        self.is_host_generating: bool = False

    def monitor_logs(self)         # 主轮询循环，1秒间隔
    def write_to_forum_log(content, source)  # 写入forum.log
    def _trigger_host_speech()     # 触发ForumHost生成主持发言
```

**ForumHost** (ForumEngine/llm_host.py)：
```python
class ForumHost:
    def __init__(self, api_key, base_url, model_name):
        # 使用Qwen3-235B作为主持模型
        self.client = OpenAI(api_key=..., base_url=...)

    def generate_host_speech(forum_logs: List[str]) -> Optional[str]
    def _parse_forum_logs(forum_logs) -> Dict  # 解析Agent发言
    def _build_system_prompt() -> str           # 4段式主持Prompt
    def _build_user_prompt(parsed_content) -> str
    def _call_qwen_api(system_prompt, user_prompt)  # temperature=0.6, top_p=0.9
```

**ForumHost Prompt结构**：
1. 事件时间线分析
2. 跨Agent视角对比（含事实核查）
3. 深度分析与趋势预测
4. 讨论方向引导（2-3个关键问题）

**协作流程**：
1. `FirstSummaryNode`输出 → LogMonitor捕获 → 写入forum.log（标记`[INSIGHT]`/`[MEDIA]`/`[QUERY]`）
2. 累积5条发言 → 触发ForumHost → 生成主持发言 → 写入forum.log（标记`[HOST]`）
3. Agent通过`forum_reader`工具读取论坛内容 → 调整研究方向
4. 论坛会话在日志缩减或7200次无活动迭代后结束

### MindSpider两阶段爬取

**阶段1：广度关键词提取**
- 获取今日新闻 → LLM提取关键词 → 生成搜索词列表

**阶段2：深度情感爬取**
- 使用搜索词 → Playwright（无头Chromium）爬取各平台评论
- 支持平台：小红书/抖音/微博/B站/知乎
- 情感标注：对每条评论进行正/负/中性+情感强度标注

### 情感分析模型

多种模型可选：
- BERT Chinese LoRA微调模型
- GPT-2 LoRA微调模型
- 多语言情感分析模型
- Qwen3小参数微调模型
- 传统ML方法（SVM等）

### 报告生成

ReportEngine流程：
1. 收集所有Agent结果 + 论坛内容
2. 生成IR（中间表示）
3. 渲染为交互式HTML

## 精华与糟粕

| 类别 | 内容 | 说明 |
|------|------|------|
| **精华** | ForumEngine协作思想 | Agent异步交流，Host主持引导，避免无序讨论 |
| **精华** | 专职Agent分工 | 每个Agent有独立工具集和LLM配置 |
| **精华** | 两阶段爬取策略 | 先广度提取关键词，再深度爬取情感数据 |
| **精华** | 反思-总结循环 | Agent基于论坛反馈调整研究方向 |
| **精华** | 多模型情感分析 | 覆盖不同场景的情感分析需求 |
| **糟粕** | 日志文件通信 | 文件I/O效率低，不适合大规模仿真 |
| **糟粕** | 固定4个Agent | 无法扩展到千级规模 |
| **糟粕** | 串行报告生成 | ReportEngine是瓶颈 |
| **糟粕** | Playwright爬虫重且慢 | 维护成本高，反爬困难 |
| **糟粕** | 论坛阈值固定 | 每5条触发Host，不够灵活 |

## 改进项

| 改进项 | 改进方式 |
|--------|----------|
| 文件通信→消息传递 | asyncio.Queue替代日志文件 |
| 固定4Agent→四层架构 | A/B/C/Group分层调度策略 |
| Playwright→API优先 | 优先使用平台API，降级到Playwright |
| 串行报告→流式 | 分析结果实时推送，非等待全部完成 |
