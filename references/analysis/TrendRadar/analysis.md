# TrendRadar 深度技术分析

> 基于源码分析

---

## 1. 项目概述

- **Star数**: 少量
- **主要语言**: Python
- **License**: 未明确
- **一句话描述**: 多平台热点监控系统，覆盖11个中文热榜平台和RSS源，实现热点聚合、趋势分析和报告生成

### 1.1 核心价值

在信息爆炸时代，快速捕捉各平台热点是内容创作和舆情监控的关键能力。TrendRadar提供了一个统一的框架，从多个平台采集热点数据，进行聚合分析，生成可操作的洞察。

---

## 2. 数据源配置

### 2.1 热榜平台（11个）

```yaml
platforms:
  enabled: true
  sources:
    - id: "toutiao"              # 今日头条 - 综合新闻
    - id: "baidu"                # 百度热搜 - 搜索热度
    - id: "wallstreetcn-hot"     # 华尔街见闻 - 财经
    - id: "thepaper"             # 澎湃新闻 - 深度报道
    - id: "bilibili-hot-search"  # B站热搜 - 年轻用户
    - id: "cls-hot"              # 财联社 - 实时财经
    - id: "ifeng"                # 凤凰网 - 综合
    - id: "tieba"                # 贴吧 - 社区讨论
    - id: "weibo"                # 微博 - 社交媒体
    - id: "douyin"               # 抖音 - 短视频
    - id: "zhihu"                # 知乎 - 知识社区
```

### 2.2 平台分类

| 类别 | 平台 | 特点 |
|------|------|------|
| 综合新闻 | 今日头条、澎湃、凤凰 | 覆盖面广，时效性强 |
| 社交媒体 | 微博、贴吧、抖音 | 用户生成内容，情绪化 |
| 知识社区 | 知乎 | 深度讨论，专业性强 |
| 财经 | 华尔街见闻、财联社 | 专业投资者关注 |
| 年轻用户 | B站 | Z世代文化 |
| 搜索引擎 | 百度 | 反映搜索意图 |

### 2.3 RSS源

```yaml
rss:
  freshness_filter:
    enabled: true
    max_age_days: 1  # 只保留24小时内的内容
```

---

## 3. 数据采集策略

### 3.1 爬虫设计

每个平台需要独立的爬虫适配器：

```python
class BaseScraper:
    """爬虫基类"""
    
    def __init__(self, platform_id, config):
        self.platform_id = platform_id
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 ...',
            'Accept': 'text/html,application/json'
        })
    
    async def fetch(self):
        """获取热榜数据"""
        raise NotImplementedError
    
    async def parse(self, raw_data):
        """解析为统一格式"""
        raise NotImplementedError


class WeiboScraper(BaseScraper):
    """微博热榜爬虫"""
    
    async def fetch(self):
        url = "https://weibo.com/ajax/side/hotSearch"
        response = await self.session.get(url)
        return response.json()
    
    async def parse(self, raw_data):
        items = []
        for item in raw_data['data']['realtime']:
            items.append({
                'title': item['note'],
                'hot_value': item.get('num', 0),
                'rank': item.get('rank', 0),
                'category': item.get('category', ''),
                'timestamp': datetime.now()
            })
        return items
```

### 3.2 反爬策略

```python
class AntiDetection:
    """反爬虫检测规避"""
    
    def __init__(self):
        self.proxy_pool = ProxyPool()
        self.user_agents = self.load_user_agents()
    
    def get_proxy(self):
        """获取随机代理"""
        return self.proxy_pool.get_random()
    
    def get_headers(self):
        """获取随机请求头"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Referer': self.get_random_referer(),
            'Accept-Language': 'zh-CN,zh;q=0.9'
        }
    
    async def adaptive_delay(self, platform):
        """自适应请求间隔"""
        base_delay = self.config.get(platform, {}).get('delay', 1.0)
        jitter = random.uniform(0, base_delay * 0.5)
        await asyncio.sleep(base_delay + jitter)
```

---

## 4. 热点聚合算法

### 4.1 去重与归一化

```python
class HotTopicAggregator:
    """热点聚合器"""
    
    def __init__(self):
        self.seen_topics = {}  # 已见话题
        self.similarity_threshold = 0.8
    
    def normalize_title(self, title):
        """标题归一化"""
        # 去除标点和特殊字符
        title = re.sub(r'[【】\[\]{}（）]', '', title)
        # 统一全角半角
        title = unicodedata.normalize('NFKC', title)
        # 转小写
        title = title.lower().strip()
        return title
    
    def compute_similarity(self, title1, title2):
        """计算标题相似度"""
        # Jaccard相似度（基于字符级2-gram）
        set1 = set(self.ngrams(title1, 2))
        set2 = set(self.ngrams(title2, 2))
        if not set1 or not set2:
            return 0.0
        return len(set1 & set2) / len(set1 | set2)
    
    def aggregate(self, all_platform_data):
        """聚合所有平台的热点"""
        merged = []
        
        for platform, topics in all_platform_data.items():
            for topic in topics:
                normalized = self.normalize_title(topic['title'])
                
                # 检查是否已存在相似话题
                found = False
                for existing in merged:
                    if self.compute_similarity(normalized, existing['normalized_title']) > self.similarity_threshold:
                        # 合并：添加平台来源，累加热度
                        existing['platforms'].append(platform)
                        existing['hot_value'] += topic.get('hot_value', 0)
                        found = True
                        break
                
                if not found:
                    merged.append({
                        'title': topic['title'],
                        'normalized_title': normalized,
                        'platforms': [platform],
                        'hot_value': topic.get('hot_value', 0),
                        'first_seen': topic.get('timestamp', datetime.now())
                    })
        
        # 按热度排序
        merged.sort(key=lambda x: x['hot_value'], reverse=True)
        return merged
```

### 4.2 趋势分析

```python
class TrendAnalyzer:
    """趋势分析器"""
    
    def detect_emerging(self, current_data, historical_data):
        """检测新兴热点"""
        emerging = []
        
        for topic in current_data:
            title = topic['normalized_title']
            
            # 查找历史数据
            history = historical_data.get(title, [])
            
            if len(history) < 2:
                # 首次出现 → 新兴热点
                topic['trend'] = 'emerging'
                emerging.append(topic)
            else:
                # 计算热度变化率
                prev_hot = history[-1]['hot_value']
                curr_hot = topic['hot_value']
                
                if prev_hot > 0:
                    change_rate = (curr_hot - prev_hot) / prev_hot
                    
                    if change_rate > 0.5:
                        topic['trend'] = 'surging'      # 爆发
                    elif change_rate > 0.1:
                        topic['trend'] = 'rising'       # 上升
                    elif change_rate > -0.1:
                        topic['trend'] = 'stable'       # 稳定
                    else:
                        topic['trend'] = 'declining'    # 下降
                
                emerging.append(topic)
        
        return emerging
    
    def detect_patterns(self, time_series_data):
        """检测时间模式"""
        patterns = {
            'daily_peak': self.find_daily_peak(time_series_data),
            'weekly_pattern': self.find_weekly_pattern(time_series_data),
            'burst_events': self.find_burst_events(time_series_data)
        }
        return patterns
```

---

## 5. 报告生成

### 5.1 报告模板

```python
class ReportGenerator:
    """报告生成器"""
    
    def generate_daily_report(self, aggregated_data):
        """生成每日热点报告"""
        
        report = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'summary': self.generate_summary(aggregated_data),
            'top_topics': self.get_top_topics(aggregated_data, n=20),
            'platform_breakdown': self.get_platform_stats(aggregated_data),
            'trending': self.get_trending(aggregated_data),
            'emerging': self.get_emerging(aggregated_data),
            'category_distribution': self.get_category_stats(aggregated_data)
        }
        
        return report
    
    def generate_summary(self, data):
        """生成摘要"""
        total_topics = len(data)
        cross_platform = len([t for t in data if len(t['platforms']) > 1])
        
        return f"""
        今日共监控 {len(PLATFORMS)} 个平台，发现 {total_topics} 个热点话题。
        其中 {cross_platform} 个话题跨平台传播。
        热度最高的话题: {data[0]['title'] if data else 'N/A'}
        """
```

---

## 6. 与VibeUtopia项目的关联与借鉴

### 6.1 舆情监控

TrendRadar的多平台数据采集和聚合能力可以直接用于VibeUtopia的舆情监控模块：

| TrendRadar功能 | VibeUtopia应用 |
|---------------|---------------|
| 多平台热榜采集 | Agent发现热门话题 |
| 热点聚合去重 | 去重后的统一话题流 |
| 趋势分析 | 预测话题走向 |
| 报告生成 | 自动生成舆情报告 |

### 6.2 内容创作辅助

热点数据可以驱动VibeUtopia的内容创作Agent：
- 发现热门话题 → 生成相关内容
- 趋势分析 → 预测下一个热点
- 多平台数据 → 了解不同平台的用户偏好

### 6.3 Agent行为驱动

Agent可以根据热点数据调整行为：
- 热点话题 → Agent更积极地参与讨论
- 趋势上升 → Agent提前布局相关内容
- 跨平台传播 → Agent在多个平台同步发声

---

## 7. 精华与糟粕

### 7.1 精华

1. **覆盖面广**: 11个主流平台
2. **统一框架**: 标准化的数据采集和处理流程
3. **趋势分析**: 不仅采集，还分析趋势
4. **RSS支持**: 支持标准RSS源扩展

### 7.2 糟粕

1. **爬虫脆弱**: 各平台反爬策略变化频繁
2. **数据质量**: 不同平台的数据格式和质量差异大
3. **实时性**: 批量采集，非实时
4. **深度不足**: 只采集热榜，不采集评论和互动数据

### 7.3 改进方向

1. **API优先**: 优先使用官方API而非爬虫
2. **实时流**: 使用WebSocket等实时数据源
3. **深度采集**: 采集评论、转发等互动数据
4. **情感分析**: 对热点话题进行情感分析
5. **预测模型**: 使用ML模型预测热点走向

---

## 8. 总结

TrendRadar是一个实用的多平台热点监控框架。其核心价值在于**统一的多平台数据采集和聚合能力**。对于VibeUtopia，TrendRadar的借鉴价值在于其**数据采集策略**和**热点聚合算法**。

**关键指标**:
- 覆盖平台: 11个
- 数据源类型: 热榜 + RSS
- 聚合算法: Jaccard相似度 + 2-gram
- 趋势检测: 热度变化率
