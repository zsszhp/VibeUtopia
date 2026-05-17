"""平台权重体系 - 阶段2: 平台深度打磨

定义5大核心平台(P0)的权重配置、传播特征、用户画像特征。
不同平台的评估结果按权重影响总风险分。

平台分级:
- P0(权重1.0): 微博、B站、小红书、抖音、知乎 — 核心平台，影响占比≥70%
- P1(权重0.7): 快手、贴吧、豆瓣、微信视频号、Twitter/X、Facebook、Instagram、YouTube、Telegram、Reddit — 次核心平台
- P2(权重0.4): TikTok国际版、LinkedIn、NGA、V2EX、脉脉、Boss直聘、什么值得买、知乎专栏、即刻 — 其他长尾平台
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlatformProfile:
    """平台画像配置"""
    platform_id: str                  # 平台标识
    name: str                         # 平台名称
    tier: str                         # 平台分级 P0/P1/P2
    weight: float                     # 平台权重 (P0=1.0, P1=0.7, P2=0.4)

    # 传播特征
    propagation_speed: str            # 传播速度: 极快/快/中等/慢
    amplification_factor: float       # 放大系数 (争议内容传播倍数)
    echo_chamber_strength: float      # 信息茧房强度 0-1
    polarization_tendency: float      # 极化倾向 0-1

    # 用户特征
    user_base_size: str              # 用户规模描述
    active_age_range: tuple           # 活跃年龄段
    gender_ratio: float              # 女性占比 0-1
    education_level: str             # 教育水平: 高/中/低

    # 内容特征
    content_format: str              # 主要内容格式
    avg_content_length: str          # 平均内容长度
    interaction_types: list[str]     # 交互类型

    # 风险敏感度
    risk_sensitivity: dict[str, float] = field(default_factory=dict)  # 各维度风险敏感度 0-1
    cultural_taboos: list[str] = field(default_factory=list)          # 平台文化禁忌
    moderation_strictness: float = 0.5  # 审核严格度 0-1

    # 情绪分布基线 (正面/中性/负面)
    emotion_baseline: dict[str, float] = field(default_factory=dict)

    # 平台特有行为模式
    behavior_patterns: list[str] = field(default_factory=list)


# ===========================================================================
# P0 核心平台 (权重 1.0)
# ===========================================================================

PLATFORM_PROFILES: Dict[str, PlatformProfile] = {
    "weibo": PlatformProfile(
        platform_id="weibo",
        name="微博",
        tier="P0",
        weight=1.0,
        propagation_speed="极快",
        amplification_factor=3.5,
        echo_chamber_strength=0.5,
        polarization_tendency=0.8,
        user_base_size="5亿+月活",
        active_age_range=(18, 45),
        gender_ratio=0.55,
        education_level="中",
        content_format="短文本+图片+视频",
        avg_content_length="140字以内",
        interaction_types=["转发", "评论", "点赞", "超话"],
        risk_sensitivity={
            "政治敏感": 0.95,
            "时事踩雷": 0.90,
            "性别议题": 0.85,
            "群体冒犯": 0.80,
            "民族宗教": 0.90,
            "道德伦理": 0.75,
            "法律合规": 0.85,
            "情绪极化": 0.95,
            "事实错误": 0.70,
            "平台禁区": 0.90,
            "价值观倾向": 0.75,
        },
        cultural_taboos=["政治敏感", "虚假信息", "引战"],
        moderation_strictness=0.9,
        emotion_baseline={"positive": 0.25, "neutral": 0.35, "negative": 0.40},
        behavior_patterns=["热搜驱动", "大V引领", "情绪化表达", "快速传播"],
    ),

    "bilibili": PlatformProfile(
        platform_id="bilibili",
        name="B站",
        tier="P0",
        weight=1.0,
        propagation_speed="快",
        amplification_factor=2.5,
        echo_chamber_strength=0.7,
        polarization_tendency=0.6,
        user_base_size="3亿+月活",
        active_age_range=(15, 30),
        gender_ratio=0.45,
        education_level="中高",
        content_format="中长视频+弹幕",
        avg_content_length="5-15分钟视频",
        interaction_types=["弹幕", "评论", "点赞", "投币", "收藏", "分享"],
        risk_sensitivity={
            "政治敏感": 0.85,
            "时事踩雷": 0.75,
            "性别议题": 0.90,
            "群体冒犯": 0.85,
            "民族宗教": 0.80,
            "道德伦理": 0.70,
            "法律合规": 0.80,
            "情绪极化": 0.65,
            "事实错误": 0.85,
            "平台禁区": 0.75,
            "价值观倾向": 0.80,
        },
        cultural_taboos=["抄袭", "恰饭不透明", "低俗"],
        moderation_strictness=0.8,
        emotion_baseline={"positive": 0.40, "neutral": 0.35, "negative": 0.25},
        behavior_patterns=["弹幕文化", "二次元认同", "玩梗传播", "社区认同感强"],
    ),

    "xiaohongshu": PlatformProfile(
        platform_id="xiaohongshu",
        name="小红书",
        tier="P0",
        weight=1.0,
        propagation_speed="中等",
        amplification_factor=1.8,
        echo_chamber_strength=0.8,
        polarization_tendency=0.5,
        user_base_size="2亿+月活",
        active_age_range=(18, 35),
        gender_ratio=0.75,
        education_level="中高",
        content_format="图文笔记+短视频",
        avg_content_length="500-1000字+配图",
        interaction_types=["点赞", "收藏", "评论", "分享"],
        risk_sensitivity={
            "政治敏感": 0.70,
            "时事踩雷": 0.60,
            "性别议题": 0.95,
            "群体冒犯": 0.80,
            "民族宗教": 0.65,
            "道德伦理": 0.85,
            "法律合规": 0.75,
            "情绪极化": 0.55,
            "事实错误": 0.60,
            "平台禁区": 0.70,
            "价值观倾向": 0.90,
        },
        cultural_taboos=["虚假种草", "性别歧视", "身材焦虑"],
        moderation_strictness=0.7,
        emotion_baseline={"positive": 0.50, "neutral": 0.30, "negative": 0.20},
        behavior_patterns=["种草文化", "女性主导", "生活分享", "理性测评"],
    ),

    "douyin": PlatformProfile(
        platform_id="douyin",
        name="抖音",
        tier="P0",
        weight=1.0,
        propagation_speed="极快",
        amplification_factor=4.0,
        echo_chamber_strength=0.6,
        polarization_tendency=0.7,
        user_base_size="7亿+月活",
        active_age_range=(15, 50),
        gender_ratio=0.50,
        education_level="中",
        content_format="短视频",
        avg_content_length="15-60秒视频",
        interaction_types=["点赞", "评论", "转发", "收藏", "合拍"],
        risk_sensitivity={
            "政治敏感": 0.90,
            "时事踩雷": 0.85,
            "性别议题": 0.75,
            "群体冒犯": 0.85,
            "民族宗教": 0.90,
            "道德伦理": 0.80,
            "法律合规": 0.90,
            "情绪极化": 0.90,
            "事实错误": 0.75,
            "平台禁区": 0.95,
            "价值观倾向": 0.70,
        },
        cultural_taboos=["低俗", "虚假宣传", "危险行为"],
        moderation_strictness=0.95,
        emotion_baseline={"positive": 0.45, "neutral": 0.25, "negative": 0.30},
        behavior_patterns=["算法推荐", "病毒传播", "情绪驱动", "下沉市场"],
    ),

    "zhihu": PlatformProfile(
        platform_id="zhihu",
        name="知乎",
        tier="P0",
        weight=1.0,
        propagation_speed="慢",
        amplification_factor=1.5,
        echo_chamber_strength=0.6,
        polarization_tendency=0.5,
        user_base_size="1亿+月活",
        active_age_range=(20, 40),
        gender_ratio=0.45,
        education_level="高",
        content_format="长文回答+讨论",
        avg_content_length="1000-5000字",
        interaction_types=["赞同", "反对", "评论", "收藏", "关注"],
        risk_sensitivity={
            "政治敏感": 0.80,
            "时事踩雷": 0.85,
            "性别议题": 0.85,
            "群体冒犯": 0.75,
            "民族宗教": 0.85,
            "道德伦理": 0.90,
            "法律合规": 0.85,
            "情绪极化": 0.45,
            "事实错误": 0.95,
            "平台禁区": 0.80,
            "价值观倾向": 0.85,
        },
        cultural_taboos=["伪科学", "逻辑谬误", "情绪化表达"],
        moderation_strictness=0.8,
        emotion_baseline={"positive": 0.30, "neutral": 0.50, "negative": 0.20},
        behavior_patterns=["理性讨论", "长文分析", "专业背书", "反对情绪化"],
    ),

    # ===========================================================================
    # P1 次核心平台 (权重 0.7)
    # ===========================================================================

    "kuaishou": PlatformProfile(
        platform_id="kuaishou",
        name="快手",
        tier="P1",
        weight=0.7,
        propagation_speed="快",
        amplification_factor=2.5,
        echo_chamber_strength=0.7,
        polarization_tendency=0.6,
        user_base_size="5亿+月活",
        active_age_range=(18, 45),
        gender_ratio=0.50,
        education_level="中低",
        content_format="短视频+直播",
        avg_content_length="15-60秒视频",
        interaction_types=["点赞", "评论", "转发", "关注"],
        risk_sensitivity={
            "政治敏感": 0.85,
            "时事踩雷": 0.80,
            "性别议题": 0.70,
            "群体冒犯": 0.85,
            "民族宗教": 0.85,
            "道德伦理": 0.75,
            "法律合规": 0.85,
            "情绪极化": 0.80,
            "事实错误": 0.70,
            "平台禁区": 0.90,
            "价值观倾向": 0.65,
        },
        cultural_taboos=["低俗", "虚假宣传"],
        moderation_strictness=0.9,
        emotion_baseline={"positive": 0.50, "neutral": 0.25, "negative": 0.25},
        behavior_patterns=["老铁文化", "下沉市场", "社区粘性", "直播互动"],
    ),

    "tieba": PlatformProfile(
        platform_id="tieba",
        name="贴吧",
        tier="P1",
        weight=0.7,
        propagation_speed="中等",
        amplification_factor=1.5,
        echo_chamber_strength=0.8,
        polarization_tendency=0.7,
        user_base_size="3亿+月活",
        active_age_range=(15, 30),
        gender_ratio=0.40,
        education_level="中",
        content_format="帖子+回复",
        avg_content_length="200-1000字",
        interaction_types=["回复", "点赞", "关注"],
        risk_sensitivity={
            "政治敏感": 0.80,
            "时事踩雷": 0.75,
            "性别议题": 0.85,
            "群体冒犯": 0.90,
            "民族宗教": 0.80,
            "道德伦理": 0.70,
            "法律合规": 0.75,
            "情绪极化": 0.85,
            "事实错误": 0.70,
            "平台禁区": 0.80,
            "价值观倾向": 0.75,
        },
        cultural_taboos=["引战", "人身攻击"],
        moderation_strictness=0.75,
        emotion_baseline={"positive": 0.30, "neutral": 0.25, "negative": 0.45},
        behavior_patterns=["吧文化", "圈层化", "对抗性讨论", "玩梗"],
    ),

    "douban": PlatformProfile(
        platform_id="douban",
        name="豆瓣",
        tier="P1",
        weight=0.7,
        propagation_speed="慢",
        amplification_factor=1.2,
        echo_chamber_strength=0.75,
        polarization_tendency=0.65,
        user_base_size="3000万+月活",
        active_age_range=(20, 35),
        gender_ratio=0.65,
        education_level="高",
        content_format="长文+短评",
        avg_content_length="500-2000字",
        interaction_types=["评分", "短评", "小组讨论"],
        risk_sensitivity={
            "政治敏感": 0.75,
            "时事踩雷": 0.70,
            "性别议题": 0.95,
            "群体冒犯": 0.80,
            "民族宗教": 0.75,
            "道德伦理": 0.90,
            "法律合规": 0.70,
            "情绪极化": 0.60,
            "事实错误": 0.80,
            "平台禁区": 0.70,
            "价值观倾向": 0.95,
        },
        cultural_taboos=["饭圈文化", "低质内容"],
        moderation_strictness=0.7,
        emotion_baseline={"positive": 0.30, "neutral": 0.35, "negative": 0.35},
        behavior_patterns=["文艺社区", "小组讨论", "女性主导", "批判性强"],
    ),

    "wechat_channels": PlatformProfile(
        platform_id="wechat_channels",
        name="微信视频号",
        tier="P1",
        weight=0.7,
        propagation_speed="中等",
        amplification_factor=2.0,
        echo_chamber_strength=0.65,
        polarization_tendency=0.55,
        user_base_size="5亿+日活",
        active_age_range=(25, 55),
        gender_ratio=0.50,
        education_level="中",
        content_format="短视频+公众号",
        avg_content_length="30-60秒视频",
        interaction_types=["点赞", "评论", "转发", "在看"],
        risk_sensitivity={
            "政治敏感": 0.95,
            "时事踩雷": 0.90,
            "性别议题": 0.70,
            "群体冒犯": 0.75,
            "民族宗教": 0.90,
            "道德伦理": 0.80,
            "法律合规": 0.95,
            "情绪极化": 0.75,
            "事实错误": 0.80,
            "平台禁区": 0.95,
            "价值观倾向": 0.70,
        },
        cultural_taboos=["政治敏感", "虚假信息", "诱导分享"],
        moderation_strictness=0.95,
        emotion_baseline={"positive": 0.40, "neutral": 0.40, "negative": 0.20},
        behavior_patterns=["熟人社交传播", "公众号联动", "中老年用户多"],
    ),

    "hupu": PlatformProfile(
        platform_id="hupu",
        name="虎扑",
        tier="P1",
        weight=0.7,
        propagation_speed="快",
        amplification_factor=2.0,
        echo_chamber_strength=0.8,
        polarization_tendency=0.7,
        user_base_size="5000万+月活",
        active_age_range=(18, 35),
        gender_ratio=0.15,
        education_level="中",
        content_format="帖子+评论",
        avg_content_length="200-500字",
        interaction_types=["点赞", "评论", "回复", "亮"],
        risk_sensitivity={
            "政治敏感": 0.70, "时事踩雷": 0.75, "性别议题": 0.90,
            "群体冒犯": 0.85, "民族宗教": 0.75, "道德伦理": 0.70,
            "法律合规": 0.70, "情绪极化": 0.80, "事实错误": 0.65,
            "平台禁区": 0.70, "价值观倾向": 0.75,
        },
        cultural_taboos=["性别歧视", "引战", "地域黑"],
        moderation_strictness=0.7,
        emotion_baseline={"positive": 0.35, "neutral": 0.30, "negative": 0.35},
        behavior_patterns=["直男文化", "体育为主", "步行街文化", "投票文化"],
    ),

    "toutiao": PlatformProfile(
        platform_id="toutiao",
        name="今日头条",
        tier="P1",
        weight=0.7,
        propagation_speed="快",
        amplification_factor=2.5,
        echo_chamber_strength=0.75,
        polarization_tendency=0.65,
        user_base_size="3亿+月活",
        active_age_range=(25, 55),
        gender_ratio=0.40,
        education_level="中",
        content_format="图文+短视频",
        avg_content_length="500-1000字",
        interaction_types=["点赞", "评论", "转发", "收藏"],
        risk_sensitivity={
            "政治敏感": 0.90, "时事踩雷": 0.85, "性别议题": 0.70,
            "群体冒犯": 0.75, "民族宗教": 0.85, "道德伦理": 0.75,
            "法律合规": 0.85, "情绪极化": 0.80, "事实错误": 0.70,
            "平台禁区": 0.90, "价值观倾向": 0.70,
        },
        cultural_taboos=["标题党", "低俗", "虚假信息"],
        moderation_strictness=0.85,
        emotion_baseline={"positive": 0.30, "neutral": 0.35, "negative": 0.35},
        behavior_patterns=["算法推荐", "下沉市场", "中老年用户", "信息茧房"],
    ),

    "taptap": PlatformProfile(
        platform_id="taptap",
        name="TapTap",
        tier="P1",
        weight=0.7,
        propagation_speed="中等",
        amplification_factor=1.5,
        echo_chamber_strength=0.6,
        polarization_tendency=0.5,
        user_base_size="3000万+月活",
        active_age_range=(16, 30),
        gender_ratio=0.35,
        education_level="中高",
        content_format="游戏评测+社区讨论",
        avg_content_length="300-800字",
        interaction_types=["点赞", "评论", "回复", "评分"],
        risk_sensitivity={
            "政治敏感": 0.65, "时事踩雷": 0.55, "性别议题": 0.75,
            "群体冒犯": 0.70, "民族宗教": 0.65, "道德伦理": 0.70,
            "法律合规": 0.70, "情绪极化": 0.55, "事实错误": 0.80,
            "平台禁区": 0.65, "价值观倾向": 0.70,
        },
        cultural_taboos=["刷分", "引战", "抄袭"],
        moderation_strictness=0.7,
        emotion_baseline={"positive": 0.40, "neutral": 0.40, "negative": 0.20},
        behavior_patterns=["游戏评测", "核心玩家", "评分文化", "社区自治"],
    ),

    "wechat_official": PlatformProfile(
        platform_id="wechat_official",
        name="微信公众号",
        tier="P1",
        weight=0.7,
        propagation_speed="中等",
        amplification_factor=1.8,
        echo_chamber_strength=0.7,
        polarization_tendency=0.6,
        user_base_size="10亿+月活(微信生态)",
        active_age_range=(20, 50),
        gender_ratio=0.48,
        education_level="中高",
        content_format="长图文",
        avg_content_length="1000-3000字",
        interaction_types=["点赞", "在看", "转发", "收藏"],
        risk_sensitivity={
            "政治敏感": 0.95, "时事踩雷": 0.85, "性别议题": 0.75,
            "群体冒犯": 0.75, "民族宗教": 0.90, "道德伦理": 0.80,
            "法律合规": 0.90, "情绪极化": 0.70, "事实错误": 0.85,
            "平台禁区": 0.95, "价值观倾向": 0.80,
        },
        cultural_taboos=["政治敏感", "虚假信息", "诱导分享", "标题党"],
        moderation_strictness=0.95,
        emotion_baseline={"positive": 0.35, "neutral": 0.45, "negative": 0.20},
        behavior_patterns=["深度阅读", "长尾传播", "朋友圈转发", "意见领袖"],
    ),

    # ===========================================================================
    # P1 次核心平台 - 国际平台 (权重 0.7)
    # ===========================================================================

    "twitter": PlatformProfile(
        platform_id="twitter",
        name="Twitter/X",
        tier="P1",
        weight=0.7,
        propagation_speed="极快",
        amplification_factor=4.0,
        echo_chamber_strength=0.6,
        polarization_tendency=0.85,
        user_base_size="5亿+月活",
        active_age_range=(18, 45),
        gender_ratio=0.40,
        education_level="高",
        content_format="短文本+图片+视频",
        avg_content_length="280字以内",
        interaction_types=["转发", "回复", "点赞", "引用"],
        risk_sensitivity={
            "政治敏感": 0.90,
            "时事踩雷": 0.85,
            "性别议题": 0.80,
            "群体冒犯": 0.80,
            "民族宗教": 0.85,
            "道德伦理": 0.70,
            "法律合规": 0.75,
            "情绪极化": 0.95,
            "事实错误": 0.65,
            "平台禁区": 0.80,
            "价值观倾向": 0.80,
        },
        cultural_taboos=["仇恨言论", "政治虚假信息"],
        moderation_strictness=0.6,
        emotion_baseline={"positive": 0.20, "neutral": 0.35, "negative": 0.45},
        behavior_patterns=["话题标签传播", "意见领袖驱动", "实时性强", "极化严重"],
    ),

    "facebook": PlatformProfile(
        platform_id="facebook",
        name="Facebook",
        tier="P1",
        weight=0.7,
        propagation_speed="中等",
        amplification_factor=2.0,
        echo_chamber_strength=0.75,
        polarization_tendency=0.7,
        user_base_size="30亿+月活",
        active_age_range=(25, 55),
        gender_ratio=0.48,
        education_level="中",
        content_format="图文+视频+链接",
        avg_content_length="200-500字",
        interaction_types=["点赞", "评论", "分享", "表情反应"],
        risk_sensitivity={
            "政治敏感": 0.85,
            "时事踩雷": 0.80,
            "性别议题": 0.75,
            "群体冒犯": 0.80,
            "民族宗教": 0.85,
            "道德伦理": 0.80,
            "法律合规": 0.85,
            "情绪极化": 0.80,
            "事实错误": 0.75,
            "平台禁区": 0.85,
            "价值观倾向": 0.75,
        },
        cultural_taboos=["虚假新闻", "仇恨言论"],
        moderation_strictness=0.8,
        emotion_baseline={"positive": 0.35, "neutral": 0.35, "negative": 0.30},
        behavior_patterns=["熟人社交", "群组传播", "算法推荐", "信息茧房"],
    ),

    "instagram": PlatformProfile(
        platform_id="instagram",
        name="Instagram",
        tier="P1",
        weight=0.7,
        propagation_speed="快",
        amplification_factor=2.5,
        echo_chamber_strength=0.7,
        polarization_tendency=0.5,
        user_base_size="20亿+月活",
        active_age_range=(18, 35),
        gender_ratio=0.52,
        education_level="中高",
        content_format="图片+短视频+Stories",
        avg_content_length="图片为主+简短描述",
        interaction_types=["点赞", "评论", "分享", "收藏"],
        risk_sensitivity={
            "政治敏感": 0.60,
            "时事踩雷": 0.55,
            "性别议题": 0.85,
            "群体冒犯": 0.75,
            "民族宗教": 0.60,
            "道德伦理": 0.80,
            "法律合规": 0.70,
            "情绪极化": 0.50,
            "事实错误": 0.55,
            "平台禁区": 0.65,
            "价值观倾向": 0.85,
        },
        cultural_taboos=["身材焦虑", "虚假广告"],
        moderation_strictness=0.7,
        emotion_baseline={"positive": 0.50, "neutral": 0.30, "negative": 0.20},
        behavior_patterns=["视觉优先", "KOL营销", "生活方式展示", "滤镜文化"],
    ),

    "youtube": PlatformProfile(
        platform_id="youtube",
        name="YouTube",
        tier="P1",
        weight=0.7,
        propagation_speed="快",
        amplification_factor=2.5,
        echo_chamber_strength=0.65,
        polarization_tendency=0.6,
        user_base_size="20亿+月活",
        active_age_range=(18, 45),
        gender_ratio=0.42,
        education_level="高",
        content_format="长视频+短视频+直播",
        avg_content_length="10-30分钟视频",
        interaction_types=["点赞", "不喜欢", "评论", "分享", "订阅"],
        risk_sensitivity={
            "政治敏感": 0.80,
            "时事踩雷": 0.75,
            "性别议题": 0.70,
            "群体冒犯": 0.75,
            "民族宗教": 0.80,
            "道德伦理": 0.75,
            "法律合规": 0.90,
            "情绪极化": 0.70,
            "事实错误": 0.80,
            "平台禁区": 0.85,
            "价值观倾向": 0.70,
        },
        cultural_taboos=["版权", "极端内容"],
        moderation_strictness=0.8,
        emotion_baseline={"positive": 0.35, "neutral": 0.45, "negative": 0.20},
        behavior_patterns=["长视频深度", "创作者经济", "推荐算法", "评论区讨论"],
    ),

    "telegram": PlatformProfile(
        platform_id="telegram",
        name="Telegram",
        tier="P1",
        weight=0.7,
        propagation_speed="快",
        amplification_factor=2.0,
        echo_chamber_strength=0.8,
        polarization_tendency=0.7,
        user_base_size="8亿+月活",
        active_age_range=(18, 40),
        gender_ratio=0.40,
        education_level="高",
        content_format="即时消息+频道+群组",
        avg_content_length="无字数限制",
        interaction_types=["转发", "回复", "表情反应", "频道订阅"],
        risk_sensitivity={
            "政治敏感": 0.65,
            "时事踩雷": 0.60,
            "性别议题": 0.55,
            "群体冒犯": 0.60,
            "民族宗教": 0.60,
            "道德伦理": 0.55,
            "法律合规": 0.50,
            "情绪极化": 0.60,
            "事实错误": 0.55,
            "平台禁区": 0.45,
            "价值观倾向": 0.60,
        },
        cultural_taboos=[],
        moderation_strictness=0.3,
        emotion_baseline={"positive": 0.30, "neutral": 0.50, "negative": 0.20},
        behavior_patterns=["加密通讯", "频道订阅", "匿名性强", "信息自由流通"],
    ),

    "reddit": PlatformProfile(
        platform_id="reddit",
        name="Reddit",
        tier="P1",
        weight=0.7,
        propagation_speed="中等",
        amplification_factor=2.0,
        echo_chamber_strength=0.75,
        polarization_tendency=0.65,
        user_base_size="4亿+月活",
        active_age_range=(18, 35),
        gender_ratio=0.35,
        education_level="高",
        content_format="帖子+评论",
        avg_content_length="500-2000字",
        interaction_types=["上投票", "下投票", "评论", "奖励"],
        risk_sensitivity={
            "政治敏感": 0.75,
            "时事踩雷": 0.75,
            "性别议题": 0.80,
            "群体冒犯": 0.80,
            "民族宗教": 0.75,
            "道德伦理": 0.70,
            "法律合规": 0.70,
            "情绪极化": 0.75,
            "事实错误": 0.80,
            "平台禁区": 0.70,
            "价值观倾向": 0.75,
        },
        cultural_taboos=["人肉搜索", "仇恨言论"],
        moderation_strictness=0.65,
        emotion_baseline={"positive": 0.30, "neutral": 0.40, "negative": 0.30},
        behavior_patterns=["社区自治", "Subreddit分区", "投票机制", "匿名讨论"],
    ),

    # ===========================================================================
    # P2 长尾平台 (权重 0.4)
    # ===========================================================================

    "tiktok_global": PlatformProfile(
        platform_id="tiktok_global",
        name="TikTok国际版",
        tier="P2",
        weight=0.4,
        propagation_speed="极快",
        amplification_factor=4.0,
        echo_chamber_strength=0.6,
        polarization_tendency=0.65,
        user_base_size="15亿+月活",
        active_age_range=(15, 35),
        gender_ratio=0.52,
        education_level="中",
        content_format="短视频",
        avg_content_length="15-60秒视频",
        interaction_types=["点赞", "评论", "转发", "合拍", "收藏"],
        risk_sensitivity={
            "政治敏感": 0.80,
            "时事踩雷": 0.75,
            "性别议题": 0.70,
            "群体冒犯": 0.75,
            "民族宗教": 0.80,
            "道德伦理": 0.75,
            "法律合规": 0.85,
            "情绪极化": 0.80,
            "事实错误": 0.65,
            "平台禁区": 0.85,
            "价值观倾向": 0.65,
        },
        cultural_taboos=["低俗", "危险行为", "虚假宣传"],
        moderation_strictness=0.85,
        emotion_baseline={"positive": 0.45, "neutral": 0.30, "negative": 0.25},
        behavior_patterns=["算法推荐", "病毒传播", "挑战赛文化", "Z世代主导"],
    ),

    "linkedin": PlatformProfile(
        platform_id="linkedin",
        name="LinkedIn",
        tier="P2",
        weight=0.4,
        propagation_speed="慢",
        amplification_factor=1.2,
        echo_chamber_strength=0.5,
        polarization_tendency=0.3,
        user_base_size="9亿+月活",
        active_age_range=(25, 50),
        gender_ratio=0.45,
        education_level="高",
        content_format="职场动态+长文+招聘",
        avg_content_length="200-1000字",
        interaction_types=["点赞", "评论", "分享", "认可技能"],
        risk_sensitivity={
            "政治敏感": 0.65,
            "时事踩雷": 0.60,
            "性别议题": 0.75,
            "群体冒犯": 0.70,
            "民族宗教": 0.65,
            "道德伦理": 0.80,
            "法律合规": 0.85,
            "情绪极化": 0.35,
            "事实错误": 0.85,
            "平台禁区": 0.75,
            "价值观倾向": 0.70,
        },
        cultural_taboos=["虚假履历", "骚扰"],
        moderation_strictness=0.85,
        emotion_baseline={"positive": 0.40, "neutral": 0.45, "negative": 0.15},
        behavior_patterns=["职场社交", "个人品牌建设", "B2B营销", "招聘求职"],
    ),

    "nga": PlatformProfile(
        platform_id="nga",
        name="NGA",
        tier="P2",
        weight=0.4,
        propagation_speed="中等",
        amplification_factor=1.5,
        echo_chamber_strength=0.8,
        polarization_tendency=0.75,
        user_base_size="2000万+月活",
        active_age_range=(18, 35),
        gender_ratio=0.10,
        education_level="中",
        content_format="帖子+回复",
        avg_content_length="200-1000字",
        interaction_types=["回复", "点赞", "评分"],
        risk_sensitivity={
            "政治敏感": 0.75,
            "时事踩雷": 0.70,
            "性别议题": 0.80,
            "群体冒犯": 0.90,
            "民族宗教": 0.70,
            "道德伦理": 0.65,
            "法律合规": 0.70,
            "情绪极化": 0.85,
            "事实错误": 0.75,
            "平台禁区": 0.75,
            "价值观倾向": 0.70,
        },
        cultural_taboos=["引战", "外挂"],
        moderation_strictness=0.6,
        emotion_baseline={"positive": 0.25, "neutral": 0.30, "negative": 0.45},
        behavior_patterns=["游戏文化", "高强度讨论", "社区等级制度", "梗文化"],
    ),

    "v2ex": PlatformProfile(
        platform_id="v2ex",
        name="V2EX",
        tier="P2",
        weight=0.4,
        propagation_speed="慢",
        amplification_factor=1.2,
        echo_chamber_strength=0.7,
        polarization_tendency=0.4,
        user_base_size="500万+月活",
        active_age_range=(22, 40),
        gender_ratio=0.15,
        education_level="高",
        content_format="主题帖+回复",
        avg_content_length="300-1500字",
        interaction_types=["回复", "感谢", "收藏"],
        risk_sensitivity={
            "政治敏感": 0.70,
            "时事踩雷": 0.65,
            "性别议题": 0.60,
            "群体冒犯": 0.70,
            "民族宗教": 0.60,
            "道德伦理": 0.75,
            "法律合规": 0.70,
            "情绪极化": 0.45,
            "事实错误": 0.85,
            "平台禁区": 0.70,
            "价值观倾向": 0.65,
        },
        cultural_taboos=["引战", "招聘广告"],
        moderation_strictness=0.65,
        emotion_baseline={"positive": 0.30, "neutral": 0.50, "negative": 0.20},
        behavior_patterns=["技术极客", "理性讨论", "社区自治", "Mac文化"],
    ),

    "maimai": PlatformProfile(
        platform_id="maimai",
        name="脉脉",
        tier="P2",
        weight=0.4,
        propagation_speed="中等",
        amplification_factor=1.5,
        echo_chamber_strength=0.7,
        polarization_tendency=0.6,
        user_base_size="1亿+月活",
        active_age_range=(25, 45),
        gender_ratio=0.45,
        education_level="高",
        content_format="匿名动态+实名讨论",
        avg_content_length="200-800字",
        interaction_types=["点赞", "评论", "匿名爆料"],
        risk_sensitivity={
            "政治敏感": 0.70,
            "时事踩雷": 0.75,
            "性别议题": 0.80,
            "群体冒犯": 0.80,
            "民族宗教": 0.65,
            "道德伦理": 0.80,
            "法律合规": 0.85,
            "情绪极化": 0.75,
            "事实错误": 0.70,
            "平台禁区": 0.80,
            "价值观倾向": 0.75,
        },
        cultural_taboos=["薪资泄露", "公司负面"],
        moderation_strictness=0.75,
        emotion_baseline={"positive": 0.25, "neutral": 0.35, "negative": 0.40},
        behavior_patterns=["匿名爆料", "职场八卦", "薪资讨论", "公司评价"],
    ),

    "boss_zhilian": PlatformProfile(
        platform_id="boss_zhilian",
        name="Boss直聘",
        tier="P2",
        weight=0.4,
        propagation_speed="慢",
        amplification_factor=1.0,
        echo_chamber_strength=0.5,
        polarization_tendency=0.35,
        user_base_size="1亿+月活",
        active_age_range=(22, 40),
        gender_ratio=0.45,
        education_level="中",
        content_format="招聘帖+聊天+简历",
        avg_content_length="100-500字",
        interaction_types=["打招呼", "沟通", "收藏", "举报"],
        risk_sensitivity={
            "政治敏感": 0.60,
            "时事踩雷": 0.55,
            "性别议题": 0.80,
            "群体冒犯": 0.75,
            "民族宗教": 0.60,
            "道德伦理": 0.80,
            "法律合规": 0.90,
            "情绪极化": 0.40,
            "事实错误": 0.75,
            "平台禁区": 0.80,
            "价值观倾向": 0.65,
        },
        cultural_taboos=["虚假招聘", "薪资欺诈"],
        moderation_strictness=0.85,
        emotion_baseline={"positive": 0.35, "neutral": 0.45, "negative": 0.20},
        behavior_patterns=["直聊招聘方", "求职评价", "薪资透明", "跳槽文化"],
    ),

    "smzdm": PlatformProfile(
        platform_id="smzdm",
        name="什么值得买",
        tier="P2",
        weight=0.4,
        propagation_speed="中等",
        amplification_factor=1.5,
        echo_chamber_strength=0.6,
        polarization_tendency=0.4,
        user_base_size="3000万+月活",
        active_age_range=(25, 45),
        gender_ratio=0.40,
        education_level="中",
        content_format="消费测评+优惠信息",
        avg_content_length="300-1000字",
        interaction_types=["点赞", "评论", "收藏", "爆料"],
        risk_sensitivity={
            "政治敏感": 0.50,
            "时事踩雷": 0.45,
            "性别议题": 0.55,
            "群体冒犯": 0.60,
            "民族宗教": 0.50,
            "道德伦理": 0.75,
            "法律合规": 0.80,
            "情绪极化": 0.45,
            "事实错误": 0.85,
            "平台禁区": 0.75,
            "价值观倾向": 0.60,
        },
        cultural_taboos=["虚假测评", "软文"],
        moderation_strictness=0.75,
        emotion_baseline={"positive": 0.40, "neutral": 0.40, "negative": 0.20},
        behavior_patterns=["消费决策", "性价比导向", "优惠分享", "测评文化"],
    ),

    "zhihu_zhuanlan": PlatformProfile(
        platform_id="zhihu_zhuanlan",
        name="知乎专栏",
        tier="P2",
        weight=0.4,
        propagation_speed="慢",
        amplification_factor=1.3,
        echo_chamber_strength=0.6,
        polarization_tendency=0.45,
        user_base_size="5000万+月活",
        active_age_range=(22, 40),
        gender_ratio=0.42,
        education_level="高",
        content_format="深度长文",
        avg_content_length="2000-10000字",
        interaction_types=["点赞", "评论", "收藏", "关注"],
        risk_sensitivity={
            "政治敏感": 0.75,
            "时事踩雷": 0.80,
            "性别议题": 0.80,
            "群体冒犯": 0.70,
            "民族宗教": 0.75,
            "道德伦理": 0.85,
            "法律合规": 0.80,
            "情绪极化": 0.40,
            "事实错误": 0.90,
            "平台禁区": 0.75,
            "价值观倾向": 0.80,
        },
        cultural_taboos=["伪科学", "洗稿"],
        moderation_strictness=0.75,
        emotion_baseline={"positive": 0.30, "neutral": 0.50, "negative": 0.20},
        behavior_patterns=["深度创作", "专业背书", "长文阅读", "知识付费"],
    ),

    "jike": PlatformProfile(
        platform_id="jike",
        name="即刻",
        tier="P2",
        weight=0.4,
        propagation_speed="中等",
        amplification_factor=1.5,
        echo_chamber_strength=0.7,
        polarization_tendency=0.5,
        user_base_size="500万+月活",
        active_age_range=(22, 35),
        gender_ratio=0.35,
        education_level="高",
        content_format="短动态+话题+圈子",
        avg_content_length="100-500字",
        interaction_types=["点赞", "评论", "转发", "收藏"],
        risk_sensitivity={
            "政治敏感": 0.70,
            "时事踩雷": 0.70,
            "性别议题": 0.75,
            "群体冒犯": 0.70,
            "民族宗教": 0.65,
            "道德伦理": 0.75,
            "法律合规": 0.70,
            "情绪极化": 0.55,
            "事实错误": 0.75,
            "平台禁区": 0.65,
            "价值观倾向": 0.80,
        },
        cultural_taboos=["引战", "广告"],
        moderation_strictness=0.65,
        emotion_baseline={"positive": 0.35, "neutral": 0.40, "negative": 0.25},
        behavior_patterns=["兴趣圈子", "科技圈文化", "动态订阅", "精英社区"],
    ),
}


# ===========================================================================
# 工具函数
# ===========================================================================

def get_platform_profile(platform_id: str) -> Optional[PlatformProfile]:
    """获取平台画像配置"""
    return PLATFORM_PROFILES.get(platform_id)


def get_platforms_by_tier(tier: str = "P0") -> List[PlatformProfile]:
    """按分级获取平台列表"""
    return [p for p in PLATFORM_PROFILES.values() if p.tier == tier]


def get_p0_platforms() -> List[str]:
    """获取P0核心平台ID列表"""
    return [p.platform_id for p in get_platforms_by_tier("P0")]


def calculate_platform_weighted_score(platform_scores: Dict[str, float]) -> float:
    """计算平台加权风险分

    Args:
        platform_scores: {platform_id: score} 各平台风险评分

    Returns:
        加权后的综合风险分
    """
    if not platform_scores:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for platform_id, score in platform_scores.items():
        profile = get_platform_profile(platform_id)
        if profile:
            weight = profile.weight
        else:
            weight = 0.4  # 未知平台默认P2权重

        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight


def get_platform_risk_sensitivity(platform_id: str) -> Dict[str, float]:
    """获取平台对各维度的风险敏感度"""
    profile = get_platform_profile(platform_id)
    if profile:
        return profile.risk_sensitivity.copy()
    # 未知平台返回默认敏感度
    return {
        "政治敏感": 0.8,
        "时事踩雷": 0.8,
        "性别议题": 0.7,
        "群体冒犯": 0.7,
        "民族宗教": 0.8,
        "道德伦理": 0.7,
        "法律合规": 0.8,
        "情绪极化": 0.7,
        "事实错误": 0.7,
        "平台禁区": 0.8,
        "价值观倾向": 0.7,
    }


def adjust_risk_by_platform(score: float, dimension: str, platform_id: str) -> float:
    """根据平台敏感度调整风险分数

    Args:
        score: 原始风险分数
        dimension: 风险维度
        platform_id: 平台标识

    Returns:
        调整后的风险分数
    """
    sensitivity = get_platform_risk_sensitivity(platform_id)
    dim_sensitivity = sensitivity.get(dimension, 0.7)

    # 敏感度>0.8时风险分数上浮，<0.6时下调
    if dim_sensitivity >= 0.85:
        return min(100, score * 1.15)
    elif dim_sensitivity >= 0.80:
        return min(100, score * 1.08)
    elif dim_sensitivity <= 0.60:
        return score * 0.90
    else:
        return score


def get_platform_emotion_bias(platform_id: str) -> Dict[str, float]:
    """获取平台情绪基线偏移"""
    profile = get_platform_profile(platform_id)
    if profile:
        return profile.emotion_baseline.copy()
    return {"positive": 0.35, "neutral": 0.35, "negative": 0.30}


def get_propagation_params(platform_id: str) -> Dict[str, Any]:
    """获取平台传播动力学参数"""
    profile = get_platform_profile(platform_id)
    if not profile:
        return {
            "propagation_speed": "中等",
            "amplification_factor": 1.5,
            "echo_chamber_strength": 0.6,
            "polarization_tendency": 0.5,
        }
    return {
        "propagation_speed": profile.propagation_speed,
        "amplification_factor": profile.amplification_factor,
        "echo_chamber_strength": profile.echo_chamber_strength,
        "polarization_tendency": profile.polarization_tendency,
    }
