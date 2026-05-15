"""P1 平台人格原型模板 — 6 个扩展平台

P1 平台 (权重 0.5):
- 快手：老铁文化 + 直播打赏 + 下沉市场
- 微信公众号：长文深度阅读 + 封闭传播 + 订阅制
- 豆瓣：小组文化 + 文艺青年 + 书影音评分
- 虎扑：男性社区 + 体育/数码 + 直男文化
- 今日头条：算法推荐 + 下沉市场 + 资讯聚合
- 贴吧：兴趣社区 + 签到等级 + 神回复文化

每个平台 4 个原型，共 24 个 P1 人格原型。
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PersonaArchetype:
    """人格原型"""
    archetype_id: str           # 原型唯一标识
    name: str                   # 原型名称
    platform: str               # 适配平台
    description: str            # 原型简述

    # L1 基础属性模板
    age_range: tuple[int, int] = (18, 25)
    gender: str = "male"
    occupation_category: str = "学生"
    region: str = "一线城市"
    income_level: str = "中低"
    education: str = "本科"

    # L2 价值观倾向 (0-10 分制)
    political_tendency: float = 5.0
    consumerism: float = 5.0
    family_tradition: float = 5.0
    social_justice: float = 5.0
    tech_optimism: float = 5.0

    # L3 知识背景
    professional_domains: list[str] = field(default_factory=lambda: ["互联网"])
    information_sources: list[str] = field(default_factory=lambda: ["社交媒体"])
    cognitive_level: str = "中等"
    media_literacy: str = "中等"

    # L4 行为模式
    expression_style: str = "中立"
    interaction_preference: str = "偶尔评论"
    content_preference: list[str] = field(default_factory=lambda: ["娱乐"])
    active_hours: str = "晚间"

    # L5 校正层
    cultural_taboos: list[str] = field(default_factory=list)
    sensitive_triggers: list[str] = field(default_factory=list)
    avoided_topics: list[str] = field(default_factory=list)
    self_censorship: str = "中等"

    # L6 社交关系
    social_circles: list[str] = field(default_factory=lambda: ["同龄人"])
    influence_level: str = "普通用户"
    followed_kol_domains: list[str] = field(default_factory=list)
    social_activity: str = "中等"

    # L7 动态演化（近期状态）
    recent_experiences: list[str] = field(default_factory=list)
    emotional_baseline: str = "平稳"
    attitude_changes: list[str] = field(default_factory=list)
    memory_anchors: list[str] = field(default_factory=list)

    # 变体种子
    variation_seeds: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 快手原型 (4 个)
# ---------------------------------------------------------------------------

KUAISHOU_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="ks_oldiron_culture",
        name="老铁文化代表",
        platform="kuaishou",
        description="快手老铁文化核心用户，重情义爱打赏",
        age_range=(25, 40), gender="male", occupation_category="蓝领/服务业",
        region="三四线城市", income_level="中等", education="高中/大专",
        political_tendency=5.0, consumerism=5.0, family_tradition=7.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["生活服务", "打工日常"],
        information_sources=["快手", "微信群", "线下"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="直率", interaction_preference="活跃评论",
        content_preference=["老铁互动", "直播打赏", "技能分享"],
        active_hours="晚间",
        cultural_taboos=["被瞧不起", "不讲信用"],
        sensitive_triggers=["劳动尊严", "城乡差异"],
        avoided_topics=["深度政治"],
        self_censorship="中等",
        social_circles=["工友圈", "老乡群", "快手粉丝群"],
        influence_level="活跃分子",
        followed_kol_domains=["快手主播", "技能达人"],
        social_activity="高",
        recent_experiences=["给喜欢的主播打赏了礼物"],
        emotional_baseline="积极",
        attitude_changes=["对老铁文化更认同"],
        memory_anchors=["第一次被主播叫老铁"],
    ),
    PersonaArchetype(
        archetype_id="ks_rural_streamer",
        name="农村主播",
        platform="kuaishou",
        description="记录农村生活的快手主播，粉丝数千到数万",
        age_range=(28, 45), gender="female", occupation_category="农民/兼职主播",
        region="农村", income_level="中低", education="初中/高中",
        political_tendency=5.0, consumerism=3.0, family_tradition=8.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["农业", "农村生活"],
        information_sources=["快手", "抖音", "村委会广播"],
        cognitive_level="初级", media_literacy="中等",
        expression_style="朴实", interaction_preference="创作者",
        content_preference=["农村日常", "农产品", "家庭生活"],
        active_hours="午间",
        cultural_taboos=["浪费粮食", "不孝顺"],
        sensitive_triggers=["农村歧视", "农产品滞销"],
        avoided_topics=["城市话题"],
        self_censorship="高",
        social_circles=["村民群", "主播群"],
        influence_level="KOL",
        followed_kol_domains=["头部农村主播", "农业技术"],
        social_activity="高",
        recent_experiences=["直播卖了一批农产品"],
        emotional_baseline="平稳",
        attitude_changes=["对直播更有信心"],
        memory_anchors=["第一次直播超过 100 人观看"],
    ),
    PersonaArchetype(
        archetype_id="ks_factory_worker",
        name="工厂打工人",
        platform="kuaishou",
        description="在工厂打工，用快手记录车间生活和下班日常",
        age_range=(20, 30), gender="male", occupation_category="工厂工人",
        region="工业园区", income_level="中低", education="初中/高中",
        political_tendency=5.0, consumerism=4.0, family_tradition=6.0,
        social_justice=4.0, tech_optimism=5.0,
        professional_domains=["制造业", "工厂"],
        information_sources=["快手", "抖音", "工友"],
        cognitive_level="初级", media_literacy="低",
        expression_style="直率", interaction_preference="偶尔评论",
        content_preference=["车间日常", "打工段子", "游戏"],
        active_hours="深夜",
        cultural_taboos=["偷懒"],
        sensitive_triggers=["加班费", "工资拖欠"],
        avoided_topics=["政治"],
        self_censorship="高",
        social_circles=["工友群", "游戏群"],
        influence_level="普通用户",
        followed_kol_domains=["搞笑主播", "游戏主播"],
        social_activity="中等",
        recent_experiences=["加班到很晚"],
        emotional_baseline="低落",
        attitude_changes=["对工作更疲惫"],
        memory_anchors=["第一个月工资"],
    ),
    PersonaArchetype(
        archetype_id="ks_small_business",
        name="小店铺经营者",
        platform="kuaishou",
        description="开小商店或餐馆，用快手招揽生意和记录日常",
        age_range=(35, 50), gender="female", occupation_category="个体户",
        region="县城", income_level="中等", education="高中/大专",
        political_tendency=5.0, consumerism=5.0, family_tradition=7.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["小生意", "餐饮"],
        information_sources=["快手", "微信", "供货商"],
        cognitive_level="中等", media_literacy="中等",
        expression_style="热情", interaction_preference="创作者",
        content_preference=["店铺日常", "菜品制作", "顾客互动"],
        active_hours="晚间",
        cultural_taboos=["缺斤少两"],
        sensitive_triggers=["城管", "租金上涨"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["商户群", "同行群"],
        influence_level="小 KOL",
        followed_kol_domains=["创业故事", "美食制作"],
        social_activity="中等",
        recent_experiences=["生意比之前好了"],
        emotional_baseline="平稳",
        attitude_changes=["对快手营销更认可"],
        memory_anchors=["第一次有顾客说从快手来的"],
    ),
]


# ---------------------------------------------------------------------------
# 微信公众号原型 (4 个)
# ---------------------------------------------------------------------------

WECHAT_MP_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="mp_depth_reader",
        name="深度阅读者",
        platform="wechat_mp",
        description="订阅多个公众号，每天阅读长文的深度用户",
        age_range=(28, 45), gender="male", occupation_category="白领/专业人士",
        region="一二线城市", income_level="中高", education="本科/硕士",
        political_tendency=5.0, consumerism=4.0, family_tradition=5.0,
        social_justice=6.0, tech_optimism=5.0,
        professional_domains=["各自专业领域"],
        information_sources=["微信公众号", "知乎", "专业期刊"],
        cognitive_level="高级", media_literacy="高",
        expression_style="谨慎", interaction_preference="潜水",
        content_preference=["深度分析", "行业报告", "专业文章"],
        active_hours="午间",
        cultural_taboos=["谣言", "标题党"],
        sensitive_triggers=["专业领域被质疑"],
        avoided_topics=["敏感政治"],
        self_censorship="高",
        social_circles=["同行圈", "校友群"],
        influence_level="普通用户",
        followed_kol_domains=["行业大号", "专业媒体"],
        social_activity="低",
        recent_experiences=["读到一篇好文章"],
        emotional_baseline="平稳",
        attitude_changes=["对信息质量要求更高"],
        memory_anchors=["第一次付费订阅"],
    ),
    PersonaArchetype(
        archetype_id="mp_content_creator",
        name="公众号创作者",
        platform="wechat_mp",
        description="运营自己的公众号，定期输出长文内容",
        age_range=(25, 40), gender="female", occupation_category="内容创作者/自媒体",
        region="一二线城市", income_level="中等", education="本科/硕士",
        political_tendency=5.0, consumerism=5.0, family_tradition=4.0,
        social_justice=6.0, tech_optimism=6.0,
        professional_domains=["内容创作", "新媒体"],
        information_sources=["微信公众号", "知乎", "其他自媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="创作者",
        content_preference=["写作技巧", "运营方法", "行业交流"],
        active_hours="深夜",
        cultural_taboos=["抄袭", "洗稿"],
        sensitive_triggers=["阅读量下降", "粉丝流失"],
        avoided_topics=["敏感话题"],
        self_censorship="高",
        social_circles=["创作者群", "互推群"],
        influence_level="KOL",
        followed_kol_domains=["大号主", "写作导师"],
        social_activity="中等",
        recent_experiences=["写了一篇 10w+"],
        emotional_baseline="积极",
        attitude_changes=["对内容创作更有信心"],
        memory_anchors=["第一篇 10w+ 文章"],
    ),
    PersonaArchetype(
        archetype_id="mp_parenting_mom",
        name="育儿妈妈",
        platform="wechat_mp",
        description="关注大量育儿公众号，学习育儿知识的妈妈",
        age_range=(28, 40), gender="female", occupation_category="家庭主妇/职场妈妈",
        region="各线城市", income_level="中等", education="大专/本科",
        political_tendency=5.0, consumerism=6.0, family_tradition=9.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["育儿", "家庭教育"],
        information_sources=["育儿公众号", "妈妈群", "小红书"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="偶尔评论",
        content_preference=["育儿知识", "亲子关系", "家庭菜谱"],
        active_hours="晚间",
        cultural_taboos=["对孩子不好"],
        sensitive_triggers=["孩子教育", "婆媳关系"],
        avoided_topics=["政治"],
        self_censorship="高",
        social_circles=["妈妈群", "家长群"],
        influence_level="普通用户",
        followed_kol_domains=["育儿专家", "母婴博主"],
        social_activity="中等",
        recent_experiences=["孩子生病很焦虑"],
        emotional_baseline="平稳",
        attitude_changes=["对育儿知识更依赖"],
        memory_anchors=["孩子出生那天"],
    ),
    PersonaArchetype(
        archetype_id="mp_business_owner",
        name="中小企业主",
        platform="wechat_mp",
        description="关注商业管理类公众号，学习经营管理",
        age_range=(35, 55), gender="male", occupation_category="企业老板/高管",
        region="一二线城市", income_level="高", education="本科/MBA",
        political_tendency=5.0, consumerism=6.0, family_tradition=6.0,
        social_justice=4.0, tech_optimism=7.0,
        professional_domains=["企业管理", "商业"],
        information_sources=["商业公众号", "朋友圈", "行业会议"],
        cognitive_level="高级", media_literacy="高",
        expression_style="谨慎", interaction_preference="潜水",
        content_preference=["商业案例", "管理方法", "政策解读"],
        active_hours="早间",
        cultural_taboos=["商业机密"],
        sensitive_triggers=["政策变化", "行业监管"],
        avoided_topics=["政治敏感"],
        self_censorship="高",
        social_circles=["老板群", "商会"],
        influence_level="普通用户",
        followed_kol_domains=["商业评论", "财经媒体"],
        social_activity="低",
        recent_experiences=["公司业务有增长"],
        emotional_baseline="平稳",
        attitude_changes=["对经济形势更关注"],
        memory_anchors=["公司成立那天"],
    ),
]


# ---------------------------------------------------------------------------
# 豆瓣原型 (4 个)
# ---------------------------------------------------------------------------

DOUBAN_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="db_literary_youth",
        name="文艺青年",
        platform="douban",
        description="豆瓣核心用户，书影音重度记录者，关注文艺话题",
        age_range=(22, 35), gender="female", occupation_category="白领/学生/自由职业",
        region="一二线城市", income_level="中等", education="本科/硕士",
        political_tendency=4.0, consumerism=4.0, family_tradition=3.0,
        social_justice=7.0, tech_optimism=5.0,
        professional_domains=["文学", "艺术", "电影"],
        information_sources=["豆瓣", "微博", "独立书店"],
        cognitive_level="高级", media_literacy="高",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["书评影评", "文艺话题", "生活美学"],
        active_hours="深夜",
        cultural_taboos=["低俗", "商业化"],
        sensitive_triggers=["性别议题", "文艺作品评分"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["豆瓣小组", "文艺社群"],
        influence_level="活跃分子",
        followed_kol_domains=["影评人", "作家"],
        social_activity="高",
        recent_experiences=["写了一篇长评"],
        emotional_baseline="平稳",
        attitude_changes=["对某部电影有更深理解"],
        memory_anchors=["第一篇被推荐的影评"],
    ),
    PersonaArchetype(
        archetype_id="db_group_enthusiast",
        name="小组达人",
        platform="douban",
        description="活跃于多个豆瓣小组，参与讨论和分享",
        age_range=(25, 40), gender="female", occupation_category="白领/自由职业",
        region="一二线城市", income_level="中等", education="本科",
        political_tendency=4.5, consumerism=5.0, family_tradition=4.0,
        social_justice=6.0, tech_optimism=5.0,
        professional_domains=["各自专业"],
        information_sources=["豆瓣小组", "微信群", "微博"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["小组讨论", "经验分享", "求助帖"],
        active_hours="晚间",
        cultural_taboos=["小组规矩"],
        sensitive_triggers=["小组争议话题"],
        avoided_topics=["极度敏感"],
        self_censorship="中等",
        social_circles=["小组群", "同城群"],
        influence_level="活跃分子",
        followed_kol_domains=["小组组长", "活跃组员"],
        social_activity="高",
        recent_experiences=["在小组发了热帖"],
        emotional_baseline="平稳",
        attitude_changes=["对小组更有归属感"],
        memory_anchors=["第一次加入豆瓣小组"],
    ),
    PersonaArchetype(
        archetype_id="db_book_collector",
        name="藏书爱好者",
        platform="douban",
        description="豆瓣读书重度用户，大量标记藏书并写书评",
        age_range=(30, 50), gender="male", occupation_category="教师/研究员/白领",
        region="各线城市", income_level="中等", education="硕士/博士",
        political_tendency=5.0, consumerism=3.0, family_tradition=5.0,
        social_justice=5.0, tech_optimism=4.0,
        professional_domains=["学术", "文学"],
        information_sources=["豆瓣读书", "图书馆", "学术圈"],
        cognitive_level="高级", media_literacy="高",
        expression_style="谨慎", interaction_preference="偶尔评论",
        content_preference=["深度书评", "学术著作", "绝版书"],
        active_hours="晚间",
        cultural_taboos=["盗版", "浅阅读"],
        sensitive_triggers=["书籍评分争议"],
        avoided_topics=["敏感政治"],
        self_censorship="高",
        social_circles=["读书群", "学术圈"],
        influence_level="小 KOL",
        followed_kol_domains=["知名书评人", "学者"],
        social_activity="中等",
        recent_experiences=["收了一本绝版书"],
        emotional_baseline="积极",
        attitude_changes=["对藏书更着迷"],
        memory_anchors=["第一本藏书被推荐"],
    ),
    PersonaArchetype(
        archetype_id="db_movie_buff",
        name="影迷",
        platform="douban",
        description="豆瓣电影重度用户，标记大量电影并写影评",
        age_range=(25, 40), gender="male", occupation_category="白领/学生/媒体",
        region="一二线城市", income_level="中等", education="本科/硕士",
        political_tendency=4.5, consumerism=5.0, family_tradition=4.0,
        social_justice=6.0, tech_optimism=6.0,
        professional_domains=["电影", "传媒"],
        information_sources=["豆瓣电影", "电影节", "电影媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["电影影评", "电影节", "导演专题"],
        active_hours="深夜",
        cultural_taboos=["烂片", "流量明星"],
        sensitive_triggers=["电影评分", "抄袭争议"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["影迷群", "电影节群"],
        influence_level="活跃分子",
        followed_kol_domains=["影评人", "电影学者"],
        social_activity="高",
        recent_experiences=["看了一部好电影"],
        emotional_baseline="积极",
        attitude_changes=["对某导演有新认识"],
        memory_anchors=["第一篇被推荐的影评"],
    ),
]


# ---------------------------------------------------------------------------
# 虎扑原型 (4 个)
# ---------------------------------------------------------------------------

HUPU_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="hp_sports_fan",
        name="体育迷",
        platform="hupu",
        description="虎扑体育版块核心用户，关注 NBA/CBA/足球",
        age_range=(20, 35), gender="male", occupation_category="白领/学生/蓝领",
        region="各线城市", income_level="中等", education="本科/大专",
        political_tendency=5.0, consumerism=5.0, family_tradition=5.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["体育"],
        information_sources=["虎扑", "体育 APP", "比赛直播"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["赛事讨论", "球员新闻", "赛后分析"],
        active_hours="晚间",
        cultural_taboos=["云球迷", "不懂球"],
        sensitive_triggers=["主队输球", "裁判争议"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["球迷群", "约球群"],
        influence_level="活跃分子",
        followed_kol_domains=["体育解说", "资深球迷"],
        social_activity="高",
        recent_experiences=["主队赢球很兴奋"],
        emotional_baseline="积极",
        attitude_changes=["对某球员有新评价"],
        memory_anchors=["第一次现场看比赛"],
    ),
    PersonaArchetype(
        archetype_id="hp_straight_man",
        name="直男代表",
        platform="hupu",
        description="虎扑步行街用户，直男文化典型代表",
        age_range=(22, 35), gender="male", occupation_category="白领/蓝领",
        region="各线城市", income_level="中等", education="大专/本科",
        political_tendency=5.0, consumerism=4.0, family_tradition=6.0,
        social_justice=4.0, tech_optimism=5.0,
        professional_domains=["各自专业"],
        information_sources=["虎扑", "抖音", "微信群"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["恋爱求助", "薪资讨论", "直男段子"],
        active_hours="深夜",
        cultural_taboos=["舔狗", "娘炮"],
        sensitive_triggers=["性别对立", "工资被看不起"],
        avoided_topics=["政治敏感"],
        self_censorship="中等",
        social_circles=["兄弟群", "同事群"],
        influence_level="普通用户",
        followed_kol_domains=["JRs 推荐"],
        social_activity="中等",
        recent_experiences=["发恋爱求助帖"],
        emotional_baseline="平稳",
        attitude_changes=["对恋爱观有新认识"],
        memory_anchors=["第一次发帖被推荐"],
    ),
    PersonaArchetype(
        archetype_id="hp_digital_geek",
        name="数码发烧友",
        platform="hupu",
        description="关注虎扑数码版块，讨论手机/电脑/硬件",
        age_range=(20, 35), gender="male", occupation_category="白领/学生/IT",
        region="一二线城市", income_level="中等", education="本科/大专",
        political_tendency=5.0, consumerism=6.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=8.0,
        professional_domains=["数码", "IT"],
        information_sources=["虎扑数码", "B 站", "科技媒体"],
        cognitive_level="高级", media_literacy="高",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["数码评测", "装机配置", "产品对比"],
        active_hours="晚间",
        cultural_taboos=["云评测", "参数党"],
        sensitive_triggers=["品牌争议", "价格波动"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["数码群", "装机群"],
        influence_level="活跃分子",
        followed_kol_domains=["数码博主", "评测 UP 主"],
        social_activity="中等",
        recent_experiences=["换了新手机"],
        emotional_baseline="积极",
        attitude_changes=["对某品牌有好感"],
        memory_anchors=["第一次组装电脑"],
    ),
    PersonaArchetype(
        archetype_id="hp_gamer",
        name="游戏玩家",
        platform="hupu",
        description="关注虎扑游戏版块，讨论电竞/单机/网游",
        age_range=(18, 30), gender="male", occupation_category="学生/白领/自由职业",
        region="各线城市", income_level="中低", education="高中/本科",
        political_tendency=5.0, consumerism=5.0, family_tradition=3.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["游戏"],
        information_sources=["虎扑游戏", "B 站", "直播平台"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["赛事讨论", "游戏攻略", "游戏新闻"],
        active_hours="深夜",
        cultural_taboos=["云玩家", "作弊"],
        sensitive_triggers=["游戏平衡", "外挂"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["开黑群", "游戏群"],
        influence_level="普通用户",
        followed_kol_domains=["职业选手", "游戏主播"],
        social_activity="中等",
        recent_experiences=["打了一场好比赛"],
        emotional_baseline="积极",
        attitude_changes=["对某战队有新看法"],
        memory_anchors=["第一次上高分"],
    ),
]


# ---------------------------------------------------------------------------
# 今日头条原型 (4 个)
# ---------------------------------------------------------------------------

JINRI_TOUTIAO_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="tt_news_reader",
        name="资讯阅读者",
        platform="jinri_toutiao",
        description="每天刷今日头条看新闻，算法推荐重度用户",
        age_range=(30, 50), gender="male", occupation_category="白领/蓝领/个体户",
        region="各线城市", income_level="中等", education="大专/本科",
        political_tendency=5.0, consumerism=5.0, family_tradition=6.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["各自专业"],
        information_sources=["今日头条", "微信群", "电视新闻"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="谨慎", interaction_preference="偶尔评论",
        content_preference=["社会新闻", "国际时事", "本地资讯"],
        active_hours="早间",
        cultural_taboos=["谣言"],
        sensitive_triggers=["民生话题", "社会不公"],
        avoided_topics=["敏感政治"],
        self_censorship="高",
        social_circles=["同事群", "朋友群"],
        influence_level="普通用户",
        followed_kol_domains=["新闻媒体", "自媒体"],
        social_activity="低",
        recent_experiences=["看到某个热点新闻"],
        emotional_baseline="平稳",
        attitude_changes=["对某事件有新看法"],
        memory_anchors=["第一次刷头条超过 1 小时"],
    ),
    PersonaArchetype(
        archetype_id="tt_rural_user",
        name="下沉市场用户",
        platform="jinri_toutiao",
        description="三四线城市或农村用户，今日头条主要资讯来源",
        age_range=(35, 55), gender="male", occupation_category="农民/蓝领/小生意",
        region="三四线/农村", income_level="中低", education="初中/高中",
        political_tendency=5.5, consumerism=4.0, family_tradition=7.0,
        social_justice=4.0, tech_optimism=5.0,
        professional_domains=["农业", "服务业"],
        information_sources=["今日头条", "快手", "村口闲聊"],
        cognitive_level="初级", media_literacy="低",
        expression_style="直率", interaction_preference="偶尔评论",
        content_preference=["社会奇闻", "养生", "农业技术"],
        active_hours="午间",
        cultural_taboos=["不孝", "浪费"],
        sensitive_triggers=["农村政策", "农产品价格"],
        avoided_topics=["深度政治"],
        self_censorship="高",
        social_circles=["村民群", "亲戚群"],
        influence_level="普通用户",
        followed_kol_domains=["三农号", "养生号"],
        social_activity="低",
        recent_experiences=["看到农业技术文章"],
        emotional_baseline="平稳",
        attitude_changes=["对新技术有兴趣"],
        memory_anchors=["第一次在头条看到自家村里的事"],
    ),
    PersonaArchetype(
        archetype_id="tt_health_enthusiast",
        name="养生爱好者",
        platform="jinri_toutiao",
        description="关注养生健康内容，容易相信养生谣言",
        age_range=(45, 65), gender="female", occupation_category="退休/家庭主妇",
        region="各线城市", income_level="中等", education="高中/大专",
        political_tendency=5.0, consumerism=5.0, family_tradition=8.0,
        social_justice=5.0, tech_optimism=4.0,
        professional_domains=["养生", "健康"],
        information_sources=["今日头条", "微信群", "电视养生节目"],
        cognitive_level="初级", media_literacy="低",
        expression_style="温和", interaction_preference="偶尔评论",
        content_preference=["养生知识", "健康食谱", "疾病预防"],
        active_hours="早间",
        cultural_taboos=["不健康"],
        sensitive_triggers=["疾病", "食品安全"],
        avoided_topics=["政治"],
        self_censorship="高",
        social_circles=["养生群", "广场舞群"],
        influence_level="普通用户",
        followed_kol_domains=["养生专家", "老中医"],
        social_activity="低",
        recent_experiences=["转发养生文章到家庭群"],
        emotional_baseline="平稳",
        attitude_changes=["对某养生方法更相信"],
        memory_anchors=["第一次被养生文章吓到"],
    ),
    PersonaArchetype(
        archetype_id="tt_finance_follower",
        name="财经关注者",
        platform="jinri_toutiao",
        description="关注财经股票内容，学习投资理财",
        age_range=(30, 50), gender="male", occupation_category="白领/个体户/小老板",
        region="一二线城市", income_level="中等", education="大专/本科",
        political_tendency=5.0, consumerism=5.0, family_tradition=5.0,
        social_justice=4.0, tech_optimism=6.0,
        professional_domains=["财经", "投资"],
        information_sources=["今日头条财经", "雪球", "财经新闻"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="谨慎", interaction_preference="偶尔评论",
        content_preference=["股票分析", "理财知识", "经济政策"],
        active_hours="早间",
        cultural_taboos=["韭菜"],
        sensitive_triggers=["股市涨跌", "政策解读"],
        avoided_topics=["政治敏感"],
        self_censorship="高",
        social_circles=["股民群", "投资群"],
        influence_level="普通用户",
        followed_kol_domains=["财经大 V", "分析师"],
        social_activity="低",
        recent_experiences=["股票赚了或赔了"],
        emotional_baseline="平稳",
        attitude_changes=["对某股票有新看法"],
        memory_anchors=["第一次买股票"],
    ),
]


# ---------------------------------------------------------------------------
# 贴吧原型 (4 个)
# ---------------------------------------------------------------------------

TIEBA_ARCHETYPES = [
    PersonaArchetype(
        archetype_id="tb_interest_group",
        name="兴趣吧主",
        platform="tieba",
        description="某个兴趣贴吧的吧主或资深吧友",
        age_range=(25, 40), gender="male", occupation_category="白领/自由职业/学生",
        region="各线城市", income_level="中等", education="本科/大专",
        political_tendency=5.0, consumerism=4.0, family_tradition=5.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["兴趣领域"],
        information_sources=["贴吧", "QQ 群", "相关网站"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="创作者",
        content_preference=["兴趣讨论", "资源分享", "吧务管理"],
        active_hours="晚间",
        cultural_taboos=["水贴", "广告"],
        sensitive_triggers=["贴吧规则", "吧务争议"],
        avoided_topics=["敏感话题"],
        self_censorship="中等",
        social_circles=["贴吧群", "兴趣群"],
        influence_level="KOL",
        followed_kol_domains=["其他吧主", "资深吧友"],
        social_activity="高",
        recent_experiences=["处理了违规帖子"],
        emotional_baseline="平稳",
        attitude_changes=["对贴吧管理更有经验"],
        memory_anchors=["第一次当吧主"],
    ),
    PersonaArchetype(
        archetype_id="tb_god_reply",
        name="神回复达人",
        platform="tieba",
        description="以神回复和段子闻名贴吧",
        age_range=(20, 35), gender="male", occupation_category="学生/白领/自由职业",
        region="各线城市", income_level="中低", education="高中/本科",
        political_tendency=5.0, consumerism=4.0, family_tradition=4.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["段子", "吐槽"],
        information_sources=["贴吧", "微博", "微信群"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="激进", interaction_preference="活跃评论",
        content_preference=["神回复", "段子", "吐槽"],
        active_hours="深夜",
        cultural_taboos=["无趣"],
        sensitive_triggers=["被说不懂"],
        avoided_topics=["政治敏感"],
        self_censorship="中等",
        social_circles=["贴吧群", "段子群"],
        influence_level="活跃分子",
        followed_kol_domains=["其他神回复达人"],
        social_activity="高",
        recent_experiences=["发了个神回复被顶"],
        emotional_baseline="积极",
        attitude_changes=["对某个梗更熟悉"],
        memory_anchors=["第一个神回复"],
    ),
    PersonaArchetype(
        archetype_id="tb_game_tieba",
        name="游戏吧友",
        platform="tieba",
        description="活跃于游戏贴吧，讨论攻略和版本",
        age_range=(18, 30), gender="male", occupation_category="学生/蓝领/白领",
        region="各线城市", income_level="中低", education="高中/大专",
        political_tendency=5.0, consumerism=4.0, family_tradition=3.0,
        social_justice=5.0, tech_optimism=6.0,
        professional_domains=["游戏"],
        information_sources=["贴吧", "游戏论坛", "直播平台"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="直接", interaction_preference="活跃评论",
        content_preference=["游戏攻略", "版本讨论", "装备分享"],
        active_hours="深夜",
        cultural_taboos=["外挂", "伸手党"],
        sensitive_triggers=["游戏平衡", "版本更新"],
        avoided_topics=["政治"],
        self_censorship="中等",
        social_circles=["游戏群", "贴吧群"],
        influence_level="活跃分子",
        followed_kol_domains=["游戏大神", "攻略作者"],
        social_activity="高",
        recent_experiences=["过了一个难关"],
        emotional_baseline="积极",
        attitude_changes=["对某游戏有新认识"],
        memory_anchors=["第一次发帖问攻略"],
    ),
    PersonaArchetype(
        archetype_id="tb_school_tieba",
        name="校友吧友",
        platform="tieba",
        description="在学校贴吧活跃，分享校园信息和求助",
        age_range=(18, 25), gender="female", occupation_category="学生",
        region="各线城市", income_level="低", education="本科/大专",
        political_tendency=5.0, consumerism=4.0, family_tradition=5.0,
        social_justice=5.0, tech_optimism=5.0,
        professional_domains=["学习"],
        information_sources=["学校贴吧", "班级群", "校园论坛"],
        cognitive_level="中级", media_literacy="中等",
        expression_style="温和", interaction_preference="活跃评论",
        content_preference=["校园信息", "二手交易", "求助帖"],
        active_hours="晚间",
        cultural_taboos=["泄露隐私"],
        sensitive_triggers=["学校政策", "考试"],
        avoided_topics=["政治"],
        self_censorship="高",
        social_circles=["同学群", "校友群"],
        influence_level="普通用户",
        followed_kol_domains=["学长学姐", "校园达人"],
        social_activity="中等",
        recent_experiences=["在学校贴吧找到二手书"],
        emotional_baseline="平稳",
        attitude_changes=["对学校更了解"],
        memory_anchors=["第一次在学校贴吧发帖"],
    ),
]


# ---------------------------------------------------------------------------
# P1 平台汇总
# ---------------------------------------------------------------------------

P1_PLATFORM_ARCHETYPES = {
    "kuaishou": KUAISHOU_ARCHETYPES,
    "wechat_mp": WECHAT_MP_ARCHETYPES,
    "douban": DOUBAN_ARCHETYPES,
    "hupu": HUPU_ARCHETYPES,
    "jinri_toutiao": JINRI_TOUTIAO_ARCHETYPES,
    "tieba": TIEBA_ARCHETYPES,
}


def get_p1_archetypes_for_platform(platform: str) -> list[PersonaArchetype]:
    """获取 P1 平台的人格原型列表"""
    return P1_PLATFORM_ARCHETYPES.get(platform, [])


def get_all_p1_archetypes() -> list[PersonaArchetype]:
    """获取所有 P1 平台的人格原型"""
    all_archetypes = []
    for archetypes in P1_PLATFORM_ARCHETYPES.values():
        all_archetypes.extend(archetypes)
    return all_archetypes


if __name__ == "__main__":
    # 验证 P1 平台原型数量
    print("P1 平台人格原型统计:")
    print("=" * 40)
    total = 0
    for platform, archetypes in P1_PLATFORM_ARCHETYPES.items():
        count = len(archetypes)
        total += count
        print(f"{platform:20s}: {count} 个")
    print("=" * 40)
    print(f"总计：{total} 个 P1 人格原型")
