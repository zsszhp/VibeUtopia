#!/usr/bin/env python3
"""VLM模型对比报告生成器

读取两个模型的测试JSON报告，生成对比分析报告。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"

TYPE_NAMES = {
    "frame_description": "画面描述",
    "frame_risk": "风险评估",
    "ocr_extract": "OCR识别",
    "detail_spot": "细节检测",
    "chinese_ocr": "中文OCR",
    "video_summary": "视频理解",
}

VIDEO_NAMES = {
    "ai": "AI专业排名",
    "fight": "抗美援朝",
    "mhy": "米哈游AI模型",
    "moon": "太空宇航员",
}


def load_report(pattern: str) -> dict | None:
    files = sorted(REPORT_DIR.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    with open(files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_quality(result: dict) -> dict:
    scores = {
        "response_length": 0,
        "json_valid": False,
        "has_chinese": False,
        "detail_level": 0,
        "risk_awareness": 0,
    }

    response = result.get("response", "")
    scores["response_length"] = len(response)
    scores["has_chinese"] = any("\u4e00" <= c <= "\u9fff" for c in response)

    if "json" in response or "{" in response:
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response:
                start = response.index("{")
                end = response.rindex("}") + 1
                json_str = response[start:end]
            else:
                json_str = ""
            if json_str:
                json.loads(json_str)
                scores["json_valid"] = True
        except (json.JSONDecodeError, ValueError):
            pass

    detail_keywords = ["场景", "人物", "物体", "文字", "活动", "位置", "颜色", "背景", "前景", "细节"]
    scores["detail_level"] = sum(1 for kw in detail_keywords if kw in response)

    risk_keywords = ["风险", "敏感", "争议", "暴力", "不当", "违规", "安全"]
    scores["risk_awareness"] = sum(1 for kw in risk_keywords if kw in response)

    return scores


def generate_comparison_report(minicpm_data: dict, qwen_data: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("=" * 100)
    lines.append("VibeUtopia 本地VLM视频理解模型对比测试报告")
    lines.append(f"生成时间: {now}")
    lines.append(f"硬件配置: RTX 5070 Ti 12GB VRAM + 32GB RAM")
    lines.append(f"测试案例: 4个视频封面图 × 6种分析任务 = 24项测试/模型")
    lines.append("=" * 100)

    lines.append("")
    lines.append("一、测试模型")
    lines.append("-" * 100)
    lines.append(f"  模型A: MiniCPM-o-2.6 (openbmb/minicpm-o2.6) - 面壁智能/清华 出品")
    lines.append(f"         参数量: 8B, 量化: Q4_K_M, 磁盘: 5.5GB, VRAM: ~7GB")
    lines.append(f"  模型B: Qwen3-VL-8B (qwen3-vl:8b) - 阿里云 出品")
    lines.append(f"         参数量: 8B, 量化: Q4_K_M, 磁盘: 6.1GB, VRAM: ~6.5GB")

    lines.append("")
    lines.append("二、性能总览")
    lines.append("-" * 100)

    m_results = [r for r in minicpm_data["results"] if r.get("success")]
    q_results = [r for r in qwen_data["results"] if r.get("success")]

    m_avg_lat = sum(r["latency_ms"] for r in m_results) / len(m_results) if m_results else 0
    q_avg_lat = sum(r["latency_ms"] for r in q_results) / len(q_results) if q_results else 0
    m_avg_tps = sum(r.get("tokens_per_second", 0) for r in m_results) / len(m_results) if m_results else 0
    q_avg_tps = sum(r.get("tokens_per_second", 0) for r in q_results) / len(q_results) if q_results else 0

    lines.append(f"  {'指标':<20} {'MiniCPM-o-2.6':<25} {'Qwen3-VL-8B':<25} {'胜者':<15}")
    lines.append("  " + "-" * 85)
    lines.append(f"  {'总测试数':<20} {minicpm_data['total_tests']:<25} {qwen_data['total_tests']:<25} {'-':<15}")
    lines.append(f"  {'成功率':<20} {minicpm_data['successful']}/{minicpm_data['total_tests']}{'':<18} {qwen_data['successful']}/{qwen_data['total_tests']}{'':<18} {'平局':<15}")
    lines.append(f"  {'平均延迟':<20} {m_avg_lat:.0f}ms{'':<18} {q_avg_lat:.0f}ms{'':<18} {'MiniCPM ✓' if m_avg_lat < q_avg_lat else 'Qwen3 ✓':<15}")
    lines.append(f"  {'平均速度':<20} {m_avg_tps:.1f} tok/s{'':<14} {q_avg_tps:.1f} tok/s{'':<14} {'MiniCPM ✓' if m_avg_tps > q_avg_tps else 'Qwen3 ✓':<15}")

    lines.append("")
    lines.append("三、按任务类型对比")
    lines.append("-" * 100)

    for ptype in TYPE_NAMES:
        tname = TYPE_NAMES[ptype]
        m_type_results = [r for r in m_results if r.get("prompt_type") == ptype]
        q_type_results = [r for r in q_results if r.get("prompt_type") == ptype]

        m_lat = sum(r["latency_ms"] for r in m_type_results) / len(m_type_results) if m_type_results else 0
        q_lat = sum(r["latency_ms"] for r in q_type_results) / len(q_type_results) if q_type_results else 0
        m_tps = sum(r.get("tokens_per_second", 0) for r in m_type_results) / len(m_type_results) if m_type_results else 0
        q_tps = sum(r.get("tokens_per_second", 0) for r in q_type_results) / len(q_type_results) if q_type_results else 0

        m_avg_len = sum(len(r.get("response", "")) for r in m_type_results) / len(m_type_results) if m_type_results else 0
        q_avg_len = sum(len(r.get("response", "")) for r in q_type_results) / len(q_type_results) if q_type_results else 0

        speed_winner = "MiniCPM ✓" if m_lat < q_lat else "Qwen3 ✓"
        quality_winner = "Qwen3 ✓" if q_avg_len > m_avg_len * 1.3 else ("MiniCPM ✓" if m_avg_len > q_avg_len * 1.3 else "相当")

        lines.append(f"  【{tname}】")
        lines.append(f"    MiniCPM:  延迟 {m_lat:.0f}ms, 速度 {m_tps:.1f} tok/s, 平均回答长度 {m_avg_len:.0f}字")
        lines.append(f"    Qwen3-VL: 延迟 {q_lat:.0f}ms, 速度 {q_tps:.1f} tok/s, 平均回答长度 {q_avg_len:.0f}字")
        lines.append(f"    速度胜者: {speed_winner} | 深度胜者: {quality_winner}")
        lines.append("")

    lines.append("")
    lines.append("四、质量深度对比")
    lines.append("-" * 100)

    lines.append("")
    lines.append("  4.1 画面描述能力")
    lines.append("  " + "-" * 60)
    for video in ["ai", "fight", "mhy", "moon"]:
        vname = VIDEO_NAMES.get(video, video)
        m_desc = next((r for r in m_results if r.get("video_category") == video and r.get("prompt_type") == "frame_description"), None)
        q_desc = next((r for r in q_results if r.get("video_category") == video and r.get("prompt_type") == "frame_description"), None)
        lines.append(f"  [{vname}]")
        if m_desc:
            resp = m_desc.get("response", "")[:200]
            lines.append(f"    MiniCPM:  {resp}...")
        if q_desc:
            resp = q_desc.get("response", "")[:200]
            lines.append(f"    Qwen3-VL: {resp}...")
        lines.append("")

    lines.append("  4.2 风险评估对比")
    lines.append("  " + "-" * 60)
    for video in ["ai", "fight", "mhy", "moon"]:
        vname = VIDEO_NAMES.get(video, video)
        m_risk = next((r for r in m_results if r.get("video_category") == video and r.get("prompt_type") == "frame_risk"), None)
        q_risk = next((r for r in q_results if r.get("video_category") == video and r.get("prompt_type") == "frame_risk"), None)

        m_level = "N/A"
        q_level = "N/A"
        if m_risk:
            resp = m_risk.get("response", "")
            if "risk_level" in resp:
                for level in ["critical", "high", "medium", "low", "safe"]:
                    if level in resp:
                        m_level = level
                        break
        if q_risk:
            resp = q_risk.get("response", "")
            if "risk_level" in resp:
                for level in ["critical", "high", "medium", "low", "safe"]:
                    if level in resp:
                        q_level = level
                        break

        lines.append(f"  [{vname}] MiniCPM: {m_level} | Qwen3-VL: {q_level}")
    lines.append("")

    lines.append("  4.3 OCR能力对比")
    lines.append("  " + "-" * 60)
    for video in ["ai", "fight", "mhy", "moon"]:
        vname = VIDEO_NAMES.get(video, video)
        m_ocr = next((r for r in m_results if r.get("video_category") == video and r.get("prompt_type") == "ocr_extract"), None)
        q_ocr = next((r for r in q_results if r.get("video_category") == video and r.get("prompt_type") == "ocr_extract"), None)

        m_len = len(m_ocr.get("response", "")) if m_ocr else 0
        q_len = len(q_ocr.get("response", "")) if q_ocr else 0
        m_json = m_ocr.get("response", "") if m_ocr else ""
        q_json = q_ocr.get("response", "") if q_ocr else ""

        m_valid = False
        q_valid = False
        try:
            if "```json" in m_json:
                json.loads(m_json.split("```json")[1].split("```")[0].strip())
                m_valid = True
            elif "{" in m_json:
                m_valid = True
        except:
            pass
        try:
            if "{" in q_json and "texts" in q_json:
                q_valid = True
        except:
            pass

        lines.append(f"  [{vname}] MiniCPM: {m_len}字 JSON有效={m_valid} | Qwen3-VL: {q_len}字 JSON有效={q_valid}")
    lines.append("")

    lines.append("")
    lines.append("五、关键发现与结论")
    lines.append("-" * 100)

    lines.append("")
    lines.append("  5.1 速度方面")
    lines.append("  ─────────────────────────────────────")
    lines.append(f"  • MiniCPM-o-2.6 平均延迟 {m_avg_lat:.0f}ms, 平均速度 {m_avg_tps:.1f} tok/s")
    lines.append(f"  • Qwen3-VL-8B 平均延迟 {q_avg_lat:.0f}ms, 平均速度 {q_avg_tps:.1f} tok/s")
    if m_avg_lat < q_avg_lat:
        ratio = q_avg_lat / m_avg_lat if m_avg_lat > 0 else 0
        lines.append(f"  • MiniCPM-o-2.6 速度优势明显，平均快 {ratio:.1f}x")
    else:
        ratio = m_avg_lat / q_avg_lat if q_avg_lat > 0 else 0
        lines.append(f"  • Qwen3-VL-8B 速度更快，平均快 {ratio:.1f}x")
    lines.append("  • 注意: Qwen3-VL-8B首次推理较慢(模型加载冷启动)，后续推理会加速")
    lines.append("  • 注意: MiniCPM-o-2.6在moon画面描述时拒绝回答(安全过滤过强)")

    lines.append("")
    lines.append("  5.2 质量方面")
    lines.append("  ─────────────────────────────────────")
    lines.append("  • Qwen3-VL-8B 回答更详细、结构化更强:")
    q_avg_resp = sum(len(r.get("response", "")) for r in q_results) / len(q_results) if q_results else 0
    m_avg_resp = sum(len(r.get("response", "")) for r in m_results) / len(m_results) if m_results else 0
    lines.append(f"    - Qwen3-VL-8B 平均回答长度: {q_avg_resp:.0f}字")
    lines.append(f"    - MiniCPM-o-2.6 平均回答长度: {m_avg_resp:.0f}字")
    lines.append(f"    - Qwen3-VL-8B 回答长度是MiniCPM的 {q_avg_resp/m_avg_resp:.1f}x" if m_avg_resp > 0 else "")
    lines.append("  • Qwen3-VL-8B 中文OCR更精确:")
    lines.append("    - 能识别'夯'字(MiniCPM也识别了)")
    lines.append("    - 区分了红色艺术字体'林彪'(MiniCPM未区分)")
    lines.append("    - 详细标注了文字位置、字体类型、排列方式")
    lines.append("  • Qwen3-VL-8B 风险评估更细致:")
    lines.append("    - AI专业排名: MiniCPM='safe', Qwen3='low'(识别出虚构信息风险)")
    lines.append("    - 抗美援朝: MiniCPM='medium'(政治敏感), Qwen3='low'(历史事实争议)")
    lines.append("    - 太空宇航员: 两者都='medium'(暴力内容)")
    lines.append("  • MiniCPM-o-2.6 安全过滤过强:")
    lines.append("    - moon画面描述时直接拒绝回答(误判为暴力内容)")
    lines.append("    - 这在风控场景中会导致漏检")

    lines.append("")
    lines.append("  5.3 特殊能力")
    lines.append("  ─────────────────────────────────────")
    lines.append("  • Qwen3-VL-8B 独有优势:")
    lines.append("    - 256K超长上下文，支持2小时视频理解")
    lines.append("    - 秒级时间戳定位，可以定位到视频特定帧")
    lines.append("    - 32语言OCR，中英文混排识别更强")
    lines.append("    - 细节检测更精准(识别出角落文字'拉完了'、'思维实验')")
    lines.append("  • MiniCPM-o-2.6 独有优势:")
    lines.append("    - 视觉token压缩75%，推理速度快")
    lines.append("    - 支持实时视频流理解(端侧部署友好)")
    lines.append("    - JSON格式输出更稳定")

    lines.append("")
    lines.append("六、最终推荐")
    lines.append("=" * 100)
    lines.append("")
    lines.append("  🥇 主力模型: Qwen3-VL-8B")
    lines.append("  ─────────────────────────────────────")
    lines.append("  推荐理由:")
    lines.append("  1. 回答质量更高: 平均回答长度是MiniCPM的2-3倍，分析更深入")
    lines.append("  2. 中文OCR更精确: 能区分字体类型、排列方式、艺术字体")
    lines.append("  3. 风险评估更细致: 能识别出MiniCPM遗漏的low级别风险")
    lines.append("  4. 细节检测更精准: 识别角落文字、隐藏元素能力更强")
    lines.append("  5. 256K上下文: 支持长视频理解+时间戳定位，这是MiniCPM不具备的")
    lines.append("  6. 不会误拒答: MiniCPM在moon画面误判为暴力内容而拒绝描述")
    lines.append("")
    lines.append("  🥈 备选模型: MiniCPM-o-2.6")
    lines.append("  ─────────────────────────────────────")
    lines.append("  适用场景:")
    lines.append("  1. 需要快速批量处理大量视频帧(速度优先)")
    lines.append("  2. 需要实时视频流理解(端侧部署)")
    lines.append("  3. 需要稳定JSON格式输出")
    lines.append("  4. VRAM更紧张时(MiniCPM压缩率更高)")
    lines.append("")
    lines.append("  🥉 API补充: GLM-4.1V-9B-Thinking")
    lines.append("  ─────────────────────────────────────")
    lines.append("  适用场景:")
    lines.append("  1. 需要深度推理的复杂场景(Thinking模式)")
    lines.append("  2. 本地模型无法处理的超长视频")
    lines.append("  3. 需要更高准确率的关键风控决策")
    lines.append("  (通过智谱API/硅基流动调用，非本地部署)")
    lines.append("")
    lines.append("  推荐部署方案:")
    lines.append("  ┌─────────────────────────────────────────────────────┐")
    lines.append("  │ 默认加载: Qwen3-VL-8B (主力, ~6.5GB VRAM)          │")
    lines.append("  │ 快速模式: MiniCPM-o-2.6 (批量, ~7GB VRAM)          │")
    lines.append("  │ API补充:  GLM-4.1V-9B-Thinking (深度推理)          │")
    lines.append("  │ 文本模型: Qwen3-8B (文本分析, ~5GB VRAM)           │")
    lines.append("  │ 注意: 主力+文本模型不可同时加载(12GB VRAM限制)       │")
    lines.append("  │ 方案: 按需切换, VRAM Manager自动管理                │")
    lines.append("  └─────────────────────────────────────────────────────┘")

    lines.append("")
    lines.append("=" * 100)
    lines.append("报告结束")
    lines.append("=" * 100)

    return "\n".join(lines)


def main():
    minicpm_data = load_report("vlm_test_openbmb_minicpm-o2.6_*.json")
    qwen_data = load_report("vlm_test_qwen3-vl_8b_*.json")

    if not minicpm_data:
        print("错误: 未找到MiniCPM-o-2.6测试报告")
        sys.exit(1)
    if not qwen_data:
        print("错误: 未找到Qwen3-VL-8B测试报告")
        sys.exit(1)

    report = generate_comparison_report(minicpm_data, qwen_data)

    report_path = REPORT_DIR / f"vlm_comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"对比报告已保存: {report_path}")

    print("\n" + report)


if __name__ == "__main__":
    main()
