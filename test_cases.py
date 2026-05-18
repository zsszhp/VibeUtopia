import httpx
import asyncio
import json
import sys
import os

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)

API_BASE = "http://localhost:8000/api/v1"

CASES = {
    "AI一键脱衣黑产": """# "AI一键脱衣"黑产：9.9元就能毁掉一个女性的名誉

2026年初，中国官媒下场斥责"AI一键脱衣"黑色产业链，引发全社会关注。

这项黑产的操作模式极其简单：只需一张普通女性照片和9.9元，就能通过AI深度伪造技术生成极其逼真的"裸照"。这些伪造图片被用于敲诈勒索、网络暴力、人肉搜索，甚至被批量出售到色情网站。

受害者的遭遇触目惊心：有人被前男友用AI生成"裸照"后威胁复合；有人因社交媒体头像被AI处理后发到色情论坛，导致工作丢失、家庭破裂；有大学生因同学恶意P图而患上抑郁症退学。

更令人担忧的是，这类工具正在快速扩散。多家电商平台和社交平台上，以"AI换脸""照片处理"为关键词的商品月销量过万。有商家甚至在商品描述中暗示"特殊用途"，规避平台审查。

法律界人士指出，AI伪造他人裸照至少涉及三项违法：侵犯肖像权、侵犯隐私权、制作传播淫秽物品。如果用于敲诈勒索，更是刑事犯罪。但实际执法面临困难——黑产多使用境外服务器，交易通过加密聊天工具完成，受害者往往因羞耻感不愿报警。

中国官媒在报道中严厉批评了这一黑产，称"技术不应成为伤害的工具"，呼吁加快AI立法、加强平台审核责任、提高违法成本。多位人大代表已提交关于AI深度伪造立法的提案。

与此同时，AI换脸技术在影视制作、虚拟试衣等合法领域的应用也在快速发展。如何在保护创新的同时遏制黑产，成为政策制定者面临的难题。""",

    "王妈背刺打工人": """# 案例二：王妈背刺打工人事件

短视频角色"王妈"因短剧《重生之我在霸总短剧里当保姆》走红，她在剧中为打工人仗义执言、吐槽职场不公，成了"互联网嘴替"，扮演者"七颗猩猩"收获超千万粉丝。

然而去年5月，有网友发现"七颗猩猩"所属的武汉荒野文化传媒有限公司问题重重：招聘软件显示公司实行大小周，员工需自备电脑，工资仅4000元左右且加班频繁。这与王妈在剧中维护打工人权益的形象形成鲜明反差，网友怒称被"背刺"，#王妈塌房#迅速登上热搜。

面对舆论，荒野文化迅速回应：即日起实行双休、试用期缴纳社保、员工薪资不低于6000元、规范群演招募与薪资结算、升级工作设备。

尽管公司有所行动，但网友并不买账，指出这恰恰证明了此前确实存在压榨员工的事实，王妈人设彻底崩塌。更讽刺的是，同样是在2024年11月，另一个网红"羊毛月"嘲讽00后找不到工作"都想来卷我们当网红"，被批"何不食肉糜"，随后其北大本科学历也被打假。

两个案例共同揭示了一个残酷现实：很多与打工人共情的网红，背后可能就是他们口中"霸总"的化身。""",

    "哈佛蒋雨融演讲争议": """# 哈佛中国毕业生蒋雨融演讲引发赞誉与争议

在美国签证风波的背景下，哈佛大学中国毕业生蒋雨融的毕业演讲引发了中美两国社交媒体上的截然不同反响。

蒋雨融在哈佛毕业典礼上的演讲以流利的英文讲述了自己从中国到美国求学的经历，强调了跨文化理解的重要性和教育的力量。演讲视频在中文社交媒体上迅速传播，许多人为她感到骄傲，认为她代表了中国年轻一代的国际视野和竞争力。

然而，争议也随之而来。一些批评者质疑她是否"代表中国"发言，认为她的演讲内容过于迎合西方视角。还有人指出，能进入哈佛本身就意味着她的家庭背景和资源远超普通中国人，她的经历不能被当作"普通人可以通过教育改变命运"的例证。

在美国方面，一些保守派媒体将她作为中国"渗透"美国高校的例子，恰逢美国政府收紧对中国学生签证政策的时期。这种将个体经历政治化的做法，让蒋雨融成为地缘政治博弈中的一个符号。

更深层的问题是：一个中国留学生的个人表达，为什么会被赋予如此多的政治意义？在两国关系紧张的背景下，每一个站在国际舞台上的华人都可能面临"站队"的压力，这种二元对立的叙事框架本身是否公平？

有评论指出，蒋雨融的演讲之所以引发争议，恰恰反映了当下中美关系的紧张程度——连一个毕业演讲都能成为舆论战场，说明双方的不信任已经渗透到了文化交流的最基础层面。"""
}


async def submit_review(name, content):
    payload = {
        "mode": "text",
        "texts": [{"type": "text", "content": content}],
        "options": {
            "depth": "quick",
            "platforms": ["bilibili", "xiaohongshu", "zhihu", "douyin"],
            "enable_simulation": False
        }
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{API_BASE}/review", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[{name}] 提交成功: task_id={data['task_id']}, status={data['status']}")
            return data["task_id"]
        else:
            print(f"[{name}] 提交失败: {resp.status_code} {resp.text}")
            return None


async def get_result(task_id, name, max_wait=600):
    import time
    start = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() - start < max_wait:
            resp = await client.get(f"{API_BASE}/review/{task_id}")
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "")
                if status in ("completed", "done", "failed"):
                    return data
                progress = data.get("progress", 0)
                step = data.get("current_step", "")
                print(f"  [{name}] 进度: {progress:.0%} 步骤: {step}")
            await asyncio.sleep(5)
    return None


async def main():
    task_ids = {}
    for name, content in CASES.items():
        tid = await submit_review(name, content)
        if tid:
            task_ids[name] = tid

    print(f"\n已提交 {len(task_ids)} 个案例，等待结果...\n")

    results = {}
    for name, tid in task_ids.items():
        print(f"等待 [{name}] 结果...")
        result = await get_result(tid, name)
        if result:
            results[name] = result

    report_path = "D:/project/VibeUtopia/test_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# VibeUtopia 风控测试报告\n\n")
        f.write(f"> 测试时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"> 测试案例数: {len(CASES)}\n")
        f.write(f"> 成功分析数: {len(results)}\n\n")
        f.write("---\n\n")

        for name, result in results.items():
            f.write(f"## 案例：{name}\n\n")
            f.write(f"- **状态**: {result.get('status', 'N/A')}\n")
            risk_level = result.get("risk_level", "N/A")
            overall_risk = result.get("overall_risk", "N/A")
            f.write(f"- **风险等级**: {risk_level}\n")
            f.write(f"- **综合风险分**: {overall_risk}\n\n")

            dimensions = result.get("dimensions", {})
            if dimensions:
                f.write("### 各维度评分\n\n")
                f.write("| 维度 | 分数 | 等级 |\n|------|------|------|\n")
                for dim, info in dimensions.items():
                    if isinstance(info, dict):
                        score = info.get("score", "N/A")
                        level = info.get("level", "N/A")
                        f.write(f"| {dim} | {score} | {level} |\n")
                f.write("\n")

            risk_items = result.get("risk_items", [])
            if risk_items:
                f.write("### 风险项详情\n\n")
                for item in risk_items:
                    if isinstance(item, dict):
                        f.write(f"- **{item.get('dimension', '未知')}**: {item.get('sentence', 'N/A')} (分数: {item.get('score', 'N/A')}, 原因: {item.get('reason', 'N/A')})\n")
                f.write("\n")

            reactions = result.get("platform_reactions", {})
            if reactions:
                f.write("### 平台反应模拟\n\n")
                for platform, plat_data in reactions.items():
                    f.write(f"#### {platform}\n\n")
                    if isinstance(plat_data, dict):
                        for sentiment, reaction in plat_data.items():
                            f.write(f"- **{sentiment}**: {reaction}\n")
                    elif isinstance(plat_data, list):
                        for r in plat_data:
                            f.write(f"- {r}\n")
                    f.write("\n")

            rewrites = result.get("rewrite_suggestions", [])
            if rewrites:
                f.write("### 安全改写建议\n\n")
                for rw in rewrites:
                    if isinstance(rw, dict):
                        f.write(f"- 原句: {rw.get('original', 'N/A')}\n")
                        for i, alt in enumerate(rw.get('alternatives', []), 1):
                            f.write(f"  - 改写{i}: {alt}\n")
                f.write("\n")

            f.write("---\n\n")

    print(f"\n测试报告已保存到: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
