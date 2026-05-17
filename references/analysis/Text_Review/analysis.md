# Text_Review 深度技术分析

> 基于源码分析 | https://github.com/jasonlbx13/Text_Review

---

## 1. 项目概述

- **GitHub地址**: https://github.com/jasonlbx13/Text_Review
- **Star数**: 少量（<50）
- **主要语言**: Python (100%)
- **License**: 未明确指定
- **一句话描述**: 基于敏感词匹配、fasttext语义分析和cherry文本分类三种策略的中文文本审核系统，支持多模型集成和Web API部署

### 1.1 项目背景

中文内容安全审核是一个复杂的多层次任务。单一方法（如敏感词匹配）无法应对所有场景：敏感词匹配速度快但无法理解语义，深度学习模型准确但计算成本高。Text_Review采用多模型集成策略，结合三种互补的审核方法，在保证准确性的同时控制成本。

### 1.2 核心功能

1. **敏感词匹配**: 约6万+敏感词库，支持多类别（政治/暴恐/色情/赌博等）
2. **fasttext语义分析**: 基于爬虫数据训练的涉政内容分类器
3. **cherry文本分类**: 基于cherry库的harmful内容分类
4. **Web API**: Flask实现的RESTful API，支持QPS限速和健康检查
5. **敏感词管理**: 支持增删改查操作

---

## 2. 整体架构

### 2.1 系统架构图

```
┌──────────────────────────────────────────────────────────────┐
│                    Text_Review System                         │
│                                                                │
│  ┌──────────────────── Web API Layer ──────────────────────┐  │
│  │  Flask App                                                  │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │  │
│  │  │ /ai        │ │ /areyouok  │ │ /metrics           │   │  │
│  │  │ 核心审核   │ │ 健康检查   │ │ Prometheus指标     │   │  │
│  │  │ 接口       │ │            │ │                    │   │  │
│  │  └─────┬──────┘ └────────────┘ └────────────────────┘   │  │
│  │        │                                                   │  │
│  │  ┌─────▼──────────────────────────────────────────────┐  │  │
│  │  │ AI Gate (ai_g7.py)                                  │  │  │
│  │  │ - 请求参数校验                                       │  │  │
│  │  │ - QPS限速 (Flask-Limiter)                           │  │  │
│  │  │ - 模型调度                                           │  │  │
│  │  │ - 结果聚合                                           │  │  │
│  │  └─────┬──────────────────────────────────────────────┘  │  │
│  └────────┼──────────────────────────────────────────────────┘  │
│           │                                                      │
│  ┌────────▼──────────── Model Integration Layer ──────────────┐  │
│  │                                                              │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │ BaseModelServer (hmai_base_aimodel.py)              │   │  │
│  │  │ - 过载保护 (self.ok标志 + 等待机制)                │   │  │
│  │  │ - 统一predict接口                                   │   │  │
│  │  │ - predict_mps多线程封装                             │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  │                          │                                   │  │
│  │        ┌─────────────────┼─────────────────┐               │  │
│  │        ▼                 ▼                 ▼               │  │
│  │  ┌──────────┐     ┌──────────┐     ┌──────────────┐       │  │
│  │  │ keyword  │     │ fnlp     │     │ cherry       │       │  │
│  │  │ 关键词   │     │ fasttext │     │ 文本分类     │       │  │
│  │  │ 匹配     │     │ 语义分析 │     │              │       │  │
│  │  └──────────┘     └──────────┘     └──────────────┘       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌──────────────────── Support Layer ────────────────────────┐  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │ ailog.py   │  │ config.py  │  │ langconv.py        │  │  │
│  │  │ 分级日志   │  │ 配置管理   │  │ 繁简体转换         │  │  │
│  │  └────────────┘  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块划分

| 模块 | 文件 | 职责 |
|------|------|------|
| AI Gate | ai_g7.py | Web API入口，请求路由，模型调度 |
| BaseModel | hmai_base_aimodel.py | 模型基类，过载保护 |
| Keyword Model | aimodel_kw.py | 敏感词匹配模型 |
| FNLP Model | aimodel_fnlp.py | fasttext语义分类模型 |
| Cherry Model | aimodel_cherry.py | cherry文本分类模型 |
| Log System | ailog.py | 分级日志系统 |
| Config | tools/config.py | 配置管理 |

---

## 3. 三种审核模型详解

### 3.1 关键词匹配模型 (aimodel_kw)

**原理**: 基于预定义敏感词字典的精确匹配

**实现流程**:
```
输入文本 → 繁体转简体 → jieba分词 → 停用词过滤 → 字典匹配 → 输出结果
```

**核心代码**:
```python
def juge(self, text):
    weigui_word = []
    weigui_kind = []
    for word in text:
        if word in self.mingan_dict:
            weigui_word.append(word)
            weigui_kind.append(self.mingan_dict[word])
    return weigui_word, weigui_kind
```

**敏感词库管理**:
```python
def increase(self, word, kind_num):  # 新增敏感词
    self.mingan_dict[word] = kind
    with open('ai/{}/fenlei_mingan'.format(self.title), 'wb') as f:
        pickle.dump(self.mingan_dict, f)
    self.jieba_buchong()  # 更新jieba词典

def delete(self, word):  # 删除敏感词
    self.mingan_dict.pop(word)
    # 重新持久化...

def change(self, word, kind_num):  # 修改类别
    self.mingan_dict[word] = kind
    # 重新持久化...
```

**特点**:
- 速度极快（字典查找O(1)）
- 可解释性强（精确匹配到哪个词）
- 无法处理变体、谐音、拆字等
- 需要持续维护词库

### 3.2 fasttext语义分析模型 (aimodel_fnlp)

**原理**: 基于fasttext的文本分类，理解语义而非字面匹配

**训练数据**:
- 正样本：贴吧正常内容
- 负样本：境外反动网站爬取内容

**实现流程**:
```
输入文本 → 繁体转简体 → jieba分词 → 停用词过滤 →
拼接为空格分隔字符串 → fasttext.predict() → 输出类别
```

**核心代码**:
```python
def fasttest_juge(self, text):
    res = [' '.join(text)]  # fasttext需要空格分隔的输入
    labels = self.ft_model.predict(res)
    return labels[0][0], self.kind_book[int(labels[0][0])-1]

def predict(self, text_data, title, ...):
    text_data = self.fan2jian(text_data)  # 繁体→简体
    par_words = self.participle_fnlp(text_data, add_var_1)
    cate_num, cate_label = self.fasttest_juge(par_words)
    if cate_label == "normal":
        dic['code'] = '0'  # 正常
    else:
        dic['code'] = '1'  # 违规
```

**分类标签**:
- `normal`: 正常内容
- `normal_politics`: 正常涉政内容
- `violation_politics`: 违规涉政内容

**特点**:
- 能理解语义，处理变体和谐音
- 模型体积小，推理速度快
- 训练数据质量直接影响效果
- 对新型违规内容反应滞后

### 3.3 cherry文本分类模型 (aimodel_cherry)

**原理**: 使用cherry库的预训练harmful内容分类模型

**实现流程**:
```python
def predict(self, text_data, title, ...):
    text_data = self.fan2jian(text_data)  # 繁体→简体
    cate_label = self.kind_book[
        np.argmax(cherry.classify(model='harmful', text=[text_data]).probability[0])
    ]
    if cate_label == "normal":
        dic['code'] = '0'
    else:
        dic['code'] = '1'
```

**特点**:
- 使用预训练模型，无需自己训练
- cherry库内置多类别分类
- 依赖第三方库的质量
- 不支持自定义训练

---

## 4. 文本预处理管线

### 4.1 繁简体转换

```python
from langconv import Converter

def fan2jian(self, text):
    line = Converter('zh-hans').convert(text)
    line.encode('utf-8')
    return line
```

使用 `langconv` 库将繁体中文转换为简体中文，确保后续处理的一致性。

### 4.2 jieba分词

```python
self.jieba_kw = jieba.Tokenizer(dictionary="ai/keyword/jieba_kwdict.txt")

def participle_kw(self, text, add_var_1=0):
    if add_var_1 == 1:
        segs = re.sub(r'\.|#|，|/|,|。|!|:|《|》|-|\?', '', text)
    else:
        segs = text
    segs = self.jieba_kw.lcut(segs)  # 精确模式分词
    segs = list(filter(lambda x: len(x) > 0, segs))
    if add_var_1 == 2:
        segs = list(filter(lambda x: x not in self.stopwords, segs))
    segs = list(filter(lambda x: x != ' ', segs))
    return segs
```

**关键设计**:
- 使用自定义词典（`jieba_kwdict.txt`），包含敏感词以提高分词准确性
- 支持三种模式：默认、去标点、去停用词
- 过滤空字符串和空格

### 4.3 停用词过滤

```python
self.stopwords = pd.read_csv("ai/{}/stopwords.txt".format(title), 
    index_col=False, quoting=3, sep="\t", names=['stopword'], encoding='utf-8').values
```

---

## 5. 过载保护机制

BaseModelServer实现了一个简单的过载保护：

```python
def predict(self, image_data, title, ...):
    i = 0
    while self.ok == False:  # 如果模型正在被使用
        i += 1
        if i < self.overload_par['wait_num_1']:
            time.sleep(self.overload_par['wait_time_1'])  # 第一阶段等待
        elif i < (self.overload_par['wait_num_2'] + self.overload_par['wait_num_1']):
            time.sleep(self.overload_par['wait_time_2'])  # 第二阶段等待
        else:
            dic['error'] = 'overload'  # 超时返回过载错误
            return dic
    
    self.ok = False  # 占用模型
    try:
        # 执行预测...
    finally:
        self.ok = True  # 释放模型
```

**设计思路**:
- 使用 `self.ok` 布尔标志实现互斥锁
- 两级等待策略：先短时间等待，再长时间等待
- 超时后返回过载错误，而不是无限等待

---

## 6. Web API设计

### 6.1 Flask路由

```python
@app.route('/ai', methods=['POST'])
@limiter.limit("{}/second".format(self.my_s_limiter))
@limiter.limit("{}/5seconds".format(self.my_5s_limiter))
def get_tasks():
    # 核心审核接口
```

**API参数**:
- `textdata`: 待审核文本
- `ais`: 指定使用的模型（ALL_GROUP表示全部）
- `aigroup`: 模型组名
- `add_var_1/2/3`: 附加参数
- `fr`: fpr优先(f)或recall优先(r)
- `debug`: 是否返回调试信息

### 6.2 QPS限速

```python
limiter = Limiter(
    app,
    key_func=self.get_myrequest,
    default_limits=["{}/second".format(self.my_s_limiter), 
                    "{}/5seconds".format(self.my_5s_limiter)]
)
```

使用 `Flask-Limiter` 实现基于模型组的QPS限速，支持每秒和每5秒两个维度。

### 6.3 健康检查

```python
@app.route('/areyouok')
def areyouok():
    dic = health()  # 用测试文本跑一遍所有模型
    return 'health:{}, speed:{}s/per_dectection\n'.format(dic['health'], dic['speed'])
```

健康检查会用测试文本实际调用所有模型，确保模型正常工作。

### 6.4 Prometheus Metrics

```python
@app.route('/metrics')
def metrics():
    # 返回Prometheus格式的监控指标
    # - ai_health: 健康状态
    # - request_access_ai_total: 总请求数
    # - request_overload_ratio: 过载率
    # - 各模型的overload次数
```

---

## 7. 日志系统设计

AILog实现了一个分级日志系统：

```python
class AILog:
    handlers = {
        logging.NOTSET: "./log/ai-notset.log",
        logging.DEBUG: "./log/ai-debug.log",
        logging.INFO: "./log/ai-info.log",
        logging.WARNING: "./log/ai-warning.log",
        logging.ERROR: "./log/ai-error.log",
        logging.CRITICAL: "./log/ai-critical.log"
    }
    
    def info(self, message):
        message = self.getLogMessage("info", message)
        self.__loggers[logging.INFO].info(message)
```

**特性**:
- 按级别分文件存储
- 每小时轮转（TimedRotatingFileHandler）
- 保留120个备份文件
- 日志格式：`[时间] [类型] [文件名 - 行号] 信息`

---

## 8. 与VibeUtopia项目的关联与借鉴

### 8.1 多策略融合审核

Text_Review的多模型集成策略（关键词+语义+分类）是内容审核的最佳实践：

| Text_Review策略 | VibeUtopia应用 |
|----------------|---------------|
| 敏感词精确匹配 | 基础风控层（快速过滤） |
| fasttext语义分析 | 语义理解层 |
| cherry预训练分类 | 通用分类层 |
| 多模型集成 | 多层审核管线 |

### 8.2 过载保护设计

简单的布尔锁+超时机制可以借鉴到VibeUtopia的Agent资源管理中：
- 限制同时处理的请求数
- 超时返回降级响应
- 防止系统过载崩溃

### 8.3 敏感词管理系统

完整的增删改查+持久化方案可以直接用于VibeUtopia的内容安全模块：
- 分类管理（政治/色情/暴力等）
- jieba词典同步更新
- pickle持久化

### 8.4 繁简体转换

langconv的繁简体转换可以集成到VibeUtopia的文本预处理管线中，确保多来源内容的一致性。

---

## 9. 精华与糟粕

### 9.1 精华

1. **多策略融合**: 三种互补的方法覆盖了不同层面的审核需求
2. **工程化部署**: Flask + 限速 + 健康检查 + 监控，可直接部署
3. **过载保护**: 简单的互斥锁+超时机制，实用有效
4. **敏感词管理**: 完整的CRUD操作，支持动态更新
5. **分级日志**: 按级别分文件，便于问题定位

### 9.2 糟粕

1. **单线程模型**: 过载保护使用简单的布尔锁，无法并发处理
2. **fasttext已过时**: fasttext分类器已被BERT等模型大幅超越
3. **cherry库依赖**: cherry库的维护和更新不确定
4. **无模型热更新**: 更新模型需要重启服务
5. **配置管理简单**: 使用configparser，不支持热加载
6. **无分布式设计**: 单机部署，无法水平扩展

### 9.3 改进方向

1. **异步架构**: 使用FastAPI + asyncio替代Flask
2. **模型升级**: 用BERT/RoBERTa替代fasttext
3. **模型热更新**: 支持不重启服务更新模型
4. **分布式部署**: 支持多实例负载均衡
5. **审核结果缓存**: 对重复文本直接返回缓存结果
6. **A/B测试**: 支持灰度发布新模型

---

## 10. 总结

Text_Review是一个实用的中文文本审核系统，其最大价值在于**多模型集成的审核策略**和**完整的工程化部署方案**。虽然使用的技术栈相对传统（fasttext、Flask），但其系统设计思路（多策略融合、过载保护、监控）仍然有参考价值。

**关键指标**:
- 敏感词库: ~6万+词条
- 审核策略: 3种（关键词+fasttext+cherry）
- API: Flask RESTful API
- QPS控制: 可配置（秒级+5秒级）
- 日志: 6个级别，按小时轮转

对于VibeUtopia，Text_Review的核心借鉴价值在于其**多层审核管线设计**和**工程化部署经验**，但具体实现应使用更现代的技术栈。
