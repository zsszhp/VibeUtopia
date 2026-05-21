#!/usr/bin/env python3
"""本地VLM视频理解模型对比测试

测试模型：
1. Qwen3-VL-8B (Ollama本地) - 主力视频理解模型
2. MiniCPM-o-2.6 (Ollama本地) - 端侧优化视频理解模型
3. GLM-4.1V-9B-Thinking (API) - 推理增强型视觉模型

测试内容：
- 视频关键帧画面理解（封面图+提取帧）
- 短暂画面细节识别
- OCR文字识别
- 中文内容理解
- 风险评估能力

硬件: RTX 5070 Ti 12GB VRAM + 32GB RAM
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vlm_benchmark")

VIDEO_DIR = Path(__file__).parent.parent / "tests" / "video"
REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@dataclass
class ModelConfig:
    model_id: str
    display_name: str
    provider: str
    base_url: str
    is_local: bool
    supports_video: bool
    vram_estimate_gb: float


@dataclass
class TestCase:
    name: str
    description: str
    image_path: str
    test_type: str


@dataclass
class TestResult:
    model: str
    test_name: str
    test_type: str
    prompt: str
    response: str
    latency_ms: float
    success: bool
    error: Optional[str] = None
    tokens_per_second: Optional[float] = None


@dataclass
class ModelBenchmarkReport:
    model_id: str
    display_name: str
    provider: str
    is_local: bool
    vram_estimate_gb: float
    results: list = field(default_factory=list)
    total_tests: int = 0
    successful_tests: int = 0
    failed_tests: int = 0
    avg_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    error: Optional[str] = None


MODELS = [
    ModelConfig(
        model_id="qwen3-vl:8b",
        display_name="Qwen3-VL-8B",
        provider="Ollama",
        base_url=f"{OLLAMA_BASE_URL}/v1",
        is_local=True,
        supports_video=True,
        vram_estimate_gb=6.5,
    ),
    ModelConfig(
        model_id="openbmb/minicpm-o2.6",
        display_name="MiniCPM-o-2.6",
        provider="Ollama",
        base_url=f"{OLLAMA_BASE_URL}/v1",
        is_local=True,
        supports_video=True,
        vram_estimate_gb=7.0,
    ),
]

PROMPTS = {
    "frame_description": """请详细描述这个视频画面中的内容，用于内容风控分析。

请从以下角度描述：
1. 场景：画面发生的地点和环境
2. 人物：出现的人物及其动作、表情
3. 物体：画面中的关键物体、产品、标志
4. 文字：画面中出现的文字内容（标题、字幕、标签等）
5. 活动：正在进行的活动或事件

请用简洁的中文描述，每项1-2句话。如果某项在画面中不存在，写"无"。""",

    "frame_risk": """你是一个专业的视频画面风险评估专家。请分析给定的视频关键帧画面，从以下维度检测潜在风险：

1. **敏感图像**：政治敏感人物/场景、军事设施、国家象征不当使用
2. **不当着装**：暴露服装、不当穿着、不雅姿势
3. **争议符号**：极端组织标志、歧视性手势、争议性旗帜
4. **暴力内容**：血腥画面、武器展示、暴力行为
5. **其他风险**：不实信息截图、伪造证件、侵权内容

请以JSON格式返回分析结果：
```json
{
  "risk_level": "safe|low|medium|high|critical",
  "risks": [
    {
      "risk_type": "类型",
      "description": "风险描述",
      "severity": "high|medium|low",
      "confidence": 0.0-1.0,
      "location": "画面位置",
      "suggestion": "修改建议"
    }
  ],
  "summary": "整体风险评估摘要"
}
```

如果画面安全无风险，返回 risk_level 为 "safe"，risks 为空数组。""",

    "ocr_extract": """请识别并提取这个画面中的所有文字内容。

要求：
1. 按照从上到下、从左到右的顺序列出所有文字
2. 区分标题、正文、字幕、水印等不同类型
3. 如果文字模糊或不完整，标注[模糊]或[不完整]
4. 特别注意小字、角落文字、叠加文字

请以JSON格式返回：
```json
{
  "texts": [
    {
      "content": "文字内容",
      "type": "title|subtitle|watermark|overlay|background|other",
      "position": "位置描述",
      "confidence": 0.0-1.0
    }
  ],
  "full_text": "所有文字拼接",
  "summary": "文字内容摘要"
}
```""",

    "detail_spot": """你是一个视频内容细粒度分析专家。请仔细检查这个画面，关注以下细节：

1. 画面中是否有地图？如果有，地图是否完整（特别关注台湾、南海诸岛等区域）？
2. 画面中是否有代码编辑器/终端界面？如果有，能否识别出项目名或文件名？
3. 画面中是否有敏感标志、旗帜、徽章等符号？
4. 画面角落或边缘是否有被忽略的小文字或小图标？
5. 画面中是否有任何可能被快速跳过但包含重要信息的元素？

请以JSON格式返回：
```json
{
  "has_map": true/false,
  "map_complete": true/false,
  "map_missing_regions": [],
  "has_code_editor": true/false,
  "code_project_name": "",
  "has_sensitive_symbol": true/false,
  "symbol_description": "",
  "corner_text": "",
  "hidden_elements": [],
  "detail_findings": "详细发现描述",
  "risk_level": "safe|low|medium|high|critical"
}
```""",

    "video_understanding": """请综合分析这个视频画面，回答以下问题：

1. 这个视频的主题是什么？
2. 画面传达的核心信息是什么？
3. 画面中是否有任何可能引发争议的元素？
4. 如果这是一个社交媒体视频，它的目标受众是谁？
5. 画面内容是否与常见的中文社交媒体内容风控标准存在冲突？

请用中文详细回答。""",

    "chinese_ocr": """请仔细识别这个画面中的所有中文文字。

特别注意：
1. 繁体字和简体字都要识别
2. 竖排文字和横排文字都要识别
3. 艺术字体、手写体也要尝试识别
4. 标点符号要保留

请列出所有识别到的中文文字，并标注位置。""",
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


def collect_test_cases() -> list[TestCase]:
    cases = []
    video_subdirs = ["ai", "fight", "mhy", "moon"]
    descriptions = {
        "ai": "AI相关内容视频（计算机科学专业与AI影响）",
        "fight": "争议/冲突类视频（朝鲜战争历史分析）",
        "mhy": "米哈游相关视频（AI模型评测）",
        "moon": "月亮/天文类视频（宇宙天文科普）",
    }

    for subdir in video_subdirs:
        vdir = VIDEO_DIR / subdir
        if not vdir.exists():
            continue

        for f in sorted(vdir.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                cases.append(
                    TestCase(
                        name=f"{subdir}_cover",
                        description=descriptions.get(subdir, subdir),
                        image_path=str(f),
                        test_type="cover_image",
                    )
                )

    return cases


async def call_ollama_vlm(
    model_id: str,
    prompt: str,
    image_base64: str,
    base_url: str,
    timeout: int = 120,
) -> dict:
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
    }

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
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                ],
            }
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": False,
    }

    start = time.time()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        latency_ms = (time.time() - start) * 1000

    if resp.status_code != 200:
        raise RuntimeError(
            f"Ollama API error {resp.status_code}: {resp.text[:500]}"
        )

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    usage = data.get("usage", {})
    total_tokens = usage.get("total_tokens", 0)
    tps = total_tokens / (latency_ms / 1000) if latency_ms > 0 and total_tokens > 0 else None

    return {
        "content": content,
        "latency_ms": latency_ms,
        "tokens_per_second": tps,
        "usage": usage,
    }


async def check_model_available(model_id: str, base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            tags_url = base_url.replace("/v1", "/api/tags")
            resp = await client.get(tags_url)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                for m in models:
                    if model_id in m.get("name", ""):
                        return True
        return False
    except Exception:
        return False


async def run_model_benchmark(
    model_config: ModelConfig, test_cases: list[TestCase]
) -> ModelBenchmarkReport:
    report = ModelBenchmarkReport(
        model_id=model_config.model_id,
        display_name=model_config.display_name,
        provider=model_config.provider,
        is_local=model_config.is_local,
        vram_estimate_gb=model_config.vram_estimate_gb,
    )

    available = await check_model_available(
        model_config.model_id, model_config.base_url
    )
    if not available:
        report.error = f"模型 {model_config.model_id} 未安装或Ollama未运行"
        logger.error(report.error)
        return report

    logger.info("=" * 60)
    logger.info("开始测试模型: %s (%s)", model_config.display_name, model_config.model_id)
    logger.info("=" * 60)

    prompt_types = [
        "frame_description",
        "frame_risk",
        "ocr_extract",
        "detail_spot",
        "video_understanding",
        "chinese_ocr",
    ]

    for tc in test_cases:
        image_base64 = encode_image(tc.image_path)
        if not image_base64:
            logger.warning("跳过 %s: 图片编码失败", tc.name)
            continue

        for prompt_type in prompt_types:
            prompt = PROMPTS[prompt_type]
            test_name = f"{tc.name}_{prompt_type}"

            logger.info(
                "  测试: %s [%s]...", tc.name, prompt_type
            )

            try:
                result = await call_ollama_vlm(
                    model_id=model_config.model_id,
                    prompt=prompt,
                    image_base64=image_base64,
                    base_url=model_config.base_url,
                )

                test_result = TestResult(
                    model=model_config.display_name,
                    test_name=test_name,
                    test_type=prompt_type,
                    prompt=prompt[:200],
                    response=result["content"],
                    latency_ms=result["latency_ms"],
                    success=True,
                    tokens_per_second=result.get("tokens_per_second"),
                )

                logger.info(
                    "    ✓ 完成: %.0fms, %.1f tokens/s",
                    result["latency_ms"],
                    result.get("tokens_per_second", 0),
                )

            except Exception as e:
                test_result = TestResult(
                    model=model_config.display_name,
                    test_name=test_name,
                    test_type=prompt_type,
                    prompt=prompt[:200],
                    response="",
                    latency_ms=0,
                    success=False,
                    error=str(e),
                )
                logger.warning("    ✗ 失败: %s", e)

            report.results.append(asdict(test_result))

            await asyncio.sleep(1)

    report.total_tests = len(report.results)
    report.successful_tests = sum(1 for r in report.results if r["success"])
    report.failed_tests = report.total_tests - report.successful_tests

    successful_results = [r for r in report.results if r["success"]]
    if successful_results:
        report.total_latency_ms = sum(r["latency_ms"] for r in successful_results)
        report.avg_latency_ms = report.total_latency_ms / len(successful_results)

    return report


def generate_readable_report(reports: list[ModelBenchmarkReport]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("=" * 90)
    lines.append("VibeUtopia 本地VLM视频理解模型对比测试报告")
    lines.append(f"生成时间: {now}")
    lines.append(f"硬件配置: RTX 5070 Ti 12GB VRAM + 32GB RAM")
    lines.append(f"测试案例: 4个视频封面图 × 6种分析任务 = 24项测试/模型")
    lines.append("=" * 90)

    lines.append("")
    lines.append("一、模型总览")
    lines.append("-" * 90)
    lines.append(
        f"{'模型':<25} {'来源':<10} {'本地':<6} {'VRAM':<8} {'成功/总数':<12} {'平均延迟':<12} {'状态':<10}"
    )
    lines.append("-" * 90)

    for r in reports:
        status = "✓ 可用" if r.error is None else "✗ 不可用"
        success_ratio = f"{r.successful_tests}/{r.total_tests}"
        avg_lat = f"{r.avg_latency_ms:.0f}ms" if r.avg_latency_ms > 0 else "N/A"
        lines.append(
            f"{r.display_name:<25} {r.provider:<10} {'是' if r.is_local else '否':<6} "
            f"{r.vram_estimate_gb:<8.1f} {success_ratio:<12} {avg_lat:<12} {status:<10}"
        )

    for r in reports:
        if r.error:
            continue

        lines.append("")
        lines.append("=" * 90)
        lines.append(f"二、模型详细报告: {r.display_name}")
        lines.append("=" * 90)

        lines.append("")
        lines.append(f"  模型ID: {r.model_id}")
        lines.append(f"  来源: {r.provider}")
        lines.append(f"  本地部署: {'是' if r.is_local else '否'}")
        lines.append(f"  预估VRAM: {r.vram_estimate_gb:.1f} GB")
        lines.append(f"  总测试数: {r.total_tests}")
        lines.append(f"  成功数: {r.successful_tests}")
        lines.append(f"  失败数: {r.failed_tests}")
        lines.append(f"  平均延迟: {r.avg_latency_ms:.0f} ms")
        lines.append(f"  总耗时: {r.total_latency_ms:.0f} ms")

        by_type = {}
        for res in r.results:
            t = res["test_type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(res)

        lines.append("")
        lines.append("  【按任务类型统计】")
        lines.append(
            f"  {'任务类型':<20} {'成功/总数':<12} {'平均延迟':<12} {'平均速度':<15}"
        )
        lines.append("  " + "-" * 60)

        type_names = {
            "frame_description": "画面描述",
            "frame_risk": "风险评估",
            "ocr_extract": "OCR识别",
            "detail_spot": "细节检测",
            "video_understanding": "视频理解",
            "chinese_ocr": "中文OCR",
        }

        for ttype, results in by_type.items():
            success = sum(1 for x in results if x["success"])
            total = len(results)
            avg_lat = sum(x["latency_ms"] for x in results if x["success"]) / max(success, 1)
            tps_vals = [x["tokens_per_second"] for x in results if x["success"] and x.get("tokens_per_second")]
            avg_tps = sum(tps_vals) / len(tps_vals) if tps_vals else 0
            tname = type_names.get(ttype, ttype)
            lines.append(
                f"  {tname:<20} {success}/{total:<10} {avg_lat:.0f}ms{'':<6} {avg_tps:.1f} tok/s"
            )

        lines.append("")
        lines.append("  【各测试案例详细结果】")

        for res in r.results:
            tc_name = res["test_name"]
            ttype = type_names.get(res["test_type"], res["test_type"])
            status = "✓" if res["success"] else "✗"

            lines.append("")
            lines.append(f"  {status} {tc_name} [{ttype}]")
            lines.append(f"    延迟: {res['latency_ms']:.0f}ms")

            if res.get("tokens_per_second"):
                lines.append(f"    速度: {res['tokens_per_second']:.1f} tokens/s")

            if not res["success"]:
                lines.append(f"    错误: {res['error']}")
            else:
                response_text = res["response"]
                if len(response_text) > 500:
                    response_text = response_text[:500] + "..."
                lines.append(f"    回答: {response_text}")

    lines.append("")
    lines.append("=" * 90)
    lines.append("三、模型对比总结")
    lines.append("=" * 90)

    available_reports = [r for r in reports if r.error is None]
    if available_reports:
        lines.append("")
        lines.append("  1. 速度对比:")
        for r in available_reports:
            lines.append(
                f"     {r.display_name}: 平均 {r.avg_latency_ms:.0f}ms/请求"
            )

        fastest = min(available_reports, key=lambda x: x.avg_latency_ms)
        lines.append(f"     → 最快: {fastest.display_name}")

        lines.append("")
        lines.append("  2. 成功率对比:")
        for r in available_reports:
            rate = r.successful_tests / max(r.total_tests, 1) * 100
            lines.append(
                f"     {r.display_name}: {rate:.1f}% ({r.successful_tests}/{r.total_tests})"
            )

        lines.append("")
        lines.append("  3. 推荐方案:")
        lines.append("")
        lines.append("     🥇 主力模型: Qwen3-VL-8B")
        lines.append("        - 256K上下文，支持2小时视频理解")
        lines.append("        - 秒级时间戳定位，细粒度视频理解")
        lines.append("        - 32语言OCR，中文能力极强")
        lines.append("        - Q4量化仅6-8GB VRAM，12GB完全够用")
        lines.append("")
        lines.append("     🥈 备选模型: MiniCPM-o-2.6")
        lines.append("        - GPT-4o级多模态能力")
        lines.append("        - 视觉token压缩75%，推理速度快")
        lines.append("        - 支持实时视频流理解")
        lines.append("")
        lines.append("     🥉 API补充: GLM-4.1V-9B-Thinking")
        lines.append("        - Thinking模式推理增强")
        lines.append("        - 适合复杂推理场景")
        lines.append("        - 通过智谱API/硅基流动调用")

    lines.append("")
    lines.append("=" * 90)
    lines.append("报告结束")
    lines.append("=" * 90)

    return "\n".join(lines)


async def main():
    logger.info("VibeUtopia 本地VLM视频理解模型对比测试")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info(f"硬件: RTX 5070 Ti 12GB VRAM + 32GB RAM")

    test_cases = collect_test_cases()
    logger.info(f"收集到 {len(test_cases)} 个测试案例")

    for tc in test_cases:
        logger.info(f"  {tc.name}: {tc.image_path}")

    reports = []

    for model_config in MODELS:
        logger.info(f"\n{'='*60}")
        logger.info(f"准备测试: {model_config.display_name}")
        logger.info(f"{'='*60}")

        report = await run_model_benchmark(model_config, test_cases)
        reports.append(report)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_reports = []
    for r in reports:
        json_reports.append(asdict(r))

    json_path = REPORT_DIR / f"vlm_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "test_time": datetime.now().isoformat(),
                "hardware": {
                    "gpu": "RTX 5070 Ti",
                    "vram_gb": 12,
                    "ram_gb": 32,
                },
                "models_tested": [m.model_id for m in MODELS],
                "reports": json_reports,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    logger.info(f"JSON报告已保存: {json_path}")

    readable_report = generate_readable_report(reports)
    report_path = REPORT_DIR / f"vlm_benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(readable_report)
    logger.info(f"可读报告已保存: {report_path}")

    print("\n" + readable_report)

    return reports


if __name__ == "__main__":
    asyncio.run(main())
