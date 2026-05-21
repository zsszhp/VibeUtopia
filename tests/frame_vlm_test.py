#!/usr/bin/env python3
"""视频帧提取 + VLM全帧分析测试

从视频中提取帧，使用不同策略：
1. 封面图（之前的测试方式）
2. 1fps密集帧（项目DenseFrameScanner策略）
3. 场景切换关键帧（项目KeyframeExtractor策略）
4. 全帧提取（每帧都分析，用于对比验证）

然后用VLM对提取的帧进行深度分析，对比不同策略的检测效果。
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("frame_vlm_test")

VIDEO_DIR = Path(__file__).parent.parent / "tests" / "video"
REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"
FRAME_DIR = Path(__file__).parent.parent / "data" / "frames"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

RISK_PROMPT = """你是视频内容安全审计专家。请分析这个视频帧画面，检测以下风险：

1. 敏感图像：政治敏感人物/场景、军事设施、国家象征
2. 不当着装：暴露服装、不雅姿势
3. 争议符号：极端组织标志、歧视性手势、争议旗帜
4. 暴力内容：血腥画面、武器展示
5. 不实信息：伪造截图、虚假新闻
6. 地图问题：地图缺失台湾/南海诸岛等
7. 代码泄露：暴露项目名/API Key等
8. 其他风险

请以JSON返回：
```json
{"risk_level": "safe|low|medium|high|critical", "risks": [{"risk_type": "类型", "description": "描述", "severity": "high|medium|low", "confidence": 0.0-1.0}], "key_findings": "关键发现", "detail_level": "这个帧中能识别到的最微小的细节"}
```"""

DETAIL_PROMPT = """请用中文详细描述这个视频帧画面中的每一个可见细节，包括：
1. 所有文字内容（精确到每个字）
2. 所有物体、人物、符号
3. 画面角落和边缘的微小元素
4. 任何可能被快速跳过但包含重要信息的内容
请尽可能详细。"""


def extract_frames_opencv(video_path: str, output_dir: str, strategy: str = "1fps", max_frames: int = 0) -> list[str]:
    import cv2

    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("无法打开视频: %s", video_path)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    logger.info(f"  视频: {Path(video_path).name}, FPS={fps:.1f}, 总帧数={total_frames}, 时长={duration:.1f}s")

    extracted = []
    frame_idx = 0

    if strategy == "1fps":
        interval = max(1, int(fps))
    elif strategy == "5fps":
        interval = max(1, int(fps / 5))
    elif strategy == "scene":
        interval = max(1, int(fps * 5))
    elif strategy == "all":
        interval = 1
    else:
        interval = max(1, int(fps))

    while cap.isOpened():
        ret, img = cap.read()
        if not ret:
            break

        if frame_idx % interval == 0:
            out_path = os.path.join(output_dir, f"frame_{frame_idx:06d}.jpg")
            img_resized = cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)
            cv2.imwrite(out_path, img_resized, [cv2.IMWRITE_JPEG_QUALITY, 90])
            extracted.append(out_path)

            if max_frames > 0 and len(extracted) >= max_frames:
                break

        frame_idx += 1

    cap.release()
    logger.info(f"  提取完成: {len(extracted)}帧 (策略={strategy}, 间隔={interval}帧)")
    return extracted


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
        img.save(buffer, format="JPEG", quality=88)
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
        "temperature": 0.2,
        "max_tokens": 2048,
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


def extract_risk_level(response: str) -> str:
    for level in ["critical", "high", "medium", "low", "safe"]:
        if f'"{level}"' in response or f'": "{level}' in response:
            return level
    return "unknown"


async def analyze_frames(model_id: str, frames: list[str], video_name: str, strategy: str) -> list[dict]:
    results = []
    for i, frame_path in enumerate(frames):
        frame_name = Path(frame_path).stem
        logger.info(f"    [{i+1}/{len(frames)}] {frame_name}...")

        image_b64 = encode_image(frame_path)
        if not image_b64:
            continue

        try:
            result = await call_vlm(model_id, RISK_PROMPT, image_b64)
            risk_level = extract_risk_level(result["content"])

            results.append({
                "frame_path": frame_path,
                "frame_name": frame_name,
                "frame_index": i,
                "risk_level": risk_level,
                "latency_ms": result["latency_ms"],
                "tokens": result["tokens"],
                "response": result["content"][:500],
            })

            if risk_level not in ("safe", "unknown"):
                logger.info(f"      ⚠️ {risk_level.upper()}: {result['content'][:200]}")

                detail_result = await call_vlm(model_id, DETAIL_PROMPT, image_b64)
                results[-1]["detail_response"] = detail_result["content"][:800]
                results[-1]["detail_latency_ms"] = detail_result["latency_ms"]

                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"      ✗ 失败: {e}")
            results.append({
                "frame_path": frame_path,
                "frame_name": frame_name,
                "frame_index": i,
                "risk_level": "error",
                "error": str(e),
            })

        await asyncio.sleep(1)

    return results


async def main():
    model_id = sys.argv[1] if len(sys.argv) > 1 else "qwen3-vl:8b"
    strategy = sys.argv[2] if len(sys.argv) > 2 else "1fps"

    logger.info("=" * 80)
    logger.info(f"视频帧级VLM测试 - 模型: {model_id}, 策略: {strategy}")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info("=" * 80)

    strategies = {
        "1fps": {"interval": "1fps", "desc": "每秒1帧（项目DenseFrameScanner策略）", "max_frames": 60},
        "5fps": {"interval": "5fps", "desc": "每秒5帧（高密度扫描）", "max_frames": 100},
        "scene": {"interval": "5秒间隔", "desc": "每5秒1帧（项目KeyframeExtractor策略）", "max_frames": 30},
        "all": {"interval": "全帧", "desc": "每一帧都分析（理论最优但极慢）", "max_frames": 300},
    }

    video_dirs = {"ai": "AI专业排名", "fight": "抗美援朝历史", "mhy": "米哈游AI模型", "moon": "太空宇航员"}
    all_results = {}

    for subdir, vname in video_dirs.items():
        vdir = VIDEO_DIR / subdir
        video_file = None
        for ext in [".mp4", ".mkv", ".avi", ".mov"]:
            for f in vdir.iterdir():
                if f.suffix.lower() == ext:
                    video_file = str(f)
                    break
            if video_file:
                break

        if not video_file:
            logger.warning(f"  未找到视频文件: {subdir}")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"视频: {vname} ({subdir})")
        logger.info(f"文件: {video_file}")
        logger.info(f"策略: {strategy} - {strategies.get(strategy, {}).get('desc', strategy)}")
        logger.info(f"{'='*60}")

        frame_output_dir = str(FRAME_DIR / subdir / strategy)
        max_frames = strategies.get(strategy, {}).get("max_frames", 0)

        frames = extract_frames_opencv(video_file, frame_output_dir, strategy, max_frames)

        if not frames:
            logger.warning(f"  未提取到帧: {subdir}")
            continue

        logger.info(f"\n  开始VLM分析 ({len(frames)}帧)...")
        results = await analyze_frames(model_id, frames, vname, strategy)
        all_results[subdir] = {
            "video_name": vname,
            "strategy": strategy,
            "total_frames": len(frames),
            "analyzed_frames": len(results),
            "results": results,
        }

        risk_counts = {}
        for r in results:
            rl = r.get("risk_level", "unknown")
            risk_counts[rl] = risk_counts.get(rl, 0) + 1
        logger.info(f"  风险分布: {risk_counts}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    safe_model_name = model_id.replace("/", "_").replace(":", "_")
    json_path = REPORT_DIR / f"frame_vlm_{safe_model_name}_{strategy}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "model": model_id,
            "strategy": strategy,
            "hardware": {"gpu": "RTX 5070 Ti", "vram_gb": 12, "ram_gb": 32},
            "videos": all_results,
        }, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"JSON报告已保存: {json_path}")

    lines = []
    lines.append("=" * 100)
    lines.append(f"视频帧级VLM测试报告 - {model_id}")
    lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"硬件: RTX 5070 Ti 12GB VRAM + 32GB RAM")
    lines.append(f"帧提取策略: {strategy} - {strategies.get(strategy, {}).get('desc', strategy)}")
    lines.append("=" * 100)

    lines.append("")
    lines.append("一、帧提取策略说明")
    lines.append("-" * 100)
    lines.append("""
  当前测试使用的帧提取策略对比:

  ┌────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
  │ 策略       │ 1fps         │ 5fps         │ 场景切换     │ 全帧         │
  ├────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
  │ 帧率       │ 每秒1帧      │ 每秒5帧      │ 每5秒1帧     │ 每帧都取     │
  │ 30fps漏帧率│ 96.7%        │ 83.3%        │ 99.3%        │ 0%           │
  │ 0.5s闪帧   │ 可能漏       │ 基本不漏     │ 大概率漏     │ 不漏         │
  │ 分析耗时   │ 中等         │ 较长         │ 短           │ 极长         │
  │ 适用场景   │ 常规审核     │ 高风险内容   │ OCR初筛      │ 关键片段精审 │
  └────────────┴──────────────┴──────────────┴──────────────┴──────────────┘

  项目现有方案:
  - KeyframeExtractor: 场景切换+5秒间隔 → 最多50帧 → OCR/初筛
  - DenseFrameScanner: 1fps密集扫描 → 最多1200帧 → 异常检测
  - RegionAmplifier: 区域放大 → 小细节识别

  建议: 1fps常规扫描 + 异常帧5fps精审 + 关键区域全帧放大
""")

    for subdir, data in all_results.items():
        vname = data["video_name"]
        results = data["results"]
        total = data["total_frames"]

        lines.append(f"\n{'='*100}")
        lines.append(f"二、{vname} ({subdir}) - 帧级分析结果")
        lines.append(f"  总帧数: {total}, 分析帧数: {len(results)}, 策略: {strategy}")
        lines.append("=" * 100)

        risk_counts = {}
        for r in results:
            rl = r.get("risk_level", "unknown")
            risk_counts[rl] = risk_counts.get(rl, 0) + 1

        lines.append(f"\n  风险分布:")
        for level in ["critical", "high", "medium", "low", "safe", "unknown", "error"]:
            count = risk_counts.get(level, 0)
            if count > 0:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "safe": "✅", "unknown": "❓", "error": "❌"}.get(level, "?")
                lines.append(f"    {icon} {level.upper()}: {count}帧 ({count/len(results)*100:.1f}%)")

        risky_frames = [r for r in results if r.get("risk_level") not in ("safe", "unknown", "error")]
        if risky_frames:
            lines.append(f"\n  风险帧详情:")
            for r in risky_frames:
                lines.append(f"    [{r['frame_name']}] {r['risk_level'].upper()}")
                lines.append(f"      风险: {r.get('response', '')[:300]}")
                if r.get("detail_response"):
                    lines.append(f"      细节: {r['detail_response'][:300]}")
        else:
            lines.append(f"\n  所有帧均为SAFE级别 ✅")

        safe_frames = [r for r in results if r.get("risk_level") == "safe"]
        if safe_frames and len(safe_frames) <= 10:
            lines.append(f"\n  安全帧概览:")
            for r in safe_frames:
                lines.append(f"    [{r['frame_name']}] ✅ SAFE - {r.get('response', '')[:150]}")

    lines.append(f"\n{'='*100}")
    lines.append("三、帧提取策略对比结论")
    lines.append("=" * 100)
    lines.append("""
  关键发现:
  1. 封面图测试 ≠ 视频帧测试: 封面图只是视频的一帧，不能代表全部内容
  2. 1fps可能漏帧: 0.5秒闪过的画面在1fps下只有50%概率被捕获
  3. 5fps更安全: 0.5秒闪过的画面在5fps下有2-3帧被捕获
  4. 全帧最精确但极慢: 30fps视频每分钟1800帧，VLM分析每帧需5-30秒

  推荐策略（与项目DenseFrameScanner一致）:
  ┌─────────────────────────────────────────────────────────────┐
  │ Step 1: 1fps密集扫描 → 检测异常帧                          │
  │ Step 2: 异常帧区域放大 → 识别小细节                        │
  │ Step 3: 高风险片段5fps精审 → 不漏闪帧                      │
  │ Step 4: 关键帧全帧放大 → 像素级审核                         │
  └─────────────────────────────────────────────────────────────┘
""")

    lines.append(f"\n{'='*100}")
    lines.append("报告结束")
    lines.append("=" * 100)

    report_text = "\n".join(lines)
    report_path = REPORT_DIR / f"frame_vlm_{safe_model_name}_{strategy}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"可读报告已保存: {report_path}")

    print("\n" + report_text)


if __name__ == "__main__":
    asyncio.run(main())
