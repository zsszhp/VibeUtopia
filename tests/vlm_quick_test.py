#!/usr/bin/env python3
"""单模型快速VLM测试 - 用于逐个模型测试

使用方式: python tests/vlm_quick_test.py [model_id]
示例: python tests/vlm_quick_test.py openbmb/minicpm-o2.6
      python tests/vlm_quick_test.py qwen3-vl:8b
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("vlm_quick_test")

VIDEO_DIR = Path(__file__).parent.parent / "tests" / "video"
REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


PROMPTS = {
    "frame_description": "请详细描述这个视频画面中的内容，用于内容风控分析。\n\n请从以下角度描述：\n1. 场景：画面发生的地点和环境\n2. 人物：出现的人物及其动作、表情\n3. 物体：画面中的关键物体、产品、标志\n4. 文字：画面中出现的文字内容（标题、字幕、标签等）\n5. 活动：正在进行的活动或事件\n\n请用简洁的中文描述，每项1-2句话。",

    "frame_risk": "你是一个专业的视频画面风险评估专家。请分析给定的视频关键帧画面，从以下维度检测潜在风险：\n1. 敏感图像：政治敏感人物/场景、军事设施、国家象征不当使用\n2. 不当着装：暴露服装、不当穿着、不雅姿势\n3. 争议符号：极端组织标志、歧视性手势、争议性旗帜\n4. 暴力内容：血腥画面、武器展示、暴力行为\n5. 其他风险：不实信息截图、伪造证件、侵权内容\n\n请以JSON格式返回：\n```json\n{\"risk_level\": \"safe|low|medium|high|critical\", \"risks\": [{\"risk_type\": \"类型\", \"description\": \"描述\", \"severity\": \"high|medium|low\", \"confidence\": 0.0-1.0}], \"summary\": \"摘要\"}\n```",

    "ocr_extract": "请识别并提取这个画面中的所有文字内容。\n\n要求：\n1. 按照从上到下、从左到右的顺序列出所有文字\n2. 区分标题、正文、字幕、水印等不同类型\n3. 特别注意小字、角落文字、叠加文字\n\n请以JSON格式返回：\n```json\n{\"texts\": [{\"content\": \"文字内容\", \"type\": \"title|subtitle|watermark|overlay|other\", \"confidence\": 0.0-1.0}], \"full_text\": \"所有文字拼接\", \"summary\": \"文字内容摘要\"}\n```",

    "detail_spot": "你是一个视频内容细粒度分析专家。请仔细检查这个画面，关注以下细节：\n1. 画面中是否有地图？如果有，地图是否完整？\n2. 画面中是否有代码编辑器/终端界面？\n3. 画面中是否有敏感标志、旗帜、徽章等符号？\n4. 画面角落或边缘是否有被忽略的小文字或小图标？\n5. 画面中是否有任何可能被快速跳过但包含重要信息的元素？\n\n请以JSON格式返回：\n```json\n{\"has_map\": false, \"has_code_editor\": false, \"has_sensitive_symbol\": false, \"corner_text\": \"\", \"hidden_elements\": [], \"detail_findings\": \"详细发现\", \"risk_level\": \"safe|low|medium|high|critical\"}\n```",

    "chinese_ocr": "请仔细识别这个画面中的所有中文文字。特别注意繁体字和简体字、竖排和横排、艺术字体。请列出所有识别到的中文文字并标注位置。",

    "video_summary": "请综合分析这个视频画面，回答：\n1. 这个视频的主题是什么？\n2. 画面传达的核心信息是什么？\n3. 画面中是否有任何可能引发争议的元素？\n4. 如果这是社交媒体视频，目标受众是谁？\n5. 画面内容是否与中文社交媒体内容风控标准存在冲突？\n\n请用中文详细回答。",
}


def encode_image(image_path: str, max_size: int = 1024) -> Optional[str]:
    if not os.path.exists(image_path):
        return None
    try:
        from PIL import Image
        import io
        img = Image.open(image_path)
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error("图片编码失败 %s: %s", image_path, e)
        return None


async def call_vlm(model_id: str, prompt: str, image_b64: str, timeout: int = 120) -> dict:
    url = f"{OLLAMA_BASE_URL}/v1/chat/completions"
    payload = {
        "model": model_id,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": False,
    }
    start = time.time()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
    latency_ms = (time.time() - start) * 1000
    if resp.status_code != 200:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    total_tokens = usage.get("total_tokens", 0)
    tps = total_tokens / (latency_ms / 1000) if latency_ms > 0 and total_tokens > 0 else 0
    return {"content": content, "latency_ms": latency_ms, "tps": tps, "tokens": total_tokens}


async def main():
    model_id = sys.argv[1] if len(sys.argv) > 1 else "openbmb/minicpm-o2.6"
    logger.info("=" * 70)
    logger.info(f"VLM快速测试 - 模型: {model_id}")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info("=" * 70)

    video_dirs = {"ai": "AI相关内容视频", "fight": "争议/冲突类视频", "mhy": "米哈游相关视频", "moon": "月亮/天文类视频"}

    all_results = []

    for subdir, desc in video_dirs.items():
        vdir = VIDEO_DIR / subdir
        if not vdir.exists():
            continue

        for f in sorted(vdir.iterdir()):
            if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue

            logger.info(f"\n{'='*50}")
            logger.info(f"测试图片: {subdir}/{f.name} ({desc})")
            logger.info(f"{'='*50}")

            image_b64 = encode_image(str(f))
            if not image_b64:
                continue

            for prompt_name, prompt in PROMPTS.items():
                test_name = f"{subdir}_{prompt_name}"
                logger.info(f"  [{prompt_name}] 分析中...")

                try:
                    result = await call_vlm(model_id, prompt, image_b64)
                    logger.info(f"  ✓ 完成: {result['latency_ms']:.0f}ms, {result['tps']:.1f} tok/s")

                    response_text = result["content"]
                    if len(response_text) > 600:
                        display = response_text[:600] + "..."
                    else:
                        display = response_text
                    logger.info(f"  回答: {display}")

                    all_results.append({
                        "model": model_id,
                        "test_name": test_name,
                        "video_category": subdir,
                        "prompt_type": prompt_name,
                        "success": True,
                        "latency_ms": result["latency_ms"],
                        "tokens_per_second": result["tps"],
                        "total_tokens": result["tokens"],
                        "response": result["content"],
                    })
                except Exception as e:
                    logger.error(f"  ✗ 失败: {e}")
                    all_results.append({
                        "model": model_id,
                        "test_name": test_name,
                        "video_category": subdir,
                        "prompt_type": prompt_name,
                        "success": False,
                        "error": str(e),
                    })

                await asyncio.sleep(2)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    safe_model_name = model_id.replace("/", "_").replace(":", "_")
    json_path = REPORT_DIR / f"vlm_test_{safe_model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "model": model_id,
            "hardware": {"gpu": "RTX 5070 Ti", "vram_gb": 12, "ram_gb": 32},
            "total_tests": len(all_results),
            "successful": sum(1 for r in all_results if r.get("success")),
            "failed": sum(1 for r in all_results if not r.get("success")),
            "results": all_results,
        }, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"\nJSON报告已保存: {json_path}")

    lines = []
    lines.append("=" * 90)
    lines.append(f"VLM快速测试报告 - {model_id}")
    lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"硬件: RTX 5070 Ti 12GB VRAM + 32GB RAM")
    lines.append("=" * 90)

    successful = [r for r in all_results if r.get("success")]
    failed = [r for r in all_results if not r.get("success")]

    lines.append(f"\n总测试: {len(all_results)}, 成功: {len(successful)}, 失败: {len(failed)}")

    if successful:
        avg_lat = sum(r["latency_ms"] for r in successful) / len(successful)
        avg_tps = sum(r.get("tokens_per_second", 0) for r in successful) / len(successful)
        lines.append(f"平均延迟: {avg_lat:.0f}ms")
        lines.append(f"平均速度: {avg_tps:.1f} tokens/s")

    by_type = {}
    for r in successful:
        pt = r["prompt_type"]
        if pt not in by_type:
            by_type[pt] = []
        by_type[pt].append(r)

    type_names = {
        "frame_description": "画面描述",
        "frame_risk": "风险评估",
        "ocr_extract": "OCR识别",
        "detail_spot": "细节检测",
        "chinese_ocr": "中文OCR",
        "video_summary": "视频理解",
    }

    lines.append(f"\n{'任务类型':<15} {'成功数':<8} {'平均延迟':<12} {'平均速度':<15}")
    lines.append("-" * 50)
    for pt, results in by_type.items():
        avg_l = sum(r["latency_ms"] for r in results) / len(results)
        avg_t = sum(r.get("tokens_per_second", 0) for r in results) / len(results)
        lines.append(f"{type_names.get(pt, pt):<15} {len(results):<8} {avg_l:.0f}ms{'':<6} {avg_t:.1f} tok/s")

    lines.append(f"\n{'='*90}")
    lines.append("详细结果")
    lines.append("=" * 90)

    for r in all_results:
        status = "✓" if r.get("success") else "✗"
        tn = r["test_name"]
        pt = type_names.get(r.get("prompt_type", ""), r.get("prompt_type", ""))
        lines.append(f"\n{status} {tn} [{pt}]")
        if r.get("success"):
            lines.append(f"  延迟: {r['latency_ms']:.0f}ms, 速度: {r.get('tokens_per_second', 0):.1f} tok/s")
            resp = r.get("response", "")
            if len(resp) > 800:
                resp = resp[:800] + "..."
            lines.append(f"  回答: {resp}")
        else:
            lines.append(f"  错误: {r.get('error', 'unknown')}")

    lines.append(f"\n{'='*90}")
    lines.append("报告结束")
    lines.append("=" * 90)

    report_text = "\n".join(lines)
    report_path = REPORT_DIR / f"vlm_test_{safe_model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"可读报告已保存: {report_path}")

    print("\n" + report_text)


if __name__ == "__main__":
    asyncio.run(main())
