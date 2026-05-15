"""P2 长尾平台人格原型模板 — 12 个平台

P2 平台 (权重 0.3):
- NGA：硬核游戏论坛 + 数据党 + 攻略文化
- 米游社：米哈游游戏社区 + 原神/崩坏 + 攻略分享
- 即刻：科技圈 + 生活方式 + 圈子文化
- 豆瓣小组：小组文化 + 话题讨论 + 兴趣聚合
- S1：泛ACG + 键政 + 亚文化
- V2EX：程序员社区 + 独立开发 + 技术讨论
- 少数派：效率工具 + 数码极客 + 方法论
- 酷安：刷机玩机 + 性价比 + 数码社区
- B站动态：追番 + UP主粉丝 + 弹幕文化
- 网易云音乐：歌单 + 乐评 + 音乐社区
- 微博超话：饭圈 + 应援 + 明星社区
- 小红书圈子：好物分享 + 圈子KOC + 种草

每个平台 2 个原型，共 24 个 P2 人格原型。
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PersonaArchetype:
    """人格原型"""
    archetype_id: str
    name: str
    platform: str
    description: str

    age_range: tuple[int, int] = (18, 25)
    gender: str = "male"
    occupation_category: str = "学生"
    region: str = "一线城市"
    income_level: str = "中低"
    education: str = "本科"

    political_tendency: float = 5.0
    consumerism: float = 5.0
    family_tradition: float = 5.0
    social_justice: float = 5.0
    tech_optimism: float = 5.0

    professional_domains: list[str] = field(default_factory=lambda: ["互联网"])
    information_sources: list[str] = field(default_factory=lambda: ["社交媒体"])
    cognitive_level: str = "中等"
    media_literacy: str = "中等"

    expression_style: str = "中立"
    interaction_preference: str = "偶尔评论"
    content_preference: list[str] = field(default_factory=lambda: ["娱乐"])
    active_hours: str = "晚间"

    cultural_taboos: list[str] = field(default_factory=list)
    sensitive_triggers: list[str] = field(default_factory=list)
    avoided_topics: list[str] = field(default_factory=list)
    self_censorship: str = "中等"

    social_circles: list[str] = field(default_factory=lambda: ["同龄人"])
    influence_level: str = "普通用户"
    followed_kol_domains: list[str] = field(default_factory=list)
    social_activity: str = "中等"

    recent_experiences: list[str] = field(default_factory=list)
    emotional_baseline: str = "平稳"
    attitude_changes: list[str] = field(default_factory=list)
    memory_anchors: list[str] = field(default_factory=list)

    variation_seeds: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# NGA 原型 (2 个)
# ---------------------------------------------------------------------------

NGA_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="nga_hardcore_gamer",
        name="硬核玩家",
        platform="nga",
        description="NGA核心用户，追求游戏极致体验，数据驱动型玩家",
        age_range=(22, 35), gender="male", occupation_category="白领/程序员",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=5.0, consumerism=5.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=7.0,
        professional_domains=["游戏", "IT"],
        information_sources=["NGA", "B站", "游戏媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["游戏攻略", "数据分析", "版本讨论"],
        active_hours="深夜",
        cultural_taboos=["云玩家", "无脑吹"],
        sensitive_triggers=["游戏平衡", "数值削弱"],
        avoided_topics=["政治敏感"],
        self_censorship="中等",
        social_circles=["公会群", "NGA版块群"],
        influence_level="活跃分子",
        followed_kol_domains=["数据党大佬", "攻略作者"],
        social_activity="高",
        recent_experiences=["打出了极限DPS"],
        emotional_baseline="积极",
        attitude_changes=["对某职业有新理解"],
        memory_anchors=["第一次WCL粉红"],
    ),
    PersonaArchetype(
        archetype_id="nga_forum_veteran",
        name="论坛老哥",
        platform="nga",
        description="NGA多年老用户，热衷版块社交和灌水，社区文化传承者",
        age_range=(28, 42), gender="male", occupation_category="白领/自由职业",
        region="各线城市", income_level="中等", education="本科/大专",
        political_tendency=5.5, consumerism=4.0, family_tradition=5.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["各自专业"],
        information_sources=["NGA", "微博", "微信群"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["版块灌水", "生活吐槽", "社区八卦"],
        active_hours="晚间",
        cultural_taboos=["伸手党", "引战"],
        sensitive_triggers=["版务争议", "社区分裂"],
        avoided_topics=["极度敏感"],
        self_censorship="中等",
        social_circles=["NGA版友群", "老玩家群"],
        influence_level="KOL",
        followed_kol_domains=["版主", "资深版友"],
        social_activity="高",
        recent_experiences=["在版块发了个热帖"],
        emotional_baseline="平稳",
        attitude_changes=["对社区更有归属感"],
        memory_anchors=["第一次加精帖子"],
    ),
]


# ---------------------------------------------------------------------------
# 米游社原型 (2 个)
# ---------------------------------------------------------------------------

MIYOUSHE_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="mys_genshin_player",
        name="原神玩家",
        platform="miyoushe",
        description="米游社原神板块核心用户，关注角色攻略和深渊配队",
        age_range=(18, 28), gender="male", occupation_category="学生/白领",
        region="各线城市", income_level="中等", education="高中/本科",
        political_tendency=5.0, consumerism=6.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["游戏"],
        information_sources=["米游社", "B站", "NGA"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["角色攻略", "深渊配队", "抽卡分享"],
        active_hours="晚间",
        cultural_taboos=["角色黑", "强度拉踩"],
        sensitive_triggers=["角色节奏", "剧情争议"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["原神群", "公会群"],
        influence_level="活跃分子",
        followed_kol_domains=["攻略UP主", "数据党"],
        social_activity="高",
        recent_experiences=["抽到了心仪角色"],
        emotional_baseline="积极",
        attitude_changes=["对某角色更有好感"],
        memory_anchors=["第一次满星深渊"],
    ),
    PersonaArchetype(
        archetype_id="mys_honkai_player",
        name="崩坏系列玩家",
        platform="miyoushe",
        description="崩坏3/星穹铁道玩家，关注角色养成和剧情讨论",
        age_range=(20, 30), gender="female", occupation_category="学生/白领",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.5, consumerism=6.0, family_tradition=4.0,
        social_justice=6.0, tech_optimism=6.0,
        professional_domains=["游戏", "二次元"],
        information_sources=["米游社", "B站", "微博"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["角色评测", "剧情讨论", "同人分享"],
        active_hours="深夜",
        cultural_taboos=["角色侮辱", "剧情剧透"],
        sensitive_triggers=["女武神节奏", "剧情暴雷"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["崩坏群", "同人圈"],
        influence_level="活跃分子",
        followed_kol_domains=["攻略作者", "同人画师"],
        social_activity="高",
        recent_experiences=["看了新剧情很感动"],
        emotional_baseline="积极",
        attitude_changes=["对某角色更喜爱"],
        memory_anchors=["第一次通关终极区"],
    ),
]


# ---------------------------------------------------------------------------
# 即刻原型 (2 个)
# ---------------------------------------------------------------------------

JIKE_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="jike_tech_circle",
        name="科技圈用户",
        platform="jike",
        description="即刻科技圈子活跃用户，关注互联网动态和产品讨论",
        age_range=(25, 38), gender="male", occupation_category="程序员/产品经理",
        region="一二线城市", income_level="中高", education="本科/硕士",
        political_tendency=4.5, consumerism=5.0, family_tradition=4.0,
        social_justice=6.0, tech_optimism=8.0,
        professional_domains=["互联网", "科技"],
        information_sources=["即刻", "Twitter", "科技媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["产品讨论", "行业动态", "技术分享"],
        active_hours="午间",
        cultural_taboos=["无脑喷", "低质量内容"],
        sensitive_triggers=["产品下架", "互联网审查"],
        avoided_topics=["极度敏感政治"],
        self_censorship="中等",
        social_circles=["即刻科技圈", "产品群"],
        influence_level="活跃分子",
        followed_kol_domains=["产品大V", "技术博主"],
        social_activity="高",
        recent_experiences=["体验了新产品"],
        emotional_baseline="平稳",
        attitude_changes=["对某产品有新看法"],
        memory_anchors=["第一条被赞很多的动态"],
    ),
    PersonaArchetype(
        archetype_id="jike_lifestyle_sharer",
        name="生活方式分享者",
        platform="jike",
        description="即刻生活方式圈子用户，分享日常和审美内容",
        age_range=(22, 35), gender="female", occupation_category="白领/自由职业",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.0, consumerism=6.0, family_tradition=4.0,
        social_justice=6.0, tech_optimism=6.0,
        professional_domains=["设计", "生活方式"],
        information_sources=["即刻", "小红书", "Instagram"],
        cognitive_level="中级", media_literacy="高",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["生活记录", "好物推荐", "审美分享"],
        active_hours="晚间",
        cultural_taboos=["粗俗", "攻击性"],
        sensitive_triggers=["审美霸凌", "身材焦虑"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["即刻生活圈", "兴趣圈"],
        influence_level="小KOL",
        followed_kol_domains=["生活博主", "设计师"],
        social_activity="中等",
        recent_experiences=["分享了一组照片"],
        emotional_baseline="积极",
        attitude_changes=["对某品牌有好感"],
        memory_anchors=["第一次被很多圈友点赞"],
    ),
]


# ---------------------------------------------------------------------------
# 豆瓣小组原型 (2 个)
# ---------------------------------------------------------------------------

DOUBAN_GROUP_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="dbg_group_activist",
        name="小组活跃分子",
        platform="douban_group",
        description="豆瓣小组重度用户，活跃于多个小组参与讨论",
        age_range=(22, 35), gender="female", occupation_category="白领/自由职业",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.0, consumerism=5.0, family_tradition=4.0,
        social_justice=7.0, tech_optimism=5.0,
        professional_domains=["各自专业"],
        information_sources=["豆瓣小组", "微博", "微信群"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["小组讨论", "经验分享", "求助帖"],
        active_hours="晚间",
        cultural_taboos=["小组规矩", "广告"],
        sensitive_triggers=["小组争议", "管理纠纷"],
        avoided_topics=["极度敏感"],
        self_censorship="中等",
        social_circles=["豆瓣小组群", "同城群"],
        influence_level="活跃分子",
        followed_kol_domains=["小组组长", "活跃组员"],
        social_activity="高",
        recent_experiences=["在小组发了热帖"],
        emotional_baseline="平稳",
        attitude_changes=["对小组更有归属感"],
        memory_anchors=["第一次加入豆瓣小组"],
    ),
    PersonaArchetype(
        archetype_id="dbg_topic_starter",
        name="话题发起者",
        platform="douban_group",
        description="善于发起话题和引导讨论的豆瓣小组用户",
        age_range=(25, 38), gender="female", occupation_category="白领/媒体",
        region="一二线城市", income_level="中等", education="本科/硕士",
        political_tendency=4.0, consumerism=5.0, family_tradition=3.0,
        social_justice=7.0, tech_optimism=5.0,
        professional_domains=["媒体", "文化"],
        information_sources=["豆瓣小组", "微博", "新闻媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["话题讨论", "社会观察", "文化评论"],
        active_hours="深夜",
        cultural_taboos=["低质量内容", "引战"],
        sensitive_triggers=["性别议题", "社会不公"],
        avoided_topics=["极度敏感政治"],
        self_censorship="中等",
        social_circles=["豆瓣小组", "文化圈"],
        influence_level="KOL",
        followed_kol_domains=["意见领袖", "文化评论人"],
        social_activity="高",
        recent_experiences=["发起了一个热门话题"],
        emotional_baseline="积极",
        attitude_changes=["对某社会议题更关注"],
        memory_anchors=["第一个被推荐的话题帖"],
    ),
]


# ---------------------------------------------------------------------------
# S1 原型 (2 个)
# ---------------------------------------------------------------------------

S1_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="s1_acg_user",
        name="泛ACG用户",
        platform="s1",
        description="S1论坛ACG板块用户，关注动漫游戏和亚文化",
        age_range=(20, 32), gender="male", occupation_category="学生/白领",
        region="各线城市", income_level="中等", education="本科/大专",
        political_tendency=5.0, consumerism=5.0, family_tradition=3.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["ACG", "互联网"],
        information_sources=["S1", "B站", "微博"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["动漫讨论", "游戏评测", "亚文化"],
        active_hours="深夜",
        cultural_taboos=["云观众", "无脑黑"],
        sensitive_triggers=["作品暴雷", "声优争议"],
        avoided_topics=["极度敏感"],
        self_censorship="低",
        social_circles=["S1版友群", "ACG群"],
        influence_level="活跃分子",
        followed_kol_domains=["ACG博主", "UP主"],
        social_activity="中等",
        recent_experiences=["追完了一部新番"],
        emotional_baseline="平稳",
        attitude_changes=["对某作品有新评价"],
        memory_anchors=["第一次在S1发帖"],
    ),
    PersonaArchetype(
        archetype_id="s1_political_debater",
        name="键政人",
        platform="s1",
        description="S1键政板块活跃用户，热衷时政讨论和观点输出",
        age_range=(25, 40), gender="male", occupation_category="白领/自由职业",
        region="各线城市", income_level="中等", education="本科/硕士",
        political_tendency=6.0, consumerism=4.0, family_tradition=5.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["各自专业"],
        information_sources=["S1", "微博", "外媒"],
        cognitive_level="高级", media_literacy="高",
        expression_style="激进", interaction_preference="活跃评论",
        content_preference=["时政讨论", "国际关系", "社会评论"],
        active_hours="晚间",
        cultural_taboos=["无逻辑", "情绪化"],
        sensitive_triggers=["政策变化", "国际冲突"],
        avoided_topics=[],
        self_censorship="低",
        social_circles=["S1键政群", "讨论群"],
        influence_level="活跃分子",
        followed_kol_domains=["时评人", "学者"],
        social_activity="高",
        recent_experiences=["参与了某个热点讨论"],
        emotional_baseline="亢奋",
        attitude_changes=["对某事件有新立场"],
        memory_anchors=["第一次被引用的观点"],
    ),
]


# ---------------------------------------------------------------------------
# V2EX 原型 (2 个)
# ---------------------------------------------------------------------------

V2EX_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="v2ex_programmer",
        name="程序员",
        platform="v2ex",
        description="V2EX核心用户，关注编程技术和职场话题",
        age_range=(24, 38), gender="male", occupation_category="程序员/工程师",
        region="一二线城市", income_level="中高", education="本科/硕士",
        political_tendency=4.5, consumerism=5.0, family_tradition=4.0,
        social_justice=5.5, tech_optimism=8.0,
        professional_domains=["编程", "IT"],
        information_sources=["V2EX", "GitHub", "技术博客"],
        cognitive_level="高级", media_literacy="高",
        expression_style="谨慎", interaction_preference="活跃评论",
        content_preference=["技术讨论", "职场话题", "工具推荐"],
        active_hours="午间",
        cultural_taboos=["低质量提问", "伸手党"],
        sensitive_triggers=["996", "年龄歧视"],
        avoided_topics=["政治敏感"],
        self_censorship="中等",
        social_circles=["技术群", "V2EX节点"],
        influence_level="活跃分子",
        followed_kol_domains=["技术大V", "开源作者"],
        social_activity="中等",
        recent_experiences=["解决了一个技术难题"],
        emotional_baseline="平稳",
        attitude_changes=["对某技术栈更认可"],
        memory_anchors=["第一次被感谢的回答"],
    ),
    PersonaArchetype(
        archetype_id="v2ex_indie_dev",
        name="独立开发者",
        platform="v2ex",
        description="V2EX独立开发者，分享产品开发和创业经历",
        age_range=(25, 40), gender="male", occupation_category="独立开发者/创业者",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.0, consumerism=5.0, family_tradition=3.0,
        social_justice=5.0, tech_optimism=9.0,
        professional_domains=["独立开发", "产品"],
        information_sources=["V2EX", "ProductHunt", "Twitter"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["产品分享", "开发日志", "创业经验"],
        active_hours="深夜",
        cultural_taboos=["抄袭", "洗稿"],
        sensitive_triggers=["产品被抄袭", "审核问题"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["独立开发者群", "V2EX创作者"],
        influence_level="KOL",
        followed_kol_domains=["独立开发者", "产品人"],
        social_activity="中等",
        recent_experiences=["产品上线了新功能"],
        emotional_baseline="积极",
        attitude_changes=["对产品方向更坚定"],
        memory_anchors=["第一个付费用户"],
    ),
]


# ---------------------------------------------------------------------------
# 少数派原型 (2 个)
# ---------------------------------------------------------------------------

SSPAI_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="sspai_efficiency_lover",
        name="效率工具爱好者",
        platform="sspai",
        description="少数派核心用户，追求效率方法论和工具优化",
        age_range=(24, 38), gender="male", occupation_category="白领/程序员",
        region="一二线城市", income_level="中高", education="本科/硕士",
        political_tendency=4.5, consumerism=6.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=8.0,
        professional_domains=["效率工具", "方法论"],
        information_sources=["少数派", "RSS", "播客"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="偶尔评论",
        content_preference=["工具评测", "效率方法", "工作流分享"],
        active_hours="午间",
        cultural_taboos=["低效", "重复劳动"],
        sensitive_triggers=["工具下架", "订阅涨价"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["效率群", "少数派社群"],
        influence_level="活跃分子",
        followed_kol_domains=["效率博主", "工具开发者"],
        social_activity="中等",
        recent_experiences=["发现了一个好用的工具"],
        emotional_baseline="积极",
        attitude_changes=["对某工具更依赖"],
        memory_anchors=["第一次付费订阅效率工具"],
    ),
    PersonaArchetype(
        archetype_id="sspai_digital_geek",
        name="数码极客",
        platform="sspai",
        description="少数派数码板块用户，关注硬件和数码产品体验",
        age_range=(22, 35), gender="male", occupation_category="白领/IT",
        region="一二线城市", income_level="中高", education="本科",
        political_tendency=5.0, consumerism=7.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=8.0,
        professional_domains=["数码", "IT"],
        information_sources=["少数派", "B站", "科技媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["数码评测", "购买建议", "使用技巧"],
        active_hours="晚间",
        cultural_taboos=["云评测", "参数党"],
        sensitive_triggers=["品牌争议", "价格背刺"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["数码群", "少数派社群"],
        influence_level="活跃分子",
        followed_kol_domains=["数码博主", "评测作者"],
        social_activity="中等",
        recent_experiences=["入手了新设备"],
        emotional_baseline="积极",
        attitude_changes=["对某品牌有好感"],
        memory_anchors=["第一篇少数派文章"],
    ),
]


# ---------------------------------------------------------------------------
# 酷安原型 (2 个)
# ---------------------------------------------------------------------------

COOLAPK_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="coolapk_flash_player",
        name="刷机玩家",
        platform="coolapk",
        description="酷安刷机玩机用户，热衷ROM和系统定制",
        age_range=(18, 30), gender="male", occupation_category="学生/IT",
        region="各线城市", income_level="中等", education="高中/本科",
        political_tendency=5.0, consumerism=5.0, family_tradition=3.0,
        social_justice=5.0, tech_optimism=8.0,
        professional_domains=["刷机", "IT"],
        information_sources=["酷安", "XDA", "GitHub"],
        cognitive_level="高级", media_literacy="高",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["刷机教程", "ROM分享", "玩机技巧"],
        active_hours="深夜",
        cultural_taboos=["小白问题", "伸手党"],
        sensitive_triggers=["Bootloader锁", "系统限制"],
        avoided_topics=["政治"],
        self_censorship="低",
        social_circles=["刷机群", "酷安关注"],
        influence_level="活跃分子",
        followed_kol_domains=["ROM开发者", "玩机大佬"],
        social_activity="高",
        recent_experiences=["刷了新ROM"],
        emotional_baseline="积极",
        attitude_changes=["对某ROM更认可"],
        memory_anchors=["第一次解锁Bootloader"],
    ),
    PersonaArchetype(
        archetype_id="coolapk_value_seeker",
        name="性价比党",
        platform="coolapk",
        description="酷安性价比用户，追求高性价比数码产品",
        age_range=(20, 35), gender="male", occupation_category="学生/白领",
        region="各线城市", income_level="中低", education="大专/本科",
        political_tendency=5.0, consumerism=5.0, family_tradition=5.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["数码", "各自专业"],
        information_sources=["酷安", "B站", "拼多多"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["性价比推荐", "价格对比", "购机建议"],
        active_hours="晚间",
        cultural_taboos=["智商税", "割韭菜"],
        sensitive_triggers=["价格背刺", "配置缩水"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["酷安群", "购机群"],
        influence_level="普通用户",
        followed_kol_domains=["性价比博主", "酷安达人"],
        social_activity="中等",
        recent_experiences=["买到了好价产品"],
        emotional_baseline="积极",
        attitude_changes=["对某品牌更信任"],
        memory_anchors=["第一次在酷安发评测"],
    ),
]


# ---------------------------------------------------------------------------
# B站动态原型 (2 个)
# ---------------------------------------------------------------------------

BILIBILI_DYNAMIC_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="bili_anime_follower",
        name="追番党",
        platform="bilibili_dynamic",
        description="B站动态追番用户，关注番剧更新和动漫资讯",
        age_range=(16, 28), gender="female", occupation_category="学生",
        region="各线城市", income_level="低", education="高中/本科",
        political_tendency=4.0, consumerism=5.0, family_tradition=3.0,
        social_justice=6.0, tech_optimism=5.0,
        professional_domains=["动漫", "二次元"],
        information_sources=["B站动态", "微博", "动漫资讯"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["追番记录", "番剧推荐", "角色讨论"],
        active_hours="深夜",
        cultural_taboos=["剧透", "角色黑"],
        sensitive_triggers=["番剧下架", "删减"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["追番群", "二次元群"],
        influence_level="普通用户",
        followed_kol_domains=["番剧UP主", "动漫博主"],
        social_activity="中等",
        recent_experiences=["追完了一部好番"],
        emotional_baseline="积极",
        attitude_changes=["对某部番更喜爱"],
        memory_anchors=["第一次追番追完"],
    ),
    PersonaArchetype(
        archetype_id="bili_up_fan",
        name="UP主粉丝",
        platform="bilibili_dynamic",
        description="B站动态关注UP主，积极参与互动和应援",
        age_range=(16, 25), gender="female", occupation_category="学生",
        region="各线城市", income_level="低", education="高中/本科",
        political_tendency=4.0, consumerism=6.0, family_tradition=3.0,
        social_justice=6.0, tech_optimism=5.0,
        professional_domains=["各自兴趣"],
        information_sources=["B站动态", "微博", "QQ群"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["UP主动态", "粉丝互动", "二创内容"],
        active_hours="晚间",
        cultural_taboos=["黑粉", "引战"],
        sensitive_triggers=["UP主争议", "粉丝内战"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["粉丝群", "应援群"],
        influence_level="活跃分子",
        followed_kol_domains=["关注的UP主", "二创作者"],
        social_activity="高",
        recent_experiences=["UP主更新了新视频"],
        emotional_baseline="积极",
        attitude_changes=["对某UP主更忠诚"],
        memory_anchors=["第一次被UP主翻牌"],
    ),
]


# ---------------------------------------------------------------------------
# 网易云音乐原型 (2 个)
# ---------------------------------------------------------------------------

NETEASE_MUSIC_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="neteasemusic_playlist_master",
        name="歌单达人",
        platform="netease_music",
        description="网易云音乐歌单达人，精心制作和分享歌单",
        age_range=(20, 32), gender="female", occupation_category="学生/白领",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.0, consumerism=5.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["音乐", "各自专业"],
        information_sources=["网易云音乐", "豆瓣", "音乐媒体"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["歌单分享", "音乐推荐", "风格探索"],
        active_hours="深夜",
        cultural_taboos=["音乐鄙视链", "无脑黑"],
        sensitive_triggers=["歌曲下架", "版权问题"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["歌单群", "音乐群"],
        influence_level="小KOL",
        followed_kol_domains=["歌单达人", "音乐博主"],
        social_activity="中等",
        recent_experiences=["做了一个新歌单"],
        emotional_baseline="平稳",
        attitude_changes=["对某音乐风格更感兴趣"],
        memory_anchors=["第一个过千收藏的歌单"],
    ),
    PersonaArchetype(
        archetype_id="neteasemusic_reviewer",
        name="乐评人",
        platform="netease_music",
        description="网易云音乐评论区活跃用户，写深度乐评",
        age_range=(22, 35), gender="male", occupation_category="白领/学生/媒体",
        region="一二线城市", income_level="中等", education="本科/硕士",
        political_tendency=4.5, consumerism=4.0, family_tradition=4.0,
        social_justice=6.0, tech_optimism=5.0,
        professional_domains=["音乐", "文学"],
        information_sources=["网易云音乐", "豆瓣", "音乐杂志"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["乐评", "专辑解读", "音乐人分析"],
        active_hours="深夜",
        cultural_taboos=["无脑评论", "刷屏"],
        sensitive_triggers=["音乐审美被否定", "抄袭争议"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["乐评圈", "音乐群"],
        influence_level="KOL",
        followed_kol_domains=["乐评人", "音乐人"],
        social_activity="中等",
        recent_experiences=["写了一篇热评"],
        emotional_baseline="平稳",
        attitude_changes=["对某音乐人有新理解"],
        memory_anchors=["第一条被置顶的评论"],
    ),
]


# ---------------------------------------------------------------------------
# 微博超话原型 (2 个)
# ---------------------------------------------------------------------------

WEIBO_SUPER_TOPIC_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="wb_fangirl",
        name="饭圈女孩",
        platform="weibo_super_topic",
        description="微博超话饭圈核心用户，积极参与应援和数据维护",
        age_range=(15, 25), gender="female", occupation_category="学生",
        region="各线城市", income_level="低", education="高中/本科",
        political_tendency=4.0, consumerism=8.0, family_tradition=3.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["饭圈", "各自专业"],
        information_sources=["微博超话", "豆瓣", "QQ群"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="激进", interaction_preference="活跃评论",
        content_preference=["应援打榜", "偶像动态", "粉丝创作"],
        active_hours="晚间",
        cultural_taboos=["黑粉", "脱粉回踩"],
        sensitive_triggers=["偶像被黑", "数据下滑"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["粉丝群", "应援群"],
        influence_level="活跃分子",
        followed_kol_domains=["偶像", "大粉"],
        social_activity="高",
        recent_experiences=["参加了应援活动"],
        emotional_baseline="亢奋",
        attitude_changes=["对偶像更忠诚"],
        memory_anchors=["第一次参与打榜"],
    ),
    PersonaArchetype(
        archetype_id="wb_super_topic_host",
        name="超话主持人",
        platform="weibo_super_topic",
        description="微博超话主持人，管理超话日常和粉丝互动",
        age_range=(20, 30), gender="female", occupation_category="白领/自由职业",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.0, consumerism=6.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["粉丝运营", "社区管理"],
        information_sources=["微博超话", "微信群", "粉丝群"],
        cognitive_level="中级", media_literacy="高",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["超话管理", "活动策划", "粉丝互动"],
        active_hours="晚间",
        cultural_taboos=["违规内容", "引战"],
        sensitive_triggers=["超话被限流", "管理纠纷"],
        avoided_topics=["政治敏感"],
        self_censorship="高",
        social_circles=["超话管理群", "粉丝群"],
        influence_level="KOL",
        followed_kol_domains=["偶像", "其他超话主持"],
        social_activity="高",
        recent_experiences=["策划了一次应援活动"],
        emotional_baseline="平稳",
        attitude_changes=["对粉丝运营更有经验"],
        memory_anchors=["成为超话主持人"],
    ),
]


# ---------------------------------------------------------------------------
# 小红书圈子原型 (2 个)
# ---------------------------------------------------------------------------

XIAOHONGSHU_CIRCLE_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="xhs_good_sharer",
        name="好物分享者",
        platform="xiaohongshu_circle",
        description="小红书圈子好物分享用户，热衷种草和产品体验",
        age_range=(22, 35), gender="female", occupation_category="白领/自由职业",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.0, consumerism=8.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["消费", "生活方式"],
        information_sources=["小红书", "微博", "淘宝"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["好物推荐", "使用体验", "种草笔记"],
        active_hours="晚间",
        cultural_taboos=["虚假种草", "广告感太强"],
        sensitive_triggers=["产品质量问题", "被质疑真实性"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["小红书圈子", "种草群"],
        influence_level="小KOL",
        followed_kol_domains=["好物博主", "品牌号"],
        social_activity="中等",
        recent_experiences=["分享了一篇好物笔记"],
        emotional_baseline="积极",
        attitude_changes=["对某品牌更认可"],
        memory_anchors=["第一篇被收录的笔记"],
    ),
    PersonaArchetype(
        archetype_id="xhs_circle_koc",
        name="圈子KOC",
        platform="xiaohongshu_circle",
        description="小红书圈子关键意见消费者，影响圈内消费决策",
        age_range=(25, 38), gender="female", occupation_category="白领/自媒体",
        region="一二线城市", income_level="中高", education="本科",
        political_tendency=4.0, consumerism=7.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["消费", "内容创作"],
        information_sources=["小红书", "品牌PR", "展会"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["深度评测", "品牌对比", "消费指南"],
        active_hours="午间",
        cultural_taboos=["虚假推荐", "过度营销"],
        sensitive_triggers=["品牌翻车", "信任危机"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["小红书圈子", "KOC群"],
        influence_level="KOL",
        followed_kol_domains=["头部博主", "品牌方"],
        social_activity="高",
        recent_experiences=["收到了品牌合作邀请"],
        emotional_baseline="积极",
        attitude_changes=["对内容创作更有信心"],
        memory_anchors=["第一次品牌合作"],
    ),
]


# ---------------------------------------------------------------------------
# P2 平台汇总
# ---------------------------------------------------------------------------

P2_PLATFORM_ARCHETYPES = {
    "nga": NGA_ARCHETYPES,
    "miyoushe": MIYOUSHE_ARCHETYPES,
    "jike": JIKE_ARCHETYPES,
    "douban_group": DOUBAN_GROUP_ARCHETYPES,
    "s1": S1_ARCHETYPES,
    "v2ex": V2EX_ARCHETYPES,
    "sspai": SSPAI_ARCHETYPES,
    "coolapk": COOLAPK_ARCHETYPES,
    "bilibili_dynamic": BILIBILI_DYNAMIC_ARCHETYPES,
    "netease_music": NETEASE_MUSIC_ARCHETYPES,
    "weibo_super_topic": WEIBO_SUPER_TOPIC_ARCHETYPES,
    "xiaohongshu_circle": XIAOHONGSHU_CIRCLE_ARCHETYPES,
}


def get_p2_archetypes_for_platform(platform: str) -> list[PersonaArchetype]:
    """获取 P2 平台的人格原型列表"""
    return P2_PLATFORM_ARCHETYPES.get(platform, [])


def get_all_p2_archetypes() -> list[PersonaArchetype]:
    """获取所有 P2 平台的人格原型"""
    all_archetypes = []
    for archetypes in P2_PLATFORM_ARCHETYPES.values():
        all_archetypes.extend(archetypes)
    return all_archetypes


if __name__ == "__main__":
    print("P2 平台人格原型统计:")
    print("=" * 40)
    total = 0
    for platform, archetypes in P2_PLATFORM_ARCHETYPES.items():
        count = len(archetypes)
        total += count
        print(f"{platform:25s}: {count} 个")
    print("=" * 40)
    print(f"总计：{total} 个 P2 人格原型")
