#!/usr/bin/env python3
"""VLM模型就绪检测 + 自动测试启动器

等待Ollama模型下载完成后自动启动测试。
使用方式: python tests/vlm_auto_test.py
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("vlm_auto_test")

OLLAMA_BASE_URL = "http://localhost:11434"
REQUIRED_MODELS = ["qwen3-vl:8b", "openbmb/minicpm-o2.6"]
CHECK_INTERVAL = 60


async def check_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def get_installed_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass
    return []


async def wait_for_models():
    logger.info("等待Ollama模型下载完成...")
    logger.info(f"需要模型: {REQUIRED_MODELS}")

    while True:
        if not await check_ollama_running():
            logger.warning("Ollama未运行，请先启动: ollama serve")
            await asyncio.sleep(CHECK_INTERVAL)
            continue

        installed = await get_installed_models()
        logger.info(f"已安装模型: {installed}")

        missing = []
        for req in REQUIRED_MODELS:
            found = any(req in m for m in installed)
            if not found:
                missing.append(req)

        if not missing:
            logger.info("✓ 所有模型已就绪！")
            return True

        logger.info(f"等待模型下载: {missing}")
        await asyncio.sleep(CHECK_INTERVAL)


async def quick_test():
    logger.info("=" * 60)
    logger.info("快速验证测试")
    logger.info("=" * 60)

    test_image = Path(__file__).parent / "video" / "ai" / "ai(封面).jpg"
    if not test_image.exists():
        logger.error(f"测试图片不存在: {test_image}")
        return

    import base64

    from PIL import Image, ImageFile
    import io

    img = Image.open(test_image)
    if img.mode == "RGBA":
        img = img.convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    prompt = "请用中文简要描述这个画面中的内容。"

    for model_id in REQUIRED_MODELS:
        installed = await get_installed_models()
        found = any(model_id in m for m in installed)
        if not found:
            logger.info(f"跳过 {model_id} (未安装)")
            continue

        logger.info(f"\n测试模型: {model_id}")

        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
            "stream": False,
        }

        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                )
            latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(f"  ✓ 响应成功 ({latency:.0f}ms)")
                logger.info(f"  回答: {content[:300]}")
            else:
                logger.error(f"  ✗ 请求失败: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"  ✗ 调用失败: {e}")


async def main():
    logger.info("VibeUtopia VLM自动测试启动器")
    logger.info(f"时间: {datetime.now().isoformat()}")

    models_ready = await wait_for_models()

    if models_ready:
        logger.info("\n模型就绪，开始快速验证...")
        await quick_test()

        logger.info("\n启动完整基准测试...")
        benchmark_script = Path(__file__).parent / "vlm_video_benchmark.py"
        if benchmark_script.exists():
            result = subprocess.run(
                [sys.executable, str(benchmark_script)],
                cwd=str(Path(__file__).parent.parent),
            )
            logger.info(f"基准测试完成，退出码: {result.returncode}")
        else:
            logger.error(f"基准测试脚本不存在: {benchmark_script}")


if __name__ == "__main__":
    asyncio.run(main())
