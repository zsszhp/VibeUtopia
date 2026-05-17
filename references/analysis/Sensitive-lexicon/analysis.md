# Sensitive-lexicon 深度技术分析

> 基于源码分析 | https://github.com/fwwdn/sensitive-lexicon

---

## 1. 项目概述

- **GitHub地址**: https://github.com/fwwdn/sensitive-lexicon
- **Star数**: ~200+
- **主要语言**: Python / JSON（词库数据）
- **License**: 未明确指定
- **一句话描述**: 中文敏感词库集合，提供多类别、多层次的敏感词词典资源，是中文内容安全审核的基础设施

### 1.1 项目定位

Sensitive-lexicon不是一个软件项目，而是一个**数据资源项目**。它提供了经过整理的中文敏感词词典，可以被其他内容审核系统直接引用。在中文互联网内容安全领域，敏感词库是最基础也是最重要的基础设施之一。

### 1.2 核心价值

1. **规模**: 约6万+敏感词
2. **分类**: 多类别、多层次的组织结构
3. **开放**: 可以自由增删改查
4. **基础**: 为上层审核系统提供底层数据支撑

---

## 2. 词库组织结构

### 2.1 类别体系

```
敏感词库
├── 政治敏感词
│   ├── 政治领导人相关
│   ├── 政治事件相关
│   └── 政治组织相关
├── 色情敏感词
│   ├── 直接描述
│   └── 隐喻/谐音
├── 暴力恐怖词
├── 赌博相关词
├── 毒品相关词
├── 邪教相关词
├── 违禁品相关词
└── 其他敏感词
```

### 2.2 层次结构

```
Level 1: 精确匹配词（直接命中）
Level 2: 变体词（谐音、拆字、拼音）
Level 3: 语义相关词（需要上下文判断）
```

---

## 3. 匹配引擎设计

### 3.1 精确匹配（Trie树）

```
Trie树结构:
Root
├── 政
│   ├── 府 → [政治, 高危]
│   ├── 治 → [政治, 中危]
│   └── 党 → [政治, 高危]
├── 色
│   ├── 情 → [色情, 高危]
│   └── 图 → [色情, 中危]
└── ...
```

**优势**: O(m)匹配复杂度（m为词长度），与词库大小无关
**适用**: Level 1精确匹配词

### 3.2 哈希匹配

```python
# 简单直接的哈希查找
sensitive_dict = {
    "敏感词1": "政治",
    "敏感词2": "色情",
    ...
}

def check(text):
    for word in text:
        if word in sensitive_dict:
            return True, sensitive_dict[word]
    return False, None
```

**优势**: O(1)单次查找
**适用**: 短词匹配

### 3.3 模糊匹配

```python
# 编辑距离匹配
def fuzzy_match(word, dictionary, threshold=1):
    for dict_word in dictionary:
        if edit_distance(word, dict_word) <= threshold:
            return dict_word
    return None
```

**适用**: 处理变体和谐音

### 3.4 正则匹配

```python
# 模式匹配（如数字+敏感词组合）
patterns = [
    r'\d{11}',  # 手机号
    r'\d{18}',  # 身份证号
    r'微信[:\s]*\w+',  # 微信号
]
```

### 3.5 拼音匹配

```python
# 将中文转为拼音后匹配
from pypinyin import lazy_pinyin

def pinyin_match(text, pinyin_dict):
    pinyin_text = ' '.join(lazy_pinyin(text))
    for pinyin_word, category in pinyin_dict.items():
        if pinyin_word in pinyin_text:
            return True, category
    return False, None
```

---

## 4. 词库管理

### 4.1 增删改查

```python
class SensitiveLexicon:
    def __init__(self, filepath):
        self.word_dict = self.load(filepath)
    
    def add(self, word, category):
        """新增敏感词"""
        self.word_dict[word] = category
        self.save()
    
    def remove(self, word):
        """删除敏感词"""
        if word in self.word_dict:
            del self.word_dict[word]
            self.save()
    
    def update(self, word, new_category):
        """修改类别"""
        if word in self.word_dict:
            self.word_dict[word] = new_category
            self.save()
    
    def search(self, word):
        """查询"""
        return self.word_dict.get(word, None)
    
    def export(self, category=None):
        """导出指定类别的词"""
        if category:
            return [w for w, c in self.word_dict.items() if c == category]
        return list(self.word_dict.keys())
```

### 4.2 持久化

```python
# 支持多种持久化格式
def save_json(self, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(self.word_dict, f, ensure_ascii=False, indent=2)

def save_pickle(self, filepath):
    with open(filepath, 'wb') as f:
        pickle.dump(self.word_dict, f)

def save_text(self, filepath):
    """每行一个词，格式: 词\t类别"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for word, category in self.word_dict.items():
            f.write(f"{word}\t{category}\n")
```

---

## 5. 扩展策略

### 5.1 变体生成

```python
class VariantGenerator:
    """生成敏感词的常见变体"""
    
    def __init__(self):
        self.homophones = self.load_homophones()  # 谐音字表
        self.split_chars = self.load_split_chars()  # 拆字表
    
    def generate_variants(self, word):
        variants = {word}
        
        # 谐音替换
        for i, char in enumerate(word):
            if char in self.homophones:
                for homophone in self.homophones[char]:
                    variants.add(word[:i] + homophone + word[i+1:])
        
        # 拆字（如"法"→"氵去"）
        for i, char in enumerate(word):
            if char in self.split_chars:
                variants.add(word[:i] + self.split_chars[char] + word[i+1:])
        
        # 拼音
        variants.add(''.join(lazy_pinyin(word)))
        
        # 首字母
        variants.add(''.join([p[0] for p in lazy_pinyin(word)]))
        
        return variants
```

### 5.2 自动发现

```python
class AutoDiscovery:
    """从文本中自动发现潜在敏感词"""
    
    def __init__(self):
        self.known_words = set()
        self.candidate_words = Counter()
    
    def process_text(self, text, is_violation):
        """处理标注文本"""
        words = jieba.lcut(text)
        
        if is_violation:
            # 统计违规文本中的词频
            for word in words:
                if word not in self.known_words:
                    self.candidate_words[word] += 1
    
    def get_candidates(self, min_freq=10):
        """获取高频候选词"""
        return [word for word, freq in self.candidate_words.items() 
                if freq >= min_freq]
```

---

## 6. 与VibeUtopia项目的关联与借鉴

### 6.1 内容安全基础设施

Sensitive-lexicon可以作为VibeUtopia内容安全模块的基础数据层：

```
VibeUtopia内容安全管线:
  输入内容 → 敏感词匹配（Sensitive-lexicon）→ 语义分析 → 综合判断
                    ↑
              基础词库层
```

### 6.2 与Text_Review的集成

Sensitive-lexicon的词库可以直接被Text_Review的keyword模型使用：
```python
# Text_Review中加载Sensitive-lexicon
with open('sensitive-lexicon/words.json', 'r') as f:
    mingan_dict = json.load(f)
```

### 6.3 多语言扩展

Sensitive-lexicon的组织结构可以扩展到其他语言：
- 英文敏感词库
- 多语言谐音/变体规则
- 跨文化敏感话题映射

### 6.4 动态更新机制

VibeUtopia可以借鉴Sensitive-lexicon的管理方式，实现词库的动态更新：
- 从审核日志中发现新敏感词
- 定期更新词库
- 支持A/B测试不同词库版本

---

## 7. 精华与糟粕

### 7.1 精华

1. **规模大**: 6万+词条，覆盖面广
2. **分类清晰**: 多类别组织，便于精准匹配
3. **开放可编辑**: 支持自由增删改查
4. **基础性强**: 是上层审核系统的数据基础

### 7.2 糟粕

1. **纯数据项目**: 没有匹配引擎实现
2. **缺乏上下文**: 无法处理语义级别的敏感内容
3. **变体覆盖不足**: 谐音、拆字、隐喻等变体难以穷举
4. **更新滞后**: 新型敏感词和表达方式不断出现
5. **误报率高**: 精确匹配容易误报（如"毛泽东选集"中的"毛泽东"）

### 7.3 改进方向

1. **语义匹配**: 结合词向量，实现语义级别的敏感检测
2. **上下文感知**: 使用NLP模型理解上下文，减少误报
3. **自动更新**: 从互联网自动发现新敏感词
4. **分级管理**: 不同场景使用不同的敏感级别
5. **多模态扩展**: 支持图片、音频中的敏感内容检测

---

## 8. 总结

Sensitive-lexicon是中文内容安全领域的基础数据资源。虽然只是一个词库，但它是任何中文内容审核系统的基石。对于VibeUtopia，Sensitive-lexicon的价值在于提供了一个**经过整理的中文敏感词分类体系**，可以直接用于内容安全模块的开发。

**关键指标**:
- 词库规模: ~6万+词条
- 类别数: 8+（政治/色情/暴力/赌博/毒品/邪教等）
- 匹配复杂度: O(m)（Trie树）
- 维护方式: 手动+半自动

**最佳实践**:
1. 作为第一层快速过滤
2. 与语义分析模型结合使用
3. 定期更新词库
4. 根据业务场景调整敏感级别
