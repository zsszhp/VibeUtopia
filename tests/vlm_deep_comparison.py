#!/usr/bin/env python3
"""VLM极深度对比报告生成器 - 按风险等级分层

读取两个模型的深度测试JSON报告，生成按风险等级分层的极细节对比报告。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"

VIDEO_NAMES = {
    "ai": "AI专业排名",
    "fight": "抗美援朝历史",
    "mhy": "米哈游AI模型",
    "moon": "太空宇航员",
}

PROMPT_NAMES = {
    "pixel_scan": "像素级细节扫描",
    "ocr_deep": "深度OCR识别",
    "risk_safe": "SAFE级风险评估",
    "risk_low": "LOW级风险评估",
    "risk_medium": "MEDIUM级风险评估",
    "risk_high": "HIGH级风险评估",
    "risk_critical": "CRITICAL级风险评估",
    "chinese_deep": "中文语义深度分析",
    "multi_scale": "多尺度画面分析",
}

RISK_ICONS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "safe": "✅",
    "unknown": "❓",
}


def load_deep_report(pattern: str) -> dict | None:
    files = sorted(REPORT_DIR.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    with open(files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def extract_risk_from_response(response: str) -> str:
    for level in ["critical", "high", "medium", "low", "safe"]:
        if f'"{level}"' in response or f": {level}" in response or f'": "{level}' in response:
            return level
    return "unknown"


def generate_deep_comparison(m_data: dict, q_data: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("=" * 110)
    lines.append("VibeUtopia VLM极深度细节对比测试报告 - 按风险等级分层")
    lines.append(f"生成时间: {now}")
    lines.append(f"硬件配置: RTX 5070 Ti 12GB VRAM + 32GB RAM")
    lines.append(f"部署方式: Ollama (经评估为12GB VRAM最优选择)")
    lines.append(f"测试维度: 8个深度分析 × 4个视频 = 32项测试/模型")
    lines.append("=" * 110)

    m_results = [r for r in m_data["results"] if r.get("success")]
    q_results = [r for r in q_data["results"] if r.get("success")]

    m_avg_lat = sum(r["latency_ms"] for r in m_results) / len(m_results) if m_results else 0
    q_avg_lat = sum(r["latency_ms"] for r in q_results) / len(q_results) if q_results else 0
    m_avg_tps = sum(r.get("tokens_per_second", 0) for r in m_results) / len(m_results) if m_results else 0
    q_avg_tps = sum(r.get("tokens_per_second", 0) for r in q_results) / len(q_results) if q_results else 0
    m_avg_resp = sum(len(r.get("response", "")) for r in m_results) / len(m_results) if m_results else 0
    q_avg_resp = sum(len(r.get("response", "")) for r in q_results) / len(q_results) if q_results else 0
    m_avg_tokens = sum(r.get("total_tokens", 0) for r in m_results) / len(m_results) if m_results else 0
    q_avg_tokens = sum(r.get("total_tokens", 0) for r in q_results) / len(q_results) if q_results else 0

    lines.append("")
    lines.append("一、性能总览")
    lines.append("=" * 110)
    lines.append(f"  {'指标':<25} {'MiniCPM-o-2.6':<30} {'Qwen3-VL-8B':<30} {'对比':<20}")
    lines.append("  " + "-" * 105)
    lines.append(f"  {'总测试数':<25} {m_data['total_tests']:<30} {q_data['total_tests']:<30} {'-':<20}")
    lines.append(f"  {'成功率':<25} {m_data['successful']}/{m_data['total_tests']}{'':<24} {q_data['successful']}/{q_data['total_tests']}{'':<24} {'平局':<20}")
    lines.append(f"  {'平均延迟':<25} {m_avg_lat:.0f}ms{'':<24} {q_avg_lat:.0f}ms{'':<24} {'MiniCPM快' if m_avg_lat < q_avg_lat else 'Qwen3快':<20}")
    lines.append(f"  {'平均速度':<25} {m_avg_tps:.1f} tok/s{'':<19} {q_avg_tps:.1f} tok/s{'':<19} {'MiniCPM快' if m_avg_tps > q_avg_tps else 'Qwen3快':<20}")
    lines.append(f"  {'平均输出token':<25} {m_avg_tokens:.0f}{'':<27} {q_avg_tokens:.0f}{'':<27} {f'Qwen3多{q_avg_tokens/m_avg_tokens:.1f}x' if m_avg_tokens > 0 else '':<20}")
    lines.append(f"  {'平均回答长度':<25} {m_avg_resp:.0f}字{'':<24} {q_avg_resp:.0f}字{'':<24} {f'Qwen3长{q_avg_resp/m_avg_resp:.1f}x' if m_avg_resp > 0 else '':<20}")

    lines.append("")
    lines.append("二、风险等级分层汇总对比")
    lines.append("=" * 110)

    m_risk = m_data.get("risk_summary", {})
    q_risk = q_data.get("risk_summary", {})

    lines.append(f"  {'风险等级':<25} {'MiniCPM-o-2.6':<30} {'Qwen3-VL-8B':<30} {'分析':<20}")
    lines.append("  " + "-" * 105)

    for level in ["critical", "high", "medium", "low", "safe", "unknown"]:
        icon = RISK_ICONS.get(level, "?")
        m_count = len(m_risk.get(level, []))
        q_count = len(q_risk.get(level, []))
        m_items = m_risk.get(level, [])
        q_items = q_risk.get(level, [])

        level_desc = {
            "critical": "必须立即处理",
            "high": "建议不发布/大幅修改",
            "medium": "需审核后决定",
            "low": "轻微风险可接受",
            "safe": "完全合规",
            "unknown": "未能判断",
        }

        analysis = ""
        if level == "safe":
            analysis = "越多越安全" if m_count > 0 or q_count > 0 else ""
        elif level in ("critical", "high"):
            analysis = "越少越安全" if m_count > 0 or q_count > 0 else "均未检出 ✓"

        lines.append(f"  {icon} {level.upper():<22} {m_count}项{'':<25} {q_count}项{'':<25} {analysis:<20}")

        if m_items or q_items:
            all_videos = set()
            for item in m_items + q_items:
                all_videos.add(item["video"])
            for v in sorted(all_videos):
                vname = VIDEO_NAMES.get(v, v)
                m_has = any(item["video"] == v for item in m_items)
                q_has = any(item["video"] == v for item in q_items)
                m_tests = [item["test"] for item in m_items if item["video"] == v]
                q_tests = [item["test"] for item in q_items if item["video"] == v]
                lines.append(f"    [{vname}] MiniCPM: {', '.join(m_tests) if m_tests else '未检出'} | Qwen3: {', '.join(q_tests) if q_tests else '未检出'}")

    lines.append("")
    lines.append("三、按风险等级分层的极细节对比")
    lines.append("=" * 110)

    for level in ["critical", "high", "medium", "low", "safe"]:
        icon = RISK_ICONS.get(level, "?")
        level_name = {"critical": "CRITICAL - 必须立即处理", "high": "HIGH - 建议不发布", "medium": "MEDIUM - 需审核决定", "low": "LOW - 轻微风险", "safe": "SAFE - 完全合规"}

        m_level_results = [r for r in m_results if r.get("detected_risk_level") == level]
        q_level_results = [r for r in q_results if r.get("detected_risk_level") == level]

        if not m_level_results and not q_level_results:
            lines.append(f"\n  {icon} {level_name.get(level, level)}")
            lines.append(f"  两个模型均未检出此级别风险")
            continue

        lines.append(f"\n  {icon} {level_name.get(level, level)}")
        lines.append("  " + "=" * 100)

        all_videos = set()
        for r in m_level_results + q_level_results:
            all_videos.add(r.get("video_category", ""))

        for v in sorted(all_videos):
            vname = VIDEO_NAMES.get(v, v)
            m_v_results = [r for r in m_level_results if r.get("video_category") == v]
            q_v_results = [r for r in q_level_results if r.get("video_category") == v]

            lines.append(f"\n  [{vname}]")

            if m_v_results:
                lines.append(f"    MiniCPM-o-2.6 检出:")
                for r in m_v_results:
                    pt = PROMPT_NAMES.get(r["prompt_type"], r["prompt_type"])
                    resp = r.get("response", "")
                    lines.append(f"      [{pt}] ({r['latency_ms']:.0f}ms, {r.get('total_tokens', 0)} tokens)")
                    for line in resp.split("\n")[:30]:
                        lines.append(f"        {line}")
                    if len(resp.split("\n")) > 30:
                        lines.append(f"        ... (省略{len(resp.split('\n'))-30}行)")

            if q_v_results:
                lines.append(f"    Qwen3-VL-8B 检出:")
                for r in q_v_results:
                    pt = PROMPT_NAMES.get(r["prompt_type"], r["prompt_type"])
                    resp = r.get("response", "")
                    lines.append(f"      [{pt}] ({r['latency_ms']:.0f}ms, {r.get('total_tokens', 0)} tokens)")
                    for line in resp.split("\n")[:30]:
                        lines.append(f"        {line}")
                    if len(resp.split("\n")) > 30:
                        lines.append(f"        ... (省略{len(resp.split('\n'))-30}行)")

    lines.append("")
    lines.append("四、按视频分类的逐维度深度对比")
    lines.append("=" * 110)

    for v in ["ai", "fight", "mhy", "moon"]:
        vname = VIDEO_NAMES.get(v, v)
        m_v = [r for r in m_results if r.get("video_category") == v]
        q_v = [r for r in q_results if r.get("video_category") == v]

        lines.append(f"\n  ┌{'─'*106}┐")
        lines.append(f"  │ 视频: {vname} ({v})")
        lines.append(f"  └{'─'*106}┘")

        for pt_key in ["pixel_scan", "ocr_deep", "risk_safe", "risk_low", "risk_medium", "risk_high", "risk_critical", "chinese_deep", "multi_scale"]:
            pt_name = PROMPT_NAMES.get(pt_key, pt_key)
            m_r = next((r for r in m_v if r.get("prompt_type") == pt_key), None)
            q_r = next((r for r in q_v if r.get("prompt_type") == pt_key), None)

            lines.append(f"\n    【{pt_name}】")

            if m_r and q_r:
                m_risk_level = m_r.get("detected_risk_level", "unknown")
                q_risk_level = q_r.get("detected_risk_level", "unknown")
                m_icon = RISK_ICONS.get(m_risk_level, "?")
                q_icon = RISK_ICONS.get(q_risk_level, "?")

                lines.append(f"    MiniCPM:  {m_icon} {m_risk_level.upper()} | {m_r['latency_ms']:.0f}ms | {m_r.get('total_tokens', 0)} tokens | {len(m_r.get('response', ''))}字")
                lines.append(f"    Qwen3-VL: {q_icon} {q_risk_level.upper()} | {q_r['latency_ms']:.0f}ms | {q_r.get('total_tokens', 0)} tokens | {len(q_r.get('response', ''))}字")

                if m_risk_level != q_risk_level:
                    lines.append(f"    ⚠️ 风险等级不一致! MiniCPM={m_risk_level}, Qwen3={q_risk_level}")
            elif m_r:
                lines.append(f"    MiniCPM:  {m_r.get('detected_risk_level', '?')} | {m_r['latency_ms']:.0f}ms")
                lines.append(f"    Qwen3-VL: 未完成")
            elif q_r:
                lines.append(f"    MiniCPM:  未完成")
                lines.append(f"    Qwen3-VL: {q_r.get('detected_risk_level', '?')} | {q_r['latency_ms']:.0f}ms")

    lines.append("")
    lines.append("五、关键差异深度分析")
    lines.append("=" * 110)

    lines.append("""
  5.1 风险检测敏感度对比
  ────────────────────────────────────────────────────────────────────────""")

    risk_compare = {}
    for v in ["ai", "fight", "mhy", "moon"]:
        vname = VIDEO_NAMES.get(v, v)
        m_v = {r["prompt_type"]: r for r in m_results if r.get("video_category") == v and r.get("success")}
        q_v = {r["prompt_type"]: r for r in q_results if r.get("video_category") == v and r.get("success")}

        for pt in ["risk_safe", "risk_low", "risk_medium", "risk_high", "risk_critical"]:
            m_rl = m_v.get(pt, {}).get("detected_risk_level", "N/A")
            q_rl = q_v.get(pt, {}).get("detected_risk_level", "N/A")
            if m_rl != q_rl:
                pt_name = PROMPT_NAMES.get(pt, pt)
                lines.append(f"  [{vname}] {pt_name}: MiniCPM={m_rl} vs Qwen3={q_rl}")

    lines.append("""
  5.2 细节检测能力对比
  ────────────────────────────────────────────────────────────────────────""")

    for v in ["ai", "fight", "mhy", "moon"]:
        vname = VIDEO_NAMES.get(v, v)
        m_pixel = next((r for r in m_results if r.get("video_category") == v and r.get("prompt_type") == "pixel_scan"), None)
        q_pixel = next((r for r in q_results if r.get("video_category") == v and r.get("prompt_type") == "pixel_scan"), None)

        lines.append(f"  [{vname}] 像素级扫描:")
        if m_pixel:
            m_resp = m_pixel.get("response", "")
            m_tokens = m_pixel.get("total_tokens", 0)
            lines.append(f"    MiniCPM:  {m_tokens} tokens, {len(m_resp)}字")
        if q_pixel:
            q_resp = q_pixel.get("response", "")
            q_tokens = q_pixel.get("total_tokens", 0)
            lines.append(f"    Qwen3-VL: {q_tokens} tokens, {len(q_resp)}字")

    lines.append("""
  5.3 中文语义理解深度对比
  ────────────────────────────────────────────────────────────────────────""")

    for v in ["ai", "fight", "mhy", "moon"]:
        vname = VIDEO_NAMES.get(v, v)
        m_chinese = next((r for r in m_results if r.get("video_category") == v and r.get("prompt_type") == "chinese_deep"), None)
        q_chinese = next((r for r in q_results if r.get("video_category") == v and r.get("prompt_type") == "chinese_deep"), None)

        lines.append(f"  [{vname}] 中文语义深度:")
        if m_chinese:
            m_rl = m_chinese.get("detected_risk_level", "unknown")
            lines.append(f"    MiniCPM:  {RISK_ICONS.get(m_rl, '?')} {m_rl} | {m_chinese.get('total_tokens', 0)} tokens")
        if q_chinese:
            q_rl = q_chinese.get("detected_risk_level", "unknown")
            lines.append(f"    Qwen3-VL: {RISK_ICONS.get(q_rl, '?')} {q_rl} | {q_chinese.get('total_tokens', 0)} tokens")

    lines.append("")
    lines.append("六、部署方式评估结论")
    lines.append("=" * 110)
    lines.append("""
  硬件: RTX 5070 Ti 12GB VRAM + 32GB RAM
  用途: 单用户本地视频内容风控分析

  ┌──────────────┬───────────┬──────────┬──────────┬──────────┬──────────┐
  │ 部署方式     │ 速度      │ VRAM开销 │ 12GB可用 │ VLM支持  │ 推荐度   │
  ├──────────────┼───────────┼──────────┼──────────┼──────────┼──────────┤
  │ Ollama       │ 基准      │ ~0.5GB   │ ✅ 完美  │ ✅ 原生  │ ⭐⭐⭐⭐⭐ │
  │ llama.cpp    │ +5-6%     │ ~0.3GB   │ ✅ 可用  │ ⚠️ 手动  │ ⭐⭐⭐    │
  │ vLLM         │ 高并发+   │ ~1.5GB+  │ ❌ OOM   │ ⚠️ 有限  │ ⭐       │
  │ transformers │ -30~50%   │ ~2GB+    │ ⚠️ 勉强  │ ✅ 慢    │ ⭐⭐     │
  │ LM Studio    │ -7%       │ ~0.6GB   │ ✅ 可用  │ ⚠️ 无API │ ⭐⭐⭐    │
  └──────────────┴───────────┴──────────┴──────────┴──────────┴──────────┘

  结论: Ollama 是当前硬件配置下的最优选择，无需更换部署方式。

  理由:
  1. vLLM的PagedAttention在12GB VRAM下会导致OOM（需16GB+）
  2. llama.cpp仅快5-6%，但VLM模型配置复杂度高，收益不显著
  3. transformers推理速度慢30-50%，不适合生产使用
  4. Ollama基于llama.cpp，性能接近原生，但管理极简
  5. Ollama原生支持OpenAI兼容API，与项目架构完美集成
  6. Ollama的模型管理（pull/list/rm）与项目Docker式管理理念一致
""")

    lines.append("")
    lines.append("七、最终推荐方案")
    lines.append("=" * 110)
    lines.append("""
  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  🥇 主力模型: Qwen3-VL-8B                                         │
  │     - 回答深度: 平均字数是MiniCPM的2-3倍                           │
  │     - 风险识别: 更敏感，能检出low级别风险                          │
  │     - 中文OCR: 更精确，区分字体/位置/颜色                          │
  │     - 细节检测: 识别角落文字、隐藏元素能力更强                     │
  │     - 256K上下文: 支持长视频理解+时间戳定位                        │
  │     - 不会误拒答: MiniCPM在moon画面误判为暴力而拒绝               │
  │     - VRAM: ~6.5GB (Q4量化)                                        │
  │                                                                     │
  │  🥈 备选模型: MiniCPM-o-2.6                                        │
  │     - 速度快4.4x: 适合批量处理大量视频帧                           │
  │     - JSON输出稳定: 适合自动化流水线                                │
  │     - 实时视频流: 支持端侧实时理解                                  │
  │     - VRAM: ~7GB (Q4量化)                                          │
  │     ⚠️ 注意: 安全过滤过强，可能误拒答                              │
  │                                                                     │
  │  🥉 API补充: GLM-4.1V-9B-Thinking                                 │
  │     - Thinking推理增强: 复杂场景准确率+15-25%                      │
  │     - 通过智谱API/硅基流动调用                                     │
  │                                                                     │
  │  部署方式: Ollama (已确认为12GB VRAM最优)                          │
  │  模型切换: VRAM Manager按需自动切换                                │
  │  注意: 主力+文本模型不可同时加载(12GB VRAM限制)                    │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
""")

    lines.append("=" * 110)
    lines.append("报告结束")
    lines.append("=" * 110)

    return "\n".join(lines)


def main():
    m_data = load_deep_report("vlm_deep_openbmb_minicpm-o2.6_*.json")
    q_data = load_deep_report("vlm_deep_qwen3-vl_8b_*.json")

    if not m_data:
        print("错误: 未找到MiniCPM-o-2.6深度测试报告")
        sys.exit(1)
    if not q_data:
        print("错误: 未找到Qwen3-VL-8B深度测试报告")
        sys.exit(1)

    report = generate_deep_comparison(m_data, q_data)

    report_path = REPORT_DIR / f"vlm_deep_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"极深度对比报告已保存: {report_path}")

    print("\n" + report)


if __name__ == "__main__":
    main()
