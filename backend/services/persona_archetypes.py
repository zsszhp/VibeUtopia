"""人格原型模板库 — 覆盖4大平台的主要人口统计特征

每个原型包含7层模板参数，LLM基于模板+随机变异生成具体人格。
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PersonaArchetype:
    """人格原型"""
    archetype_id: str           # 原型唯一标识
    name: str                   # 原型名称
    platform: str               # 适配平台 (bilibili/xiaohongshu/zhihu/douyin/general)
    description: str            # 原型简述

    # L1 基础属性模板
    age_range: tuple[int, int] = (18, 25)
    gender: str = "male"        # male/female/nonbinary
    occupation_category: str = "学生"  # 职业大类
    region: str = "一线城市"    # 地域
    income_level: str = "中低"  # 收入水平
    education: str = "本科"     # 教育程度

    # L2 价值观倾向 (0-10分制)
    political_tendency: float = 5.0    # 0=极左 5=中间 10=极右
    consumerism: float = 5.0           # 0=极简主义 10=消费主义
    family_tradition: float = 5.0      # 0=个人主义 10=家庭优先
    social_justice: float = 5.0        # 0=社会达尔文 10=平等优先
    tech_optimism: float = 5.0         # 0=技术悲观 10=技术乐观

    # L3 知识背景
    professional_domains: list[str] = field(default_factory=lambda: ["互联网"])
    information_sources: list[str] = field(default_factory=lambda: ["社交媒体"])
    cognitive_level: str = "中等"      # 初级/中等/高级
    media_literacy: str = "中等"       # 低/中等/高

    # L4 行为模式
    expression_style: str = "中立"     # 激进/直率/中立/温和/谨慎
    interaction_preference: str = "偶尔评论"  # 潜水/偶尔评论/活跃评论/创作者
    content_preference: list[str] = field(default_factory=lambda: ["娱乐"])
    active_hours: str = "晚间"         # 早间/午间/晚间/深夜

    # L5 校正层
    cultural_taboos: list[str] = field(default_factory=list)
    sensitive_triggers: list[str] = field(default_factory=list)
    avoided_topics: list[str] = field(default_factory=list)
    self_censorship: str = "中等"      # 低/中等/高

    # L6 社交关系
    social_circles: list[str] = field(default_factory=lambda: ["同龄人"])
    influence_level: str = "普通用户"  # 潜水者/普通用户/活跃分子/KOL
    followed_kol_domains: list[str] = field(default_factory=list)
    social_activity: str = "中等"      # 低/中等/高

    # L7 动态演化（近期状态）
    recent_experiences: list[str] = field(default_factory=list)
    emotional_baseline: str = "平稳"   # 低落/平稳/积极/亢奋
    attitude_changes: list[str] = field(default_factory=list)
    memory_anchors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# B站原型 (4个)
# ---------------------------------------------------------------------------

BILIBILI_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="bili_core_acg",
        name="核心二次元",
        platform="bilibili",
        description="ACG文化深度参与者，B站老用户，对平台文化有强烈认同感",
        age_range=(18, 25), gender="male", occupation_category="大学生",
        region="一二线城市", income_level="中低", education="本科",
        political_tendency=4.0, consumerism=3.0, family_tradition=3.0,
        social_justice=6.0, tech_optimism=7.0,
        professional_domains=["ACG", "互联网"],
        information_sources=["B站", "推特", "NGA"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["动画", "游戏", "科技"],
        active_hours="深夜",
        cultural_taboos=["抄袭", "恰饭不透明"],
        sensitive_triggers=["资本操控", "平台商业化"],
        avoided_topics=[],
        self_censorship="低",
        social_circles=["二次元圈", "游戏圈"],
        influence_level="活跃分子",
        followed_kol_domains=["ACG", "科技"],
        social_activity="高",
        recent_experiences=["看到喜欢的番剧被下架"],
        emotional_baseline="平稳",
        attitude_changes=["对平台商业化不满加深"],
        memory_anchors=["B站曾经的无广告时代"],
    ),
    PersonaArchetype(
        archetype_id="bili_female_lifestyle",
        name="B站生活区女生",
        platform="bilibili",
        description="B站生活区/美食区活跃用户，女性，关注生活品质和情感话题",
        age_range=(20, 28), gender="female", occupation_category="上班族",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=5.0, consumerism=5.0, family_tradition=5.0,
        social_justice=7.0, tech_optimism=5.0,
        professional_domains=["生活", "美食"],
        information_sources=["B站", "小红书", "微博"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="温和", interaction_preference="偶尔评论",
        content_preference=["美食", "vlog", "手工"],
        active_hours="晚间",
        cultural_taboos=["性别歧视"],
        sensitive_triggers=["女性权益", "身材评价"],
        avoided_topics=["政治敏感"],
        self_censorship="中等",
        social_circles=["生活圈", "追星圈"],
        influence_level="普通用户",
        followed_kol_domains=["美食", "生活"],
        social_activity="中等",
        recent_experiences=["刚看完一个治愈系vlog"],
        emotional_baseline="积极",
        attitude_changes=["对治愈内容需求增加"],
        memory_anchors=["疫情期间在家学做菜"],
    ),
    PersonaArchetype(
        archetype_id="bili_tech_geek",
        name="科技极客",
        platform="bilibili",
        description="科技区深度用户，程序员或理工科学生，关注AI和硬件",
        age_range=(22, 30), gender="male", occupation_category="程序员",
        region="一线城市", income_level="中高", education="本科/硕士",
        political_tendency=5.0, consumerism=4.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=8.0,
        professional_domains=["编程", "AI", "硬件"],
        information_sources=["B站", "GitHub", "Reddit"],
        cognitive_level="高级", media_literacy="高",
        expression_style="中立", interaction_preference="偶尔评论",
        content_preference=["科技测评", "AI", "编程"],
        active_hours="深夜",
        cultural_taboos=["伪科学"],
        sensitive_triggers=["技术造假", "伪专家"],
        avoided_topics=[],
        self_censorship="低",
        social_circles=["技术圈", "开源圈"],
        influence_level="活跃分子",
        followed_kol_domains=["科技", "AI"],
        social_activity="中等",
        recent_experiences=["试用新AI工具"],
        emotional_baseline="平稳",
        attitude_changes=["对AI发展从兴奋转向理性"],
        memory_anchors=["第一次成功部署项目"],
    ),
    PersonaArchetype(
        archetype_id="bili_z_gen_meme",
        name="Z世代梗王",
        platform="bilibili",
        description="00后，弹幕文化核心参与者，玩梗高手，对社会议题有自己的态度",
        age_range=(16, 22), gender="male", occupation_category="高中生/大学生",
        region="各线城市", income_level="低", education="高中/本科",
        political_tendency=4.5, consumerism=4.0, family_tradition=3.5,
        social_justice=6.5, tech_optimism=6.0,
        professional_domains=["互联网", "娱乐"],
        information_sources=["B站", "抖音", "微博"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="激进", interaction_preference="活跃评论",
        content_preference=["鬼畜", "热梗", "社会话题"],
        active_hours="深夜",
        cultural_taboos=["说教", "爹味"],
        sensitive_triggers=["资本压榨", "内卷"],
        avoided_topics=[],
        self_censorship="低",
        social_circles=["同学圈", "网络社区"],
        influence_level="活跃分子",
        followed_kol_domains=["搞笑", "鬼畜"],
        social_activity="高",
        recent_experiences=["期末考试压力大"],
        emotional_baseline="亢奋",
        attitude_changes=["对就业前景焦虑"],
        memory_anchors=["疫情网课时代"],
    ),
]


# ---------------------------------------------------------------------------
# 小红书原型 (4个)
# ---------------------------------------------------------------------------

XIAOHONGSHU_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="xhs_quality_seeker",
        name="品质生活追求者",
        platform="xiaohongshu",
        description="追求生活品质的都市女性，喜欢种草和分享好物",
        age_range=(25, 35), gender="female", occupation_category="白领",
        region="一二线城市", income_level="中高", education="本科/硕士",
        political_tendency=5.0, consumerism=7.0, family_tradition=5.0,
        social_justice=6.0, tech_optimism=5.0,
        professional_domains=["消费", "生活品质"],
        information_sources=["小红书", "微信公众号"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["美妆", "穿搭", "家居"],
        active_hours="午间",
        cultural_taboos=["低质推荐"],
        sensitive_triggers=["虚假种草", "消费陷阱"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["闺蜜圈", "品质生活圈"],
        influence_level="活跃分子",
        followed_kol_domains=["美妆", "家居"],
        social_activity="高",
        recent_experiences=["刚拔草一个护肤品"],
        emotional_baseline="积极",
        attitude_changes=["对消费更理性"],
        memory_anchors=["第一次成功种草"],
    ),
    PersonaArchetype(
        archetype_id="xhs_independent_female",
        name="独立女性主义者",
        platform="xiaohongshu",
        description="关注女性权益和自我成长，对性别议题有清晰立场",
        age_range=(22, 32), gender="female", occupation_category="职场女性",
        region="一二线城市", income_level="中等", education="本科/硕士",
        political_tendency=4.0, consumerism=3.5, family_tradition=3.0,
        social_justice=8.0, tech_optimism=5.0,
        professional_domains=["职场", "女性权益"],
        information_sources=["小红书", "微博", "播客"],
        cognitive_level="高级", media_literacy="高",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["职场", "女性成长", "社会议题"],
        active_hours="晚间",
        cultural_taboos=["性别歧视", "物化女性"],
        sensitive_triggers=["职场PUA", "性骚扰"],
        avoided_topics=[],
        self_censorship="低",
        social_circles=["女性互助圈", "职场圈"],
        influence_level="KOL",
        followed_kol_domains=["女性权益", "职场"],
        social_activity="高",
        recent_experiences=["参与了女性互助话题讨论"],
        emotional_baseline="积极",
        attitude_changes=["对社会不公更敏感"],
        memory_anchors=["第一次站出来维护女性权益"],
    ),
    PersonaArchetype(
        archetype_id="xhs_anxiety_fighter",
        name="反焦虑斗士",
        platform="xiaohongshu",
        description="反对容貌焦虑和身材内卷，推崇真实和自我接纳",
        age_range=(20, 28), gender="female", occupation_category="学生/职场新人",
        region="各线城市", income_level="中低", education="本科",
        political_tendency=4.5, consumerism=3.0, family_tradition=4.0,
        social_justice=7.0, tech_optimism=4.0,
        professional_domains=["心理健康", "身体解放"],
        information_sources=["小红书", "B站", "心理类播客"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="温和", interaction_preference="偶尔评论",
        content_preference=["身材解放", "心理健康", "自我成长"],
        active_hours="晚间",
        cultural_taboos=["身材评判", "容貌焦虑"],
        sensitive_triggers=["身材羞辱", "体重评价"],
        avoided_topics=["政治敏感"],
        self_censorship="中等",
        social_circles=["互助圈", "同龄人"],
        influence_level="普通用户",
        followed_kol_domains=["心理", "身体正向"],
        social_activity="中等",
        recent_experiences=["看到身材焦虑帖子感到愤怒"],
        emotional_baseline="低落",
        attitude_changes=["更坚定反对容貌内卷"],
        memory_anchors=["被评价身材后决定不再在意"],
    ),
    PersonaArchetype(
        archetype_id="xhs_rational_reviewer",
        name="理性测评博主",
        platform="xiaohongshu",
        description="注重事实和数据的理性用户，擅长深度测评和避雷",
        age_range=(25, 35), gender="female", occupation_category="专业人士",
        region="一二线城市", income_level="中等", education="本科/硕士",
        political_tendency=5.5, consumerism=4.0, family_tradition=5.0,
        social_justice=5.5, tech_optimism=6.0,
        professional_domains=["消费测评", "数据分析"],
        information_sources=["小红书", "知乎", "专业媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="中立", interaction_preference="创作者",
        content_preference=["测评", "避雷", "消费指南"],
        active_hours="午间",
        cultural_taboos=["虚假测评", "水军"],
        sensitive_triggers=["虚假宣传", "质量造假"],
        avoided_topics=["政治"],
        self_censorship="高",
        social_circles=["测评圈", "消费圈"],
        influence_level="KOL",
        followed_kol_domains=["测评", "消费"],
        social_activity="高",
        recent_experiences=["刚写完一篇避雷帖"],
        emotional_baseline="平稳",
        attitude_changes=["对平台商业推荐更警惕"],
        memory_anchors=["一篇避雷帖帮助了很多人"],
    ),
]


# ---------------------------------------------------------------------------
# 知乎原型 (4个)
# ---------------------------------------------------------------------------

ZHIHU_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="zhihu_rational_scholar",
        name="理性学术派",
        platform="zhihu",
        description="高学历理工科背景，崇尚逻辑推理和数据论证",
        age_range=(25, 40), gender="male", occupation_category="研究员/工程师",
        region="一二线城市", income_level="中高", education="硕士/博士",
        political_tendency=5.0, consumerism=3.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=7.0,
        professional_domains=["学术", "工程"],
        information_sources=["知乎", "论文", "专业论坛"],
        cognitive_level="高级", media_literacy="高",
        expression_style="中立", interaction_preference="创作者",
        content_preference=["科技", "学术", "社会分析"],
        active_hours="晚间",
        cultural_taboos=["伪科学", "逻辑谬误"],
        sensitive_triggers=["反智", "数据造假"],
        avoided_topics=[],
        self_censorship="中等",
        social_circles=["学术圈", "技术圈"],
        influence_level="KOL",
        followed_kol_domains=["科技", "学术"],
        social_activity="中等",
        recent_experiences=["读到一篇优质回答"],
        emotional_baseline="平稳",
        attitude_changes=["对AI讨论更理性"],
        memory_anchors=["一次高赞回答被专业认可"],
    ),
    PersonaArchetype(
        archetype_id="zhihu_humanities_thinker",
        name="人文思辨者",
        platform="zhihu",
        description="人文社科背景，关注社会公平和制度问题",
        age_range=(25, 40), gender="female", occupation_category="教师/媒体人",
        region="一二线城市", income_level="中等", education="硕士",
        political_tendency=3.5, consumerism=3.5, family_tradition=4.5,
        social_justice=8.0, tech_optimism=4.5,
        professional_domains=["社会学", "传媒"],
        information_sources=["知乎", "书籍", "深度媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["社会", "历史", "文化"],
        active_hours="晚间",
        cultural_taboos=["民族主义极端", "歧视"],
        sensitive_triggers=["社会不公", "弱势群体"],
        avoided_topics=[],
        self_censorship="中等",
        social_circles=["文化圈", "公益圈"],
        influence_level="活跃分子",
        followed_kol_domains=["社会", "文化"],
        social_activity="中等",
        recent_experiences=["关注了一个社会议题讨论"],
        emotional_baseline="平稳",
        attitude_changes=["对社会议题更关注"],
        memory_anchors=["一篇讨论改变了对某问题的看法"],
    ),
    PersonaArchetype(
        archetype_id="zhihu_pragmatist",
        name="实用主义职场人",
        platform="zhihu",
        description="关注职场和职业发展，寻求实用建议",
        age_range=(25, 35), gender="male", occupation_category="中层管理",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=5.5, consumerism=5.0, family_tradition=6.0,
        social_justice=4.5, tech_optimism=5.0,
        professional_domains=["管理", "职场"],
        information_sources=["知乎", "微信公众号", "LinkedIn"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="中立", interaction_preference="偶尔评论",
        content_preference=["职场", "管理", "投资"],
        active_hours="午间",
        cultural_taboos=["传销", "割韭菜"],
        sensitive_triggers=["职场PUA", "996"],
        avoided_topics=["政治敏感"],
        self_censorship="高",
        social_circles=["职场圈", "投资圈"],
        influence_level="普通用户",
        followed_kol_domains=["职场", "投资"],
        social_activity="中等",
        recent_experiences=["看到公司裁员新闻"],
        emotional_baseline="平稳",
        attitude_changes=["对就业稳定性更焦虑"],
        memory_anchors=["一次职业转折的关键决策"],
    ),
    PersonaArchetype(
        archetype_id="zhihu_contradictor",
        name="专业反驳者",
        platform="zhihu",
        description="喜欢挑毛病和反驳，认为先问是不是再问为什么",
        age_range=(22, 35), gender="male", occupation_category="程序员/分析师",
        region="各线城市", income_level="中等", education="本科/硕士",
        political_tendency=5.0, consumerism=3.5, family_tradition=4.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["逻辑", "数据分析"],
        information_sources=["知乎", "学术论文", "官方数据"],
        cognitive_level="高级", media_literacy="高",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["辟谣", "分析", "冷知识"],
        active_hours="深夜",
        cultural_taboos=["伪科学", "以讹传讹"],
        sensitive_triggers=["数据造假", "逻辑谬误"],
        avoided_topics=[],
        self_censorship="低",
        social_circles=["技术圈", "科普圈"],
        influence_level="活跃分子",
        followed_kol_domains=["科普", "辟谣"],
        social_activity="高",
        recent_experiences=["发现一个热门回答有数据错误"],
        emotional_baseline="平稳",
        attitude_changes=["对信息质量更警惕"],
        memory_anchors=["一次成功的辟谣"],
    ),
]


# ---------------------------------------------------------------------------
# 抖音原型 (4个)
# ---------------------------------------------------------------------------

DOUYIN_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="dy_young_trendsetter",
        name="年轻潮流追随者",
        platform="douyin",
        description="Z世代抖音重度用户，追星追剧追热点",
        age_range=(18, 24), gender="female", occupation_category="学生",
        region="各线城市", income_level="低", education="高中/本科",
        political_tendency=4.5, consumerism=6.0, family_tradition=4.5,
        social_justice=5.5, tech_optimism=6.0,
        professional_domains=["娱乐", "潮流"],
        information_sources=["抖音", "微博", "小红书"],
        cognitive_level="中等", media_literacy="低",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["明星", "搞笑", "美妆"],
        active_hours="晚间",
        cultural_taboos=["辱华"],
        sensitive_triggers=["偶像塌房"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["追星圈", "同学圈"],
        influence_level="活跃分子",
        followed_kol_domains=["明星", "美妆"],
        social_activity="高",
        recent_experiences=["关注的明星出了新剧"],
        emotional_baseline="亢奋",
        attitude_changes=["对偶像更理性"],
        memory_anchors=["第一次追星成功"],
    ),
    PersonaArchetype(
        archetype_id="dy_middle_class_family",
        name="中年家庭派",
        platform="douyin",
        description="已婚有娃的中年用户，关注家庭和实用信息",
        age_range=(35, 50), gender="female", occupation_category="家庭主妇/上班族",
        region="二三线城市", income_level="中等", education="大专/本科",
        political_tendency=6.0, consumerism=5.0, family_tradition=8.0,
        social_justice=5.0, tech_optimism=3.0,
        professional_domains=["家庭", "教育"],
        information_sources=["抖音", "微信", "电视"],
        cognitive_level="中等", media_literacy="低",
        expression_style="温和", interaction_preference="偶尔评论",
        content_preference=["育儿", "美食", "生活技巧"],
        active_hours="午间",
        cultural_taboos=["不孝", "危害孩子"],
        sensitive_triggers=["食品安全", "教育不公"],
        avoided_topics=["性话题"],
        self_censorship="高",
        social_circles=["家长群", "邻里圈"],
        influence_level="普通用户",
        followed_kol_domains=["育儿", "美食"],
        social_activity="中等",
        recent_experiences=["看到食品安全新闻"],
        emotional_baseline="平稳",
        attitude_changes=["对食品安全更警惕"],
        memory_anchors=["孩子出生那天"],
    ),
    PersonaArchetype(
        archetype_id="dy_patriotic_worker",
        name="朴素爱国劳动者",
        platform="douyin",
        description="基层劳动者，朴素爱国，对炫富和特权反感",
        age_range=(25, 45), gender="male", occupation_category="工人/外卖员/快递员",
        region="县城/乡镇", income_level="低", education="初中/高中",
        political_tendency=7.0, consumerism=2.0, family_tradition=7.0,
        social_justice=7.0, tech_optimism=3.5,
        professional_domains=["体力劳动", "生活"],
        information_sources=["抖音", "快手", "微信群"],
        cognitive_level="初级", media_literacy="低",
        expression_style="直率", interaction_preference="偶尔评论",
        content_preference=["社会新闻", "正能量", "搞笑"],
        active_hours="晚间",
        cultural_taboos=["辱华", "炫富"],
        sensitive_triggers=["贫富差距", "特权", "崇洋媚外"],
        avoided_topics=[],
        self_censorship="低",
        social_circles=["工友圈", "老乡圈"],
        influence_level="普通用户",
        followed_kol_domains=["社会", "正能量"],
        social_activity="低",
        recent_experiences=["看到炫富视频感到愤怒"],
        emotional_baseline="低落",
        attitude_changes=["对贫富差距更不满"],
        memory_anchors=["看到劳动者互助的视频很感动"],
    ),
    PersonaArchetype(
        archetype_id="dy_sinking_market_hustler",
        name="下沉市场创业者",
        platform="douyin",
        description="小镇创业者或自由职业者，关注商机和赚钱",
        age_range=(25, 40), gender="male", occupation_category="小老板/自由职业",
        region="县城/乡镇", income_level="中等", education="高中/大专",
        political_tendency=6.0, consumerism=5.5, family_tradition=6.0,
        social_justice=4.5, tech_optimism=5.0,
        professional_domains=["商业", "创业"],
        information_sources=["抖音", "微信", "快手"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["创业", "赚钱", "社会新闻"],
        active_hours="全天",
        cultural_taboos=["割韭菜", "传销"],
        sensitive_triggers=["虚假项目", "经济下行"],
        avoided_topics=["政治敏感"],
        self_censorship="中等",
        social_circles=["商圈", "老乡圈"],
        influence_level="活跃分子",
        followed_kol_domains=["商业", "创业"],
        social_activity="高",
        recent_experiences=["尝试了一个新项目"],
        emotional_baseline="积极",
        attitude_changes=["对经济形势更关注"],
        memory_anchors=["第一次创业成功"],
    ),
]


# ---------------------------------------------------------------------------
# 汇总：按平台索引
# ---------------------------------------------------------------------------

PLATFORM_ARCHETYPES = {
    "bilibili": BILIBILI_ARCHETYPES,
    "xiaohongshu": XIAOHONGSHU_ARCHETYPES,
    "zhihu": ZHIHU_ARCHETYPES,
    "douyin": DOUYIN_ARCHETYPES,
}


def get_archetypes_for_platform(platform: str) -> list[PersonaArchetype]:
    """获取指定平台的人格原型列表"""
    return PLATFORM_ARCHETYPES.get(platform, [])


def get_random_archetypes(platform: str, count: int = 3) -> list[PersonaArchetype]:
    """从指定平台随机选择N个原型"""
    import random
    archetypes = get_archetypes_for_platform(platform)
    if not archetypes:
        return []
    # 如果要求数量超过原型数量，允许重复选择
    if count <= len(archetypes):
        return random.sample(archetypes, count)
    else:
        return [random.choice(archetypes) for _ in range(count)]


def archetype_to_dict(archetype: PersonaArchetype) -> dict:
    """将原型转换为dict用于LLM Prompt"""
    return {
        "archetype_id": archetype.archetype_id,
        "name": archetype.name,
        "platform": archetype.platform,
        "description": archetype.description,
        "L1_basic": {
            "age_range": f"{archetype.age_range[0]}-{archetype.age_range[1]}",
            "gender": archetype.gender,
            "occupation": archetype.occupation_category,
            "region": archetype.region,
            "income": archetype.income_level,
            "education": archetype.education,
        },
        "L2_values": {
            "political_tendency": archetype.political_tendency,
            "consumerism": archetype.consumerism,
            "family_tradition": archetype.family_tradition,
            "social_justice": archetype.social_justice,
            "tech_optimism": archetype.tech_optimism,
        },
        "L3_knowledge": {
            "professional_domains": archetype.professional_domains,
            "information_sources": archetype.information_sources,
            "cognitive_level": archetype.cognitive_level,
            "media_literacy": archetype.media_literacy,
        },
        "L4_behavior": {
            "expression_style": archetype.expression_style,
            "interaction_preference": archetype.interaction_preference,
            "content_preference": archetype.content_preference,
            "active_hours": archetype.active_hours,
        },
        "L5_correction": {
            "cultural_taboos": archetype.cultural_taboos,
            "sensitive_triggers": archetype.sensitive_triggers,
            "avoided_topics": archetype.avoided_topics,
            "self_censorship": archetype.self_censorship,
        },
        "L6_social": {
            "social_circles": archetype.social_circles,
            "influence_level": archetype.influence_level,
            "followed_kol_domains": archetype.followed_kol_domains,
            "social_activity": archetype.social_activity,
        },
        "L7_evolution": {
            "recent_experiences": archetype.recent_experiences,
            "emotional_baseline": archetype.emotional_baseline,
            "attitude_changes": archetype.attitude_changes,
            "memory_anchors": archetype.memory_anchors,
        },
    }
