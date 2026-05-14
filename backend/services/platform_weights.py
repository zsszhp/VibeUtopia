"""平台权重体系 - 阶段2: 平台深度打磨

定义5大核心平台(P0)的权重配置、传播特征、用户画像特征。
不同平台的评估结果按权重影响总风险分。

平台分级:
- P0(权重1.0): 微博、B站、小红书、抖音、知乎 — 核心平台，影响占比≥70%
- P1(权重0.7): 快手、贴吧、豆瓣、微信视频号 — 次核心平台
- P2(权重0.4): 其他长尾平台
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

    "shipinhao": PlatformProfile(
        platform_id="shipinhao",
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
