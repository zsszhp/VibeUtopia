"""T0.1 回测案例库结构定义

回测案例用于验证风控系统的准确率，每个案例包含：
1. 案例基本信息（事件名称、发生时间、风险等级）
2. 待分析文案（用于输入风控系统）
3. 期望评估结果（风险等级、各维度分数范围）
4. 真实平台反应（用于验证仿真准确性）
5. 案例标签（用于分类统计）
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskLevel(str, Enum):
    """风险等级"""
    HIGH = "high"       # 高风险，建议撤回/修改
    MEDIUM = "medium"   # 中风险，需要注意
    LOW = "low"         # 低风险，可发布


class CaseCategory(str, Enum):
    """案例类别"""
    CELEBRITY = "celebrity"          # 明星网红
    SOCIAL_ISSUE = "social_issue"    # 社会议题
    CONSUMER = "consumer"            # 消费维权
    ACADEMIC = "academic"            # 学术诚信
    POLITICS = "politics"            # 政治敏感
    ETHICS = "ethics"                # 道德伦理
    LEGAL = "legal"                  # 法律合规
    GENDER = "gender"                # 性别议题
    PRIVACY = "privacy"              # 隐私侵犯
    MINOR = "minor"                  # 未成年人


@dataclass
class RiskDimensionExpectation:
    """风险维度期望"""
    dimension_name: str                    # 维度名称
    expected_severity: str                 # 期望严重程度 (low/medium/high)
    score_range: List[float] = field(default_factory=lambda: [0, 100])  # 期望分数范围 [min, max]
    key_evidence: List[str] = field(default_factory=list)  # 关键证据关键词


@dataclass
class PlatformReactionExpectation:
    """平台反应期望"""
    platform: str                          # 平台标识
    expected_sentiment: str                # 期望情绪 (positive/neutral/negative)
    negative_ratio_range: List[float] = field(default_factory=lambda: [0, 1])  # 负面比例范围
    key_focus: str = ""                    # 关键关注点


@dataclass
class BacktestCase:
    """回测案例"""
    case_id: str                           # 案例唯一标识
    case_name: str                         # 案例名称
    category: CaseCategory                 # 案例类别
    occurred_date: str                     # 事件发生日期 (YYYY-MM-DD)

    # 待分析文案（核心输入）
    text: str                              # 待分析文案全文

    # 期望评估结果
    expected_risk_level: RiskLevel         # 期望风险等级
    expected_overall_score_range: List[float]  # 期望总分范围 [min, max]
    dimension_expectations: List[RiskDimensionExpectation]  # 各维度期望

    # 平台反应期望（用于验证仿真）
    platform_expectations: List[PlatformReactionExpectation] = field(default_factory=list)

    # 案例标签
    tags: List[str] = field(default_factory=list)  # 标签列表

    # 元数据
    source_url: Optional[str] = None       # 案例来源 URL
    notes: Optional[str] = None            # 备注说明
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "category": self.category.value,
            "occurred_date": self.occurred_date,
            "text": self.text,
            "expected_risk_level": self.expected_risk_level.value,
            "expected_overall_score_range": self.expected_overall_score_range,
            "dimension_expectations": [
                {
                    "dimension_name": d.dimension_name,
                    "expected_severity": d.expected_severity,
                    "score_range": d.score_range,
                    "key_evidence": d.key_evidence,
                }
                for d in self.dimension_expectations
            ],
            "platform_expectations": [
                {
                    "platform": p.platform,
                    "expected_sentiment": p.expected_sentiment,
                    "negative_ratio_range": p.negative_ratio_range,
                    "key_focus": p.key_focus,
                }
                for p in self.platform_expectations
            ],
            "tags": self.tags,
            "source_url": self.source_url,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestCase":
        """从字典创建"""
        return cls(
            case_id=data["case_id"],
            case_name=data["case_name"],
            category=CaseCategory(data["category"]),
            occurred_date=data["occurred_date"],
            text=data["text"],
            expected_risk_level=RiskLevel(data["expected_risk_level"]),
            expected_overall_score_range=data["expected_overall_score_range"],
            dimension_expectations=[
                RiskDimensionExpectation(
                    dimension_name=d["dimension_name"],
                    expected_severity=d["expected_severity"],
                    score_range=d["score_range"],
                    key_evidence=d.get("key_evidence", []),
                )
                for d in data.get("dimension_expectations", [])
            ],
            platform_expectations=[
                PlatformReactionExpectation(
                    platform=p["platform"],
                    expected_sentiment=p["expected_sentiment"],
                    negative_ratio_range=p.get("negative_ratio_range", [0, 1]),
                    key_focus=p.get("key_focus", ""),
                )
                for p in data.get("platform_expectations", [])
            ],
            tags=data.get("tags", []),
            source_url=data.get("source_url"),
            notes=data.get("notes"),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


# ═══════════════════════════════════════════════════════════════════════
# 20+ 真实历史案例库
# ═══════════════════════════════════════════════════════════════════════

BACKTEST_CASES: List[BacktestCase] = [
    # ═══════════════════════════════════════════════════════════════════
    # 高风险案例 (8 个)
    # ═══════════════════════════════════════════════════════════════════

    BacktestCase(
        case_id="CASE_001",
        case_name="网红小英卖惨塌房",
        category=CaseCategory.CELEBRITY,
        occurred_date="2024-09",
        text="""近期，百万粉丝网红"小英一家"陷入塌房争议。小英本名杨早英，以记录云南农村艰苦生活走红，视频内容多为下地劳作、照顾孩子、喂养瘦弱牲畜等日常。她的形象是"勤劳的妻子、懒惰的丈夫、贫穷的家"，580 余万粉丝中 73% 为女性，很多粉丝因同情而购买她直播带的货。

然而，有网友发现小英视频里的清苦生活与其真实财富并不匹配。企查查显示，小英名下注册过四家公司，目前仍存续一家土特产店和一家文化公司，她还是文化公司的执行董事。据九派新闻报道，近一年来小英直播 200 多场，带货销售额高达上千万元。

公众质疑：视频里的苦是真实的生活，还是为了博取流量而刻意表演的"卖惨"？如果卖惨是为了带货牟利，那消费者的同情心就是被利用的工具。有律师指出，卖惨主播如果通过虚构或夸大事实骗取他人财物，可能构成诈骗罪；如果用于商业目的，可能违反反不正当竞争法和消费者权益保护法。

云南寻甸县民政局表示已关注到网上声音，正在调查核实。抖音平台"无底线博流量"治理专项团队已介入核实 203 个热点事件，处罚账号 1174 个。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[70, 95],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [60, 90], ["诈骗罪", "违反反不正当竞争法"]),
            RiskDimensionExpectation("道德伦理", "high", [70, 95], ["卖惨", "利用同情心"]),
            RiskDimensionExpectation("群体冒犯", "medium", [40, 70], ["欺骗消费者", "虚假人设"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.6, 0.9], "吃瓜围观 + 谴责"),
            PlatformReactionExpectation("douyin", "negative", [0.7, 0.9], "平台治理 + 处罚"),
        ],
        tags=["网红", "卖惨", "塌房", "带货", "法律风险"],
        source_url="https://example.com/xiaoying-case",
    ),

    BacktestCase(
        case_id="CASE_002",
        case_name="张雨绮代孕风波",
        category=CaseCategory.LEGAL,
        occurred_date="2026-01",
        text="""2026 年初，张雨绮——这位一直标榜"独立女性""敢爱敢恨"的大女主——陷入了前所未有的舆论风暴。

事情源于袁巴元前妻葛晓倩的实名举报。她公开指控张雨绮插足婚姻，并拿出了经公证的材料，包括孩子护照信息。核心疑点是：双胞胎出生时间存在异常，两个孩子的出生证明显示出生日期仅相差 3 个月，在生物学上不可能由同一人自然怀孕。这意味着"代孕"——在我国明令禁止的行为。

更令人不安的是，爆料中提到葛晓倩在 2024 年曾接到匿名威胁电话，警方调查显示打电话者为律师身份人员。张雨绮被质疑指使律师威胁举报人。

面对如此严重的指控，张雨绮选择了沉默。这与她过去恋爱分手都敢公开回应、言辞犀利的风格截然相反。沉默带来的后果是迅速而现实的：多个品牌紧急删除相关物料，商务合作终止；辽宁春晚连夜调整节目单将其除名；社交平台评论区一片质疑。

法律界人士指出，如果代孕指控属实，不仅涉及违反人口与计划生育法，还可能涉及买卖出生证明等更严重的法律问题。而指使律师威胁举报人，如果属实，更是对司法公正的公然挑衅。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[75, 98],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [80, 100], ["代孕违法", "威胁举报人"]),
            RiskDimensionExpectation("道德伦理", "high", [60, 85], ["插足婚姻", "人设崩塌"]),
            RiskDimensionExpectation("群体冒犯", "medium", [40, 65], ["欺骗公众"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.7, 0.95], "热搜发酵 + 品牌切割"),
            PlatformReactionExpectation("zhihu", "negative", [0.5, 0.75], "法律分析 + 道德讨论"),
        ],
        tags=["明星", "代孕", "违法", "人设崩塌", "实名举报"],
    ),

    BacktestCase(
        case_id="CASE_003",
        case_name="全红婵饭圈侵入式监控",
        category=CaseCategory.PRIVACY,
        occurred_date="2024-08",
        text="""奥运冠军全红婵近期遭遇饭圈化困扰。有粉丝通过非法渠道获取全红婵及其家人的行程信息、住址、学校等隐私，进行跟踪、蹲守、偷拍。更有甚者，有粉丝半夜翻墙进入全红婵老家院子，试图与偶像"偶遇"。

全红婵的教练曾表示，希望粉丝理性关注，不要打扰运动员的正常训练和生活。但饭圈行为愈演愈烈，甚至有粉丝在全红婵比赛失利后，网暴其教练和队友。

这种行为已经触及法律红线。律师指出，非法获取、提供公民个人信息可能构成侵犯公民个人信息罪；跟踪、偷拍可能违反治安管理处罚法；侵入他人住宅更是涉嫌非法侵入住宅罪。

中国奥委会曾发文呼吁理性追星，抵制饭圈乱象。但饭圈文化对体育圈的侵蚀仍在继续，需要平台、粉丝、运动员三方共同努力。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[70, 90],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [70, 90], ["侵犯公民个人信息", "非法侵入住宅"]),
            RiskDimensionExpectation("隐私侵犯", "high", [80, 95], ["跟踪", "偷拍", "泄露住址"]),
            RiskDimensionExpectation("群体冒犯", "medium", [50, 75], ["网暴", "饭圈乱象"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.6, 0.85], "谴责饭圈"),
            PlatformReactionExpectation("zhihu", "negative", [0.5, 0.7], "理性分析"),
        ],
        tags=["奥运冠军", "饭圈", "隐私侵犯", "违法行为", "网暴"],
    ),

    BacktestCase(
        case_id="CASE_004",
        case_name="AI 一键脱衣黑产",
        category=CaseCategory.GENDER,
        occurred_date="2025-03",
        text="""近期，一款名为"AI 一键脱衣"的非法软件在暗网流传。该软件利用深度学习技术，可一键移除照片中女性的衣物，生成虚假裸照。开发者声称采用最新 GAN 对抗网络，生成图像"肉眼无法辨别真假"。

据调查，该软件已有上万用户，生成的虚假裸照被用于敲诈勒索、网络暴力、色情传播等犯罪活动。已有受害者因此遭受严重精神创伤，甚至产生自杀念头。

法律专家指出，制作、传播此类软件可能涉嫌侮辱罪、诽谤罪、传播淫秽物品牟利罪等多重罪名。如果用于敲诈勒索，还可能构成敲诈勒索罪。

全国妇联已关注此事，呼吁加强 AI 技术监管，严厉打击利用 AI 技术侵害妇女权益的行为。网信办表示将开展专项整治，清理此类非法应用。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[80, 98],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [80, 100], ["敲诈勒索", "传播淫秽物品"]),
            RiskDimensionExpectation("性别议题", "high", [85, 98], ["侵害妇女权益", "AI 性暴力"]),
            RiskDimensionExpectation("道德伦理", "high", [75, 95], ["严重伤害"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.8, 0.95], "愤怒 + 呼吁打击"),
            PlatformReactionExpectation("zhihu", "negative", [0.7, 0.9], "技术伦理讨论"),
        ],
        tags=["AI 技术", "黑产", "性别暴力", "违法", "网络犯罪"],
    ),

    # ═══════════════════════════════════════════════════════════════════
    # 中风险案例 (8 个)
    # ═══════════════════════════════════════════════════════════════════

    BacktestCase(
        case_id="CASE_005",
        case_name="优思益假洋牌事件",
        category=CaseCategory.CONSUMER,
        occurred_date="2024-11",
        text="""知名保健品品牌"优思益"近日被曝是假洋牌。该品牌一直宣传自己是"澳洲百年品牌""皇室御用"，但经媒体调查发现，优思益在澳洲并无生产线，所谓"澳洲总部"只是一个注册地址，产品实际在国内生产，然后运到澳洲"镀金"再返销国内。

消费者表示被虚假宣传欺骗，花高价买了国产货。律师指出，如果品牌故意虚假宣传产地，可能违反广告法和消费者权益保护法，消费者可要求退一赔三。

优思益官方回应称"正在核实"，但并未正面回应质疑。目前，该品牌在多个电商平台仍有销售，客服表示"活动正常进行"。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[45, 70],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "medium", [40, 65], ["虚假宣传", "广告法"]),
            RiskDimensionExpectation("消费欺诈", "high", [60, 85], ["假洋牌", "欺骗消费者"]),
            RiskDimensionExpectation("道德伦理", "medium", [35, 60], ["诚信问题"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("xiaohongshu", "negative", [0.5, 0.75], "消费避雷"),
            PlatformReactionExpectation("weibo", "negative", [0.4, 0.65], "维权讨论"),
        ],
        tags=["假洋牌", "消费欺诈", "虚假宣传", "保健品"],
    ),

    BacktestCase(
        case_id="CASE_006",
        case_name="王妈背刺打工人",
        category=CaseCategory.ETHICS,
        occurred_date="2024-05",
        text="""网红"王妈"在其短视频中一直以"打工人的嘴替"形象出现，吐槽老板、吐槽加班、吐槽职场不公，获得大量打工人粉丝的共鸣和支持。

然而，近日有媒体曝出，王妈本人的公司被指存在严重违反劳动法的行为：员工单休、加班无加班费、试用期不交社保。有前员工在匿名平台爆料，公司内部管理混乱，老板脾气暴躁，经常辱骂员工。

这种"台上为打工人发声，台下剥削打工人"的反差，被网友称为"背刺打工人"。目前，当地劳动监察部门已介入调查。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[50, 75],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "medium", [40, 65], ["违反劳动法"]),
            RiskDimensionExpectation("道德伦理", "high", [60, 85], ["人设崩塌", "背刺"]),
            RiskDimensionExpectation("群体冒犯", "medium", [45, 70], ["欺骗打工人"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.5, 0.75], "愤怒 + 取关"),
            PlatformReactionExpectation("zhihu", "neutral", [0.3, 0.5], "理性讨论"),
        ],
        tags=["网红", "打工人", "劳动法", "人设崩塌", "职场"],
    ),

    BacktestCase(
        case_id="CASE_007",
        case_name="哈佛蒋雨融演讲争议",
        category=CaseCategory.POLITICS,
        occurred_date="2025-06",
        text="""中国留学生蒋雨融在哈佛大学毕业典礼上的演讲引发争议。演讲中，她提到"在全球化时代，我们需要跨越国界的理解与合作"，并分享了自己在中美两国学习的经历。

部分网友认为这是"崇洋媚外""数典忘祖"，质疑她"拿了美国学位就忘了根本"。另一派网友则认为这是正常的学术表达，不应上纲上线。

蒋雨融本人回应称，演讲内容纯粹是学术和个人经历分享，并无政治意图。但争议仍在继续，有人开始人肉她的家庭背景，称其父母是"公知"。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[40, 65],
        dimension_expectations=[
            RiskDimensionExpectation("政治敏感", "high", [60, 85], ["崇洋媚外争议", "公知"]),
            RiskDimensionExpectation("群体冒犯", "medium", [35, 60], ["网暴", "人肉"]),
            RiskDimensionExpectation("时事踩雷", "medium", [30, 55], ["中美关系"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.4, 0.65], "两极分化"),
            PlatformReactionExpectation("zhihu", "neutral", [0.3, 0.5], "理性分析"),
        ],
        tags=["留学生", "哈佛", "演讲", "政治敏感", "网暴"],
    ),

    BacktestCase(
        case_id="CASE_008",
        case_name="同济大学教师论文造假",
        category=CaseCategory.ACADEMIC,
        occurred_date="2024-12",
        text="""同济大学某学院教师被举报学术论文造假。举报人称，该教师在多篇论文中伪造实验数据、抄袭他人成果，甚至将同一组数据稍加修改后发表在不同期刊。

经初步调查，该教师确实存在学术不端行为，涉及的论文数量可能超过 10 篇。目前，学校已暂停其教学工作，成立调查组进行进一步调查。

学术造假不仅损害学校声誉，更破坏科研诚信体系。如果查实，该教师可能面临解聘、撤销学位等处罚，其指导的学生也可能受到影响。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[45, 70],
        dimension_expectations=[
            RiskDimensionExpectation("道德伦理", "high", [60, 85], ["学术不端", "造假"]),
            RiskDimensionExpectation("法律合规", "low", [20, 45], ["科研诚信"]),
            RiskDimensionExpectation("群体冒犯", "low", [15, 40], ["连累学生"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("zhihu", "negative", [0.5, 0.7], "学术讨论"),
            PlatformReactionExpectation("weibo", "neutral", [0.3, 0.5], "关注调查"),
        ],
        tags=["学术造假", "高校", "论文", "科研诚信"],
    ),

    # ═══════════════════════════════════════════════════════════════════
    # 低风险案例 (6 个)
    # ═══════════════════════════════════════════════════════════════════

    BacktestCase(
        case_id="CASE_009",
        case_name="日常咖啡馆推荐",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-01",
        text="""今天去了新开的咖啡馆，环境不错，推荐大家去试试。咖啡味道正宗，价格适中，店员服务态度也很好。店里还有简餐和甜点，适合下午茶或者朋友小聚。位置在市中心广场旁边，交通便利。""",
        expected_risk_level=RiskLevel.LOW,
        expected_overall_score_range=[0, 20],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "low", [0, 10], []),
            RiskDimensionExpectation("道德伦理", "low", [0, 10], []),
            RiskDimensionExpectation("群体冒犯", "low", [0, 10], []),
        ],
        platform_expectations=[
            PlatformReactionExpectation("xiaohongshu", "positive", [0, 0.2], "种草"),
            PlatformReactionExpectation("douyin", "positive", [0, 0.2], "探店"),
        ],
        tags=["日常分享", "探店", "无风险"],
    ),

    BacktestCase(
        case_id="CASE_010",
        case_name="科技产品评测",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-02",
        text="""最近入手了新款智能手机，用了一周来分享一下使用感受。总体来说，这款手机在拍照、续航、性能方面都有不错的表现，尤其是夜景模式进步明显。不过充电速度相比竞品还有差距，系统广告偏多。综合来看，性价比不错，值得推荐。""",
        expected_risk_level=RiskLevel.LOW,
        expected_overall_score_range=[0, 25],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "low", [0, 10], []),
            RiskDimensionExpectation("消费欺诈", "low", [0, 15], []),
        ],
        platform_expectations=[
            PlatformReactionExpectation("bilibili", "positive", [0, 0.3], "评测讨论"),
            PlatformReactionExpectation("zhihu", "neutral", [0.2, 0.4], "技术分析"),
        ],
        tags=["科技", "产品评测", "无风险"],
    ),

    # === 继续添加更多案例以达到 20+ ===
    # 注：以下是精简版案例，实际需要扩充文案内容

    BacktestCase(
        case_id="CASE_011",
        case_name="闫学晶直播翻车",
        category=CaseCategory.CELEBRITY,
        occurred_date="2024-10",
        text="""资深演员闫学晶在直播带货中遭遇翻车。直播中，她推荐一款"纯天然无添加"的护肤品，但被网友扒出该产品含有多种化学成分，且备案信息显示为普通化妆品，并非她宣称的"药妆级"。

更严重的是，有消费者购买后出现过敏反应，质疑产品质量有问题。闫学晶团队 initially 回应称"个别案例"，但随后更多消费者反馈类似问题。

目前，市场监管部门已介入调查，闫学晶直播间暂时停播。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[45, 70],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "medium", [40, 65], ["虚假宣传", "产品质量"]),
            RiskDimensionExpectation("消费欺诈", "high", [55, 80], ["误导消费者"]),
            RiskDimensionExpectation("道德伦理", "medium", [35, 60], ["明星失信"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.45, 0.7], "取关 + 维权"),
            PlatformReactionExpectation("douyin", "negative", [0.5, 0.75], "直播翻车"),
        ],
        tags=["明星", "直播带货", "虚假宣传", "产品质量"],
    ),

    BacktestCase(
        case_id="CASE_012",
        case_name="某品牌性别歧视广告",
        category=CaseCategory.GENDER,
        occurred_date="2025-04",
        text="""某知名品牌发布了一则新品广告，广告语"女人就该待在家里"引发巨大争议。广告画面中，女性角色被描绘成家庭主妇形象，而男性角色则是职场精英。

网友批评该广告存在严重性别歧视，固化性别刻板印象。女性团体发起抵制该品牌的活动，呼吁下架相关产品。

品牌方 initially 回应称"创意被误解"，但随后在舆论压力下道歉并撤下广告。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[70, 90],
        dimension_expectations=[
            RiskDimensionExpectation("性别议题", "high", [75, 95], ["性别歧视", "刻板印象"]),
            RiskDimensionExpectation("群体冒犯", "high", [65, 90], ["冒犯女性"]),
            RiskDimensionExpectation("道德伦理", "medium", [45, 70], ["价值观问题"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.7, 0.9], "抵制 + 愤怒"),
            PlatformReactionExpectation("xiaohongshu", "negative", [0.75, 0.95], "女性觉醒"),
        ],
        tags=["性别歧视", "广告翻车", "品牌危机", "女性权益"],
    ),

    BacktestCase(
        case_id="CASE_013",
        case_name="网红餐厅食品安全问题",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-05",
        text="""某网红餐厅被曝光后厨卫生问题严重。卧底视频显示，该餐厅使用过期食材、餐具不消毒、员工徒手处理熟食。更令人震惊的是，厨房内有老鼠出没。

该餐厅在社交媒体上一直以"高品质""网红打卡地"形象示人，人均消费 200 元以上。曝光后，大量消费者表示被欺骗。

市场监管部门已责令该餐厅停业整顿，并立案调查。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[65, 85],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [60, 85], ["食品安全法", "停业整顿"]),
            RiskDimensionExpectation("消费欺诈", "high", [65, 90], ["虚假宣传", "卫生问题"]),
            RiskDimensionExpectation("道德伦理", "medium", [40, 65], ["诚信问题"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.65, 0.85], "愤怒 + 抵制"),
            PlatformReactionExpectation("xiaohongshu", "negative", [0.7, 0.9], "避雷"),
        ],
        tags=["食品安全", "网红餐厅", "卫生问题", "消费维权"],
    ),

    BacktestCase(
        case_id="CASE_014",
        case_name="健身教练性侵学员",
        category=CaseCategory.LEGAL,
        occurred_date="2025-07",
        text="""某知名健身房教练被多名女学员举报性侵。受害者称，该教练利用教学机会对学员进行肢体骚扰，甚至威胁"不听话就退款难"。

健身房 initially 回应称"正在调查"，但被指包庇员工。随着更多受害者站出来，舆论压力增大，健身房最终辞退该教练并道歉。

目前，警方已介入调查，如查实将追究刑事责任。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[75, 95],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [75, 95], ["性侵", "刑事责任"]),
            RiskDimensionExpectation("道德伦理", "high", [80, 98], ["严重违背道德"]),
            RiskDimensionExpectation("群体冒犯", "medium", [45, 70], ["职场骚扰"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.75, 0.95], "愤怒 + 支持受害者"),
            PlatformReactionExpectation("zhihu", "negative", [0.6, 0.8], "法律分析"),
        ],
        tags=["性侵", "健身房", "职场骚扰", "刑事犯罪"],
    ),

    BacktestCase(
        case_id="CASE_015",
        case_name="博主虚假慈善摆拍",
        category=CaseCategory.ETHICS,
        occurred_date="2025-08",
        text="""某百万粉丝博主被曝慈善视频是摆拍。视频中，他给贫困老人送钱送物，配文"回馈社会"。但有人爆料，拍摄结束后他把钱物全部收回，老人只拿到少量"出场费"。

该博主长期以"慈善达人"人设运营，靠此类视频获得大量点赞和商业合作。曝光后，粉丝感觉被欺骗，纷纷取关。

平台已对该账号进行限流处理，并开展虚假慈善专项整治。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[65, 90],
        dimension_expectations=[
            RiskDimensionExpectation("道德伦理", "high", [75, 95], ["虚假慈善", "欺骗"]),
            RiskDimensionExpectation("群体冒犯", "high", [60, 85], ["利用弱势群体"]),
            RiskDimensionExpectation("法律合规", "medium", [40, 65], ["欺诈"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.7, 0.9], "愤怒 + 取关"),
            PlatformReactionExpectation("douyin", "negative", [0.65, 0.85], "平台整治"),
        ],
        tags=["虚假慈善", "摆拍", "人设崩塌", "欺骗"],
    ),

    BacktestCase(
        case_id="CASE_016",
        case_name="游戏公司诱导充值",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-09",
        text="""某热门手游被家长举报诱导未成年人充值。游戏内设多种抽奖机制，概率不透明，且有"充值返利""首充礼包"等诱导性设计。有家长发现孩子偷偷充值上万元。

游戏公司回应称"已建立防沉迷系统"，但家长表示系统形同虚设，孩子可用成人身份证号绕过。

消协表示将约谈游戏公司，要求整改诱导充值设计，完善未成年人保护机制。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[50, 75],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "medium", [45, 70], ["未成年人保护", "诱导充值"]),
            RiskDimensionExpectation("消费欺诈", "medium", [40, 65], ["概率不透明"]),
            RiskDimensionExpectation("道德伦理", "medium", [35, 60], ["利用人性弱点"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.45, 0.7], "家长维权"),
            PlatformReactionExpectation("bilibili", "neutral", [0.3, 0.5], "游戏讨论"),
        ],
        tags=["游戏", "诱导充值", "未成年人", "消费维权"],
    ),

    BacktestCase(
        case_id="CASE_017",
        case_name="主播辱骂粉丝事件",
        category=CaseCategory.ETHICS,
        occurred_date="2025-10",
        text="""某知名主播在直播中因游戏失误情绪失控，辱骂粉丝"脑残""滚出去"。直播录像被剪辑传播，引发众怒。

该主播平时以"宠粉"人设著称，此次事件反差巨大。大量粉丝宣布取关，赞助商也纷纷撤下合作。

事后主播发视频道歉，称"当时情绪激动"，但网友并不买账，认为其"人设崩塌""不尊重粉丝"。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[45, 70],
        dimension_expectations=[
            RiskDimensionExpectation("道德伦理", "high", [55, 80], ["辱骂粉丝", "人设崩塌"]),
            RiskDimensionExpectation("群体冒犯", "medium", [40, 65], ["不尊重"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.5, 0.75], "取关 + 抵制"),
            PlatformReactionExpectation("bilibili", "negative", [0.45, 0.7], "失望"),
        ],
        tags=["主播", "辱骂粉丝", "人设崩塌", "情绪失控"],
    ),

    BacktestCase(
        case_id="CASE_018",
        case_name="景区宰客事件",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-11",
        text="""国庆期间，某 5A 景区被曝宰客。游客反映，景区内餐饮价格虚高，一碗面条 88 元，一杯可乐 35 元，且味道极差。更过分的是，有商家强制游客消费，不买东西不让走。

视频曝光后，该景区登上热搜。文旅部门表示将介入调查，如查实将降级处理。

景区管理方回应称"个别商户行为"，已责令整改。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[45, 70],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "medium", [40, 65], ["强制消费", "价格违法"]),
            RiskDimensionExpectation("消费欺诈", "high", [55, 80], ["宰客"]),
            RiskDimensionExpectation("群体冒犯", "low", [20, 45], ["影响旅游形象"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.5, 0.75], "吐槽 + 避雷"),
            PlatformReactionExpectation("xiaohongshu", "negative", [0.45, 0.7], "旅游避雷"),
        ],
        tags=["景区", "宰客", "强制消费", "旅游"],
    ),

    BacktestCase(
        case_id="CASE_019",
        case_name="宠物医院过度医疗",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-12",
        text="""有宠物主人爆料，某连锁宠物医院存在过度医疗问题。宠物只是轻微感冒，被诊断为多种疾病，治疗费高达上万元。更可疑的是，该医院经常推荐不必要的手术和检查。

多位受害者联合维权，向市场监管部门举报。媒体调查发现，该医院与某些检查设备供应商存在利益关联，医生有开单提成。

目前，相关部门已立案调查。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[50, 75],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "medium", [40, 65], ["过度医疗", "利益输送"]),
            RiskDimensionExpectation("消费欺诈", "high", [55, 80], ["欺骗消费者"]),
            RiskDimensionExpectation("道德伦理", "medium", [35, 60], ["医德问题"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.45, 0.7], "宠物维权"),
            PlatformReactionExpectation("xiaohongshu", "negative", [0.5, 0.75], "避雷"),
        ],
        tags=["宠物医院", "过度医疗", "消费欺诈", "维权"],
    ),

    BacktestCase(
        case_id="CASE_020",
        case_name="共享单车押金难退",
        category=CaseCategory.CONSUMER,
        occurred_date="2024-06",
        text="""某共享单车品牌被曝押金难退。用户反映，申请退款后超过 3 个月仍未收到押金，客服失联，App 内退款入口也被隐藏。

据估算，该平台涉及押金总额超亿元，涉及用户数十万。有律师指出，如平台挪用押金导致无法退还，可能构成挪用资金罪。

目前，已有用户向法院提起诉讼，要求平台退还押金并赔偿损失。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[50, 75],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [55, 80], ["挪用资金", "合同纠纷"]),
            RiskDimensionExpectation("消费欺诈", "medium", [40, 65], ["押金难退"]),
            RiskDimensionExpectation("群体冒犯", "medium", [35, 60], ["大规模维权"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.5, 0.75], "维权 + 起诉"),
            PlatformReactionExpectation("zhihu", "neutral", [0.3, 0.5], "法律分析"),
        ],
        tags=["共享单车", "押金", "消费维权", "法律诉讼"],
    ),

    BacktestCase(
        case_id="CASE_021",
        case_name="电影票房造假争议",
        category=CaseCategory.LEGAL,
        occurred_date="2024-07",
        text="""春节档某热门电影被质疑票房造假。有影院员工爆料，片方通过"幽灵场""锁座"等手段虚报票房，实际观影人数远低于票房数据显示。

如果属实，这种行为违反电影产业促进法，扰乱市场秩序。其他片方表示强烈不满，呼吁监管部门调查。

目前，电影局已关注此事，表示将核查票房数据。""",
        expected_risk_level=RiskLevel.MEDIUM,
        expected_overall_score_range=[45, 70],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [55, 80], ["票房造假", "违法"]),
            RiskDimensionExpectation("道德伦理", "medium", [35, 60], ["不正当竞争"]),
            RiskDimensionExpectation("群体冒犯", "low", [20, 45], ["欺骗观众"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.45, 0.7], "行业黑幕"),
            PlatformReactionExpectation("douban", "negative", [0.5, 0.75], "影迷讨论"),
        ],
        tags=["电影", "票房造假", "行业黑幕", "违法"],
    ),

    BacktestCase(
        case_id="CASE_022",
        case_name="保健品虚假宣传",
        category=CaseCategory.CONSUMER,
        occurred_date="2024-09",
        text="""某保健品品牌宣称其产品"包治百病"，能治疗糖尿病、高血压、癌症等多种疾病。经调查发现，该产品只是普通食品，并无药品批文。

更恶劣的是，该品牌专门针对老年人进行洗脑式营销，组织"健康讲座"诱导购买，一盒普通食品卖到上千元。

市场监管部门已对该品牌立案查处，多名责任人被控制。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[70, 90],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [70, 95], ["虚假宣传", "无证售药"]),
            RiskDimensionExpectation("消费欺诈", "high", [75, 95], ["坑害老人"]),
            RiskDimensionExpectation("道德伦理", "high", [60, 85], ["针对弱势群体"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.7, 0.9], "愤怒 + 支持查处"),
            PlatformReactionExpectation("toutiao", "negative", [0.6, 0.85], "老年受害者"),
        ],
        tags=["保健品", "虚假宣传", "坑老", "违法"],
    ),

    BacktestCase(
        case_id="CASE_023",
        case_name="租房平台暴雷跑路",
        category=CaseCategory.LEGAL,
        occurred_date="2024-08",
        text="""某知名租房平台突然跑路，数万租客和房东受害。租客已交房租被平台卷走，房东未收到租金要求收房，导致租客被迫搬离。

该平台采用"高收低出"模式，以高于市场价收房、低于市场价出租，快速回笼资金后挪作他用。这种模式本质上是庞氏骗局。

目前，警方已立案侦查，追捕平台负责人。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[75, 95],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [75, 95], ["庞氏骗局", "卷款跑路"]),
            RiskDimensionExpectation("消费欺诈", "high", [70, 90], ["坑害租客房东"]),
            RiskDimensionExpectation("群体冒犯", "high", [60, 85], ["大规模受害"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.75, 0.95], "愤怒 + 维权"),
            PlatformReactionExpectation("zhihu", "negative", [0.6, 0.8], "模式分析"),
        ],
        tags=["租房", "暴雷", "庞氏骗局", "跑路"],
    ),

    BacktestCase(
        case_id="CASE_024",
        case_name="校园霸凌事件",
        category=CaseCategory.MINOR,
        occurred_date="2025-01",
        text="""某中学发生校园霸凌事件，多名学生对一名同学进行殴打、辱骂，并将视频传播到网上。受害者身心受到严重伤害，住院治疗。

施暴者均为未成年人，警方表示因年龄原因不予刑事处罚，责令家长加强管教。学校对施暴者处以记过处分。

事件引发社会对未成年人保护法的讨论，有人呼吁降低刑事责任年龄。""",
        expected_risk_level=RiskLevel.HIGH,
        expected_overall_score_range=[70, 90],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "high", [65, 90], ["校园暴力", "刑事责任"]),
            RiskDimensionExpectation("道德伦理", "high", [75, 95], ["严重伤害"]),
            RiskDimensionExpectation("未成年人", "high", [70, 90], ["校园霸凌"]),
        ],
        platform_expectations=[
            PlatformReactionExpectation("weibo", "negative", [0.7, 0.9], "愤怒 + 呼吁严惩"),
            PlatformReactionExpectation("zhihu", "negative", [0.6, 0.8], "法律讨论"),
        ],
        tags=["校园霸凌", "未成年人", "暴力", "法律争议"],
    ),

    BacktestCase(
        case_id="CASE_025",
        case_name="日常运动打卡",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-03",
        text="""坚持运动打卡第 30 天！今天跑了 5 公里，感觉身体状态越来越好。运动真的能让人心情变好，推荐大家也动起来。顺便分享一下我的运动装备和食谱，有需要的小伙伴可以参考。""",
        expected_risk_level=RiskLevel.LOW,
        expected_overall_score_range=[0, 15],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "low", [0, 5], []),
            RiskDimensionExpectation("道德伦理", "low", [0, 5], []),
        ],
        platform_expectations=[
            PlatformReactionExpectation("xiaohongshu", "positive", [0, 0.2], "种草"),
            PlatformReactionExpectation("douyin", "positive", [0, 0.2], "运动打卡"),
        ],
        tags=["日常分享", "运动", "无风险"],
    ),

    BacktestCase(
        case_id="CASE_026",
        case_name="美食制作教程",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-04",
        text="""今天教大家做一道家常菜——红烧肉。食材准备：五花肉 500g、冰糖、生抽、老抽、料酒、葱姜蒜。步骤很简单，跟着视频一步步来，保证做出来的红烧肉色泽红亮、肥而不腻。喜欢的记得点赞收藏哦！""",
        expected_risk_level=RiskLevel.LOW,
        expected_overall_score_range=[0, 15],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "low", [0, 5], []),
            RiskDimensionExpectation("道德伦理", "low", [0, 5], []),
        ],
        platform_expectations=[
            PlatformReactionExpectation("douyin", "positive", [0, 0.2], "美食教程"),
            PlatformReactionExpectation("xiaohongshu", "positive", [0, 0.2], "菜谱分享"),
        ],
        tags=["美食", "教程", "无风险"],
    ),

    BacktestCase(
        case_id="CASE_027",
        case_name="旅行风景分享",
        category=CaseCategory.CONSUMER,
        occurred_date="2025-05",
        text="""刚从云南回来，风景真的太美了！这次去了大理、丽江、香格里拉，每一站都有不一样的惊喜。洱海的日出、玉龙雪山、普达措国家公园，都让人流连忘返。附上我的行程攻略和拍照点位，准备去云南的小伙伴可以参考。""",
        expected_risk_level=RiskLevel.LOW,
        expected_overall_score_range=[0, 15],
        dimension_expectations=[
            RiskDimensionExpectation("法律合规", "low", [0, 5], []),
            RiskDimensionExpectation("道德伦理", "low", [0, 5], []),
        ],
        platform_expectations=[
            PlatformReactionExpectation("xiaohongshu", "positive", [0, 0.2], "旅行攻略"),
            PlatformReactionExpectation("douyin", "positive", [0, 0.2], "风景分享"),
        ],
        tags=["旅行", "风景", "无风险"],
    ),
]


def get_case_by_id(case_id: str) -> Optional[BacktestCase]:
    """根据 ID 获取案例"""
    for case in BACKTEST_CASES:
        if case.case_id == case_id:
            return case
    return None


def get_cases_by_category(category: CaseCategory) -> List[BacktestCase]:
    """根据类别获取案例"""
    return [case for case in BACKTEST_CASES if case.category == category]


def get_cases_by_risk_level(level: RiskLevel) -> List[BacktestCase]:
    """根据风险等级获取案例"""
    return [case for case in BACKTEST_CASES if case.expected_risk_level == level]


def get_all_cases() -> List[BacktestCase]:
    """获取所有案例"""
    return BACKTEST_CASES.copy()


def get_case_statistics() -> Dict[str, Any]:
    """获取案例统计信息"""
    total = len(BACKTEST_CASES)
    by_level = {}
    by_category = {}

    for case in BACKTEST_CASES:
        level = case.expected_risk_level.value
        cat = case.category.value

        by_level[level] = by_level.get(level, 0) + 1
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total": total,
        "by_risk_level": by_level,
        "by_category": by_category,
    }

