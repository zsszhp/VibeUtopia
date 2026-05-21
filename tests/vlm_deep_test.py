#!/usr/bin/env python3
"""VLM极深度细节测试 - 按风险等级分层输出

测试维度:
1. 画面逐像素级细节扫描（地图完整性、代码编辑器、敏感符号、角落文字）
2. OCR逐字精确识别（位置、字体、大小、颜色、置信度）
3. 风险评估按5级分层（safe/low/medium/high/critical）
4. 短暂画面捕捉能力（模拟几帧闪过的场景）
5. 中文语义深度理解（隐喻、双关、文化敏感点）
6. 多尺度分析（全局→区域→像素级）

使用方式: python tests/vlm_deep_test.py [model_id]
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
logger = logging.getLogger("vlm_deep_test")

VIDEO_DIR = Path(__file__).parent.parent / "tests" / "video"
REPORT_DIR = Path(__file__).parent.parent / "data" / "reports"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

DEEP_PROMPTS = {
    "pixel_scan": """你是一个视频内容安全审计专家，正在执行画面逐像素级细节扫描任务。
请以最高精度检查这个画面，不遗漏任何细节。

## 扫描任务

### A. 地图完整性检查
- 画面中是否出现任何地图（世界地图、中国地图、区域地图）？
- 如果有地图，请逐一检查以下区域是否完整显示：
  * 中国版图是否包含台湾岛？
  * 南海诸岛（九段线）是否完整？
  * 藏南地区是否正确标注？
  * 钓鱼岛是否标注？
  * 阿克赛钦是否正确？
- 地图颜色是否存在异常（如台湾用不同颜色标注）？

### B. 代码/终端界面检查
- 画面中是否出现代码编辑器、终端、IDE界面？
- 如果有，请识别：
  * 项目名称/文件夹名
  * 代码语言
  * 是否暴露了敏感信息（API Key、密码、内部URL）
  * 是否显示了开源项目名（可能泄露商业机密）

### C. 敏感符号检查
- 是否出现国旗、军旗、党旗？如有，是否完整、正确使用？
- 是否出现徽章、勋章、军衔标志？
- 是否出现宗教符号？是否可能引发宗教冲突？
- 是否出现极端组织标志或手势？

### D. 角落/边缘微元素检查
- 四个角落是否有被忽略的小文字、小图标？
- 画面边缘是否有被裁切的重要内容？
- 是否有半透明水印或叠加文字？
- 是否有极小字号的免责声明或版权信息？

### E. 快速闪过元素检查
- 画面中是否有任何元素看起来是"一闪而过"的（如弹幕、滚动文字、快速切换的画面）？
- 这些闪过元素是否包含重要信息或敏感内容？

请以JSON格式返回：
```json
{
  "map_check": {
    "has_map": false,
    "map_details": "",
    "taiwan_present": null,
    "south_china_sea": null,
    "risk_level": "safe|low|medium|high|critical",
    "risk_description": ""
  },
  "code_check": {
    "has_code_editor": false,
    "project_name": "",
    "language": "",
    "sensitive_info_exposed": false,
    "exposed_details": "",
    "risk_level": "safe|low|medium|high|critical",
    "risk_description": ""
  },
  "symbol_check": {
    "has_flags": false,
    "flag_details": "",
    "has_badges": false,
    "has_religious_symbols": false,
    "has_extreme_symbols": false,
    "risk_level": "safe|low|medium|high|critical",
    "risk_description": ""
  },
  "corner_check": {
    "top_left": "",
    "top_right": "",
    "bottom_left": "",
    "bottom_right": "",
    "watermarks": [],
    "hidden_text": [],
    "risk_level": "safe|low|medium|high|critical",
    "risk_description": ""
  },
  "flash_check": {
    "has_flashing_elements": false,
    "flash_details": "",
    "risk_level": "safe|low|medium|high|critical",
    "risk_description": ""
  },
  "overall_risk_level": "safe|low|medium|high|critical",
  "overall_summary": ""
}
```""",

    "ocr_deep": """你是一个顶级OCR专家，请对这个画面执行逐字精确识别。

## 识别要求

### 第一层：主标题识别
- 画面中最大的文字是什么？精确到每个字
- 字体类型（宋体/黑体/楷体/艺术字体/手写体）
- 字体颜色（精确描述，如"金色渐变"而非"黄色"）
- 是否有描边、阴影、发光效果

### 第二层：副标题/正文识别
- 所有中等大小的文字
- 按从上到下、从左到右顺序
- 标注每行文字的精确位置（如"画面中上部偏左"）

### 第三层：小字/注释识别
- 所有小字号的文字
- 特别关注：免责声明、版权信息、来源标注
- 水印文字

### 第四层：英文/数字识别
- 所有英文文字和数字
- 包括URL、邮箱、电话号码
- 产品型号、版本号

### 第五层：特殊文字识别
- 繁体字
- 竖排文字
- 艺术变形文字
- 手写文字
- 印章文字

请以JSON格式返回：
```json
{
  "main_titles": [
    {"content": "文字", "font": "字体", "color": "颜色", "effect": "效果", "position": "位置", "size_ratio": "占画面比例"}
  ],
  "subtitles": [
    {"content": "文字", "font": "字体", "color": "颜色", "position": "位置"}
  ],
  "small_text": [
    {"content": "文字", "type": "disclaimer|copyright|source|other", "position": "位置", "legibility": "清晰|模糊|部分遮挡"}
  ],
  "english_text": [
    {"content": "文字", "type": "url|email|phone|version|other", "position": "位置"}
  ],
  "special_text": [
    {"content": "文字", "type": "traditional|vertical|artistic|handwritten|seal", "position": "位置", "confidence": 0.0-1.0}
  ],
  "full_text_ordered": "按阅读顺序排列的完整文字",
  "text_density": "高|中|低",
  "ocr_confidence": 0.0-1.0,
  "unreadable_areas": ["无法识别的区域描述"]
}
```""",

    "risk_safe": """你是一个视频内容安全审计专家。请分析这个画面，仅关注 safe 级别的判断。

## safe 级别定义
画面内容完全合规，无任何风险点。具体标准：
- 无政治敏感内容
- 无暴力/血腥/恐怖元素
- 无色情/不当着装
- 无争议符号/标志
- 无不实信息
- 无侵权内容
- 无违法/违规内容

## 判断任务
1. 这个画面是否完全符合 safe 标准？
2. 如果是 safe，请说明理由
3. 如果不是 safe，请指出哪个维度不满足，以及可能属于哪个更高级别

请以JSON格式返回：
```json
{
  "is_safe": true/false,
  "safe_reasons": ["理由1", "理由2"],
  "unsafe_dimensions": [
    {"dimension": "维度名", "detail": "具体描述", "suggested_level": "low|medium|high|critical"}
  ],
  "confidence": 0.0-1.0,
  "note": "补充说明"
}
```""",

    "risk_low": """你是一个视频内容安全审计专家。请分析这个画面，仅关注 low 级别的风险。

## low 级别定义
存在轻微风险，但不影响正常发布。具体包括：
- 轻微的不实信息倾向（如夸张标题但内容基本属实）
- 边缘敏感话题但未越线（如历史讨论但未歪曲事实）
- 轻微的着装不当（如低胸但未暴露）
- 轻微的争议性表述（如调侃但未侮辱）
- 可能引发少量投诉但不违规的内容

## 判断任务
1. 画面中是否存在 low 级别风险？
2. 如果存在，请逐一列出每个 low 级别风险点
3. 每个风险点给出修改建议

请以JSON格式返回：
```json
{
  "has_low_risk": true/false,
  "low_risks": [
    {
      "dimension": "风险维度",
      "description": "风险描述",
      "evidence": "画面中的具体证据",
      "reasoning": "判断理由",
      "suggestion": "修改建议",
      "confidence": 0.0-1.0
    }
  ],
  "overall_low_risk_count": 0,
  "note": "补充说明"
}
```""",

    "risk_medium": """你是一个视频内容安全审计专家。请分析这个画面，仅关注 medium 级别的风险。

## medium 级别定义
存在中等风险，需要审核后决定是否发布。具体包括：
- 政治敏感人物/事件的出现（未违规但需注意）
- 中等程度的暴力/血腥画面（如受伤但非极端血腥）
- 历史争议话题（如对抗美援朝的不同解读）
- 可能引发较大争议的表述
- 涉及军事/国防的敏感内容
- 地图/领土标注问题
- 中等程度的不实信息

## 判断任务
1. 画面中是否存在 medium 级别风险？
2. 如果存在，请逐一列出每个 medium 级别风险点
3. 每个风险点给出处理建议（通过/修改/拒绝）

请以JSON格式返回：
```json
{
  "has_medium_risk": true/false,
  "medium_risks": [
    {
      "dimension": "风险维度",
      "description": "风险描述",
      "evidence": "画面中的具体证据",
      "reasoning": "判断推理过程",
      "impact": "可能造成的影响",
      "handling": "pass|modify|reject",
      "modification_suggestion": "具体修改方案",
      "confidence": 0.0-1.0
    }
  ],
  "overall_medium_risk_count": 0,
  "note": "补充说明"
}
```""",

    "risk_high": """你是一个视频内容安全审计专家。请分析这个画面，仅关注 high 级别的风险。

## high 级别定义
存在较高风险，建议不发布或大幅修改。具体包括：
- 明确的政治敏感内容（如歪曲历史、侮辱国家象征）
- 明显的暴力/血腥画面（如伤口特写、大量血迹）
- 明确的不实信息（如伪造文件、虚假新闻截图）
- 明确的侵权内容（如盗用版权素材）
- 明确的违法内容（如赌博、毒品相关）
- 严重的宗教/民族冲突内容

## 判断任务
1. 画面中是否存在 high 级别风险？
2. 如果存在，请逐一列出每个 high 级别风险点
3. 每个风险点给出紧急处理建议

请以JSON格式返回：
```json
{
  "has_high_risk": true/false,
  "high_risks": [
    {
      "dimension": "风险维度",
      "description": "风险描述",
      "evidence": "画面中的具体证据",
      "legal_basis": "可能违反的法规/政策",
      "severity_reasoning": "严重性判断理由",
      "urgent_action": "紧急处理建议",
      "confidence": 0.0-1.0
    }
  ],
  "overall_high_risk_count": 0,
  "note": "补充说明"
}
```""",

    "risk_critical": """你是一个视频内容安全审计专家。请分析这个画面，仅关注 critical 级别的风险。

## critical 级别定义
存在严重风险，必须立即下架/阻止发布。具体包括：
- 危害国家安全的内容
- 极端暴力/恐怖主义内容
- 儿童色情/虐待内容
- 严重违法犯罪内容
- 严重歪曲重大历史事实
- 煽动民族仇恨/宗教冲突
- 泄露国家机密

## 判断任务
1. 画面中是否存在 critical 级别风险？
2. 如果存在，请立即标记并给出紧急处理方案
3. 即使不存在 critical 风险，也请确认已逐一排查

请以JSON格式返回：
```json
{
  "has_critical_risk": true/false,
  "critical_risks": [
    {
      "dimension": "风险维度",
      "description": "风险描述",
      "evidence": "画面中的具体证据",
      "legal_violation": "违反的具体法律条款",
      "immediate_action": "立即行动方案",
      "report_required": true/false,
      "confidence": 0.0-1.0
    }
  ],
  "checklist": {
    "national_security": "通过|未通过",
    "extreme_violence": "通过|未通过",
    "child_exploitation": "通过|未通过",
    "serious_crime": "通过|未通过",
    "history_distortion": "通过|未通过",
    "ethnic_hatred": "通过|未通过",
    "state_secrets": "通过|未通过"
  },
  "overall_critical_risk_count": 0,
  "note": "补充说明"
}
```""",

    "chinese_deep": """你是一个中文语义深度分析专家，精通中国文化、网络用语和政治敏感性。
请对这个画面中的中文内容进行深度语义分析。

## 分析维度

### A. 字面含义
- 每个文字/词语的字面意思是什么？

### B. 隐含含义
- 是否有双关语、谐音梗？
- 是否有网络流行语的特殊含义？
- 是否有反讽、讽刺、阴阳怪气？

### C. 文化敏感性
- 是否涉及中国特有的政治敏感话题？
- 是否涉及民族/宗教敏感点？
- 是否涉及历史争议？
- 是否有可能被不同群体解读为不同含义？

### D. 语境分析
- 这些文字在视频语境中的真实意图是什么？
- 目标受众会如何理解这些文字？
- 是否存在"表面无害但实际敏感"的内容？

### E. 平台合规性
- 抖音/快手：是否符合短视频平台审核标准？
- B站：是否符合B站社区规范？
- 微博：是否符合微博内容政策？
- 微信视频号：是否符合微信内容规范？

请以JSON格式返回：
```json
{
  "literal_meaning": "字面含义解读",
  "hidden_meanings": [
    {"type": "pun|irony|slang|metaphor", "content": "隐含内容", "explanation": "解释"}
  ],
  "cultural_sensitivity": [
    {"topic": "敏感话题", "level": "safe|low|medium|high|critical", "explanation": "解释"}
  ],
  "context_analysis": {
    "true_intent": "真实意图",
    "audience_perception": "受众理解",
    "surface_safe_but_sensitive": true/false,
    "detail": "说明"
  },
  "platform_compliance": {
    "douyin": {"compliant": true/false, "risk": "描述"},
    "bilibili": {"compliant": true/false, "risk": "描述"},
    "weibo": {"compliant": true/false, "risk": "描述"},
    "weixin": {"compliant": true/false, "risk": "描述"}
  },
  "overall_risk_level": "safe|low|medium|high|critical"
}
```""",

    "multi_scale": """你是一个多尺度画面分析专家。请从三个尺度分析这个画面：

## 尺度一：全局印象（0.5秒扫视）
- 一个人快速划过这个画面，0.5秒内能获取什么信息？
- 第一印象是什么？
- 最吸引注意力的元素是什么？

## 尺度二：区域分析（3秒注视）
- 将画面分为9宫格（3×3），逐区域分析每个区域的内容
- 每个区域的关键元素是什么？
- 区域之间有什么关联？

## 尺度三：像素级细节（10秒+仔细检查）
- 画面中最微小的细节是什么？
- 有没有容易被忽略但重要的元素？
- 颜色、光影、构图有什么特殊之处？

请以JSON格式返回：
```json
{
  "global_impression": {
    "0_5s_takeaway": "0.5秒获取的信息",
    "first_impression": "第一印象",
    "attention_grabber": "最吸引注意力的元素",
    "emotional_tone": "情绪基调"
  },
  "regional_analysis": {
    "top_left": {"content": "", "key_elements": []},
    "top_center": {"content": "", "key_elements": []},
    "top_right": {"content": "", "key_elements": []},
    "mid_left": {"content": "", "key_elements": []},
    "mid_center": {"content": "", "key_elements": []},
    "mid_right": {"content": "", "key_elements": []},
    "bot_left": {"content": "", "key_elements": []},
    "bot_center": {"content": "", "key_elements": []},
    "bot_right": {"content": "", "key_elements": []}
  },
  "pixel_details": {
    "tiniest_detail": "最微小细节",
    "easily_missed": ["容易被忽略的元素"],
    "color_analysis": "颜色分析",
    "lighting": "光影分析",
    "composition": "构图分析"
  },
  "risk_at_different_scales": {
    "0_5s_risk": "快速扫视可能遗漏的风险",
    "3s_risk": "3秒注视能发现的风险",
    "10s_risk": "仔细检查才能发现的风险"
  }
}
```""",
}

VIDEO_INFO = {
    "ai": {
        "name": "AI专业排名",
        "description": "AI时代专业排名视频封面，包含专业列表和标签化评价",
        "expected_risks": {
            "safe": "基本安全",
            "low": "虚构排名信息、'NPC'贬低性标签",
            "medium": "可能涉及教育公平争议",
            "high": "无",
            "critical": "无",
        },
    },
    "fight": {
        "name": "抗美援朝历史",
        "description": "抗美援朝历史分析视频封面，涉及林彪和朝鲜战争",
        "expected_risks": {
            "safe": "不完全安全",
            "low": "历史话题讨论",
            "medium": "政治敏感人物(林彪)、历史事件(抗美援朝)",
            "high": "可能歪曲历史事实",
            "critical": "无",
        },
    },
    "mhy": {
        "name": "米哈游AI模型",
        "description": "米哈游自研AI模型评测视频封面，含学术论文截图",
        "expected_risks": {
            "safe": "基本安全",
            "low": "技术评测可能存在偏见",
            "medium": "无",
            "high": "无",
            "critical": "无",
        },
    },
    "moon": {
        "name": "太空宇航员",
        "description": "太空/天文科普视频封面，宇航员带血迹",
        "expected_risks": {
            "safe": "不完全安全",
            "low": "科幻内容可能引发不适",
            "medium": "血迹/伤口画面",
            "high": "可能被判定为暴力内容",
            "critical": "无",
        },
    },
}


def encode_image(image_path: str, max_size: int = 1536) -> Optional[str]:
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
        img.save(buffer, format="JPEG", quality=92)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error("图片编码失败 %s: %s", image_path, e)
        return None


async def call_vlm(model_id: str, prompt: str, image_b64: str, timeout: int = 180) -> dict:
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
        "max_tokens": 8192,
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
        if f'"{level}"' in response or f": {level}" in response or f'": "{level}' in response:
            return level
    return "unknown"


def extract_json_from_response(response: str) -> Optional[dict]:
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
            return json.loads(json_str)
        elif "{" in response:
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return None


async def main():
    model_id = sys.argv[1] if len(sys.argv) > 1 else "qwen3-vl:8b"
    logger.info("=" * 80)
    logger.info(f"VLM极深度细节测试 - 模型: {model_id}")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info(f"测试维度: 8个深度分析 × 4个视频 = 32项测试")
    logger.info("=" * 80)

    all_results = []
    risk_summary = {"safe": [], "low": [], "medium": [], "high": [], "critical": [], "unknown": []}

    for subdir, info in VIDEO_INFO.items():
        vdir = VIDEO_DIR / subdir
        if not vdir.exists():
            continue

        for f in sorted(vdir.iterdir()):
            if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue

            logger.info(f"\n{'='*70}")
            logger.info(f"测试视频: {info['name']} ({subdir})")
            logger.info(f"描述: {info['description']}")
            logger.info(f"{'='*70}")

            image_b64 = encode_image(str(f), max_size=1536)
            if not image_b64:
                continue

            for prompt_name, prompt in DEEP_PROMPTS.items():
                test_name = f"{subdir}_{prompt_name}"
                logger.info(f"  [{prompt_name}] 深度分析中...")

                try:
                    result = await call_vlm(model_id, prompt, image_b64, timeout=180)
                    logger.info(f"  ✓ 完成: {result['latency_ms']:.0f}ms, {result['tps']:.1f} tok/s, {result['tokens']} tokens")

                    response = result["content"]
                    risk_level = extract_risk_level(response)
                    parsed_json = extract_json_from_response(response)

                    if risk_level != "unknown":
                        risk_summary[risk_level].append({
                            "video": subdir,
                            "test": prompt_name,
                            "model": model_id,
                        })

                    all_results.append({
                        "model": model_id,
                        "test_name": test_name,
                        "video_category": subdir,
                        "video_name": info["name"],
                        "prompt_type": prompt_name,
                        "success": True,
                        "latency_ms": result["latency_ms"],
                        "tokens_per_second": result["tps"],
                        "total_tokens": result["tokens"],
                        "response": response,
                        "detected_risk_level": risk_level,
                        "json_parsed": parsed_json is not None,
                    })

                except Exception as e:
                    logger.error(f"  ✗ 失败: {e}")
                    all_results.append({
                        "model": model_id,
                        "test_name": test_name,
                        "video_category": subdir,
                        "video_name": info["name"],
                        "prompt_type": prompt_name,
                        "success": False,
                        "error": str(e),
                    })

                await asyncio.sleep(2)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    safe_model_name = model_id.replace("/", "_").replace(":", "_")
    json_path = REPORT_DIR / f"vlm_deep_{safe_model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "model": model_id,
            "test_type": "deep_analysis",
            "hardware": {"gpu": "RTX 5070 Ti", "vram_gb": 12, "ram_gb": 32},
            "total_tests": len(all_results),
            "successful": sum(1 for r in all_results if r.get("success")),
            "failed": sum(1 for r in all_results if not r.get("success")),
            "risk_summary": risk_summary,
            "results": all_results,
        }, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"JSON报告已保存: {json_path}")

    lines = []
    lines.append("=" * 100)
    lines.append(f"VLM极深度细节测试报告 - {model_id}")
    lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"硬件: RTX 5070 Ti 12GB VRAM + 32GB RAM")
    lines.append(f"测试维度: 8个深度分析 × 4个视频 = 32项测试")
    lines.append("=" * 100)

    successful = [r for r in all_results if r.get("success")]
    failed = [r for r in all_results if not r.get("success")]

    lines.append(f"\n总测试: {len(all_results)}, 成功: {len(successful)}, 失败: {len(failed)}")
    if successful:
        avg_lat = sum(r["latency_ms"] for r in successful) / len(successful)
        avg_tps = sum(r.get("tokens_per_second", 0) for r in successful) / len(successful)
        avg_tokens = sum(r.get("total_tokens", 0) for r in successful) / len(successful)
        avg_resp_len = sum(len(r.get("response", "")) for r in successful) / len(successful)
        lines.append(f"平均延迟: {avg_lat:.0f}ms")
        lines.append(f"平均速度: {avg_tps:.1f} tokens/s")
        lines.append(f"平均输出token: {avg_tokens:.0f}")
        lines.append(f"平均回答长度: {avg_resp_len:.0f}字")

    lines.append(f"\n{'='*100}")
    lines.append("一、风险等级分层汇总")
    lines.append("=" * 100)

    for level in ["critical", "high", "medium", "low", "safe", "unknown"]:
        items = risk_summary.get(level, [])
        level_names = {
            "critical": "🔴 CRITICAL - 必须立即处理",
            "high": "🟠 HIGH - 建议不发布/大幅修改",
            "medium": "🟡 MEDIUM - 需审核后决定",
            "low": "🟢 LOW - 轻微风险可接受",
            "safe": "✅ SAFE - 完全合规",
            "unknown": "❓ UNKNOWN - 未能判断",
        }
        lines.append(f"\n  {level_names.get(level, level)} ({len(items)}项)")
        lines.append("  " + "-" * 80)
        if items:
            for item in items:
                vname = VIDEO_INFO.get(item["video"], {}).get("name", item["video"])
                lines.append(f"    • [{vname}] {item['test']}")
        else:
            lines.append(f"    (无)")

    lines.append(f"\n{'='*100}")
    lines.append("二、按视频分类的详细分析")
    lines.append("=" * 100)

    for subdir, info in VIDEO_INFO.items():
        vname = info["name"]
        v_results = [r for r in successful if r.get("video_category") == subdir]

        lines.append(f"\n  ┌{'─'*96}┐")
        lines.append(f"  │ 视频: {vname} ({subdir})")
        lines.append(f"  │ 描述: {info['description']}")
        lines.append(f"  └{'─'*96}┘")

        for r in v_results:
            pt = r["prompt_type"]
            lines.append(f"\n  【{pt}】")
            lines.append(f"    延迟: {r['latency_ms']:.0f}ms | 速度: {r.get('tokens_per_second', 0):.1f} tok/s | Tokens: {r.get('total_tokens', 0)}")
            lines.append(f"    检测风险等级: {r.get('detected_risk_level', 'unknown')}")
            lines.append(f"    JSON解析: {'✓ 成功' if r.get('json_parsed') else '✗ 失败'}")

            resp = r.get("response", "")
            lines.append(f"    回答({len(resp)}字):")
            for line in resp.split("\n"):
                lines.append(f"      {line}")

    lines.append(f"\n{'='*100}")
    lines.append("三、按风险等级分层的详细发现")
    lines.append("=" * 100)

    for level in ["critical", "high", "medium", "low", "safe"]:
        level_results = [r for r in successful if r.get("detected_risk_level") == level]
        if not level_results:
            continue

        level_names = {
            "critical": "🔴 CRITICAL",
            "high": "🟠 HIGH",
            "medium": "🟡 MEDIUM",
            "low": "🟢 LOW",
            "safe": "✅ SAFE",
        }
        lines.append(f"\n  {level_names.get(level, level)} 级别详细发现 ({len(level_results)}项)")
        lines.append("  " + "=" * 90)

        for r in level_results:
            vname = VIDEO_INFO.get(r.get("video_category", ""), {}).get("name", r.get("video_category", ""))
            lines.append(f"\n  [{vname}] {r['prompt_type']}")
            resp = r.get("response", "")
            for line in resp.split("\n"):
                lines.append(f"    {line}")

    lines.append(f"\n{'='*100}")
    lines.append("四、预期风险 vs 实际检测对比")
    lines.append("=" * 100)

    for subdir, info in VIDEO_INFO.items():
        vname = info["name"]
        lines.append(f"\n  [{vname}]")
        lines.append(f"    预期风险:")
        for level, desc in info["expected_risks"].items():
            lines.append(f"      {level}: {desc}")

        actual_risks = {}
        for r in successful:
            if r.get("video_category") == subdir:
                rl = r.get("detected_risk_level", "unknown")
                if rl not in actual_risks:
                    actual_risks[rl] = []
                actual_risks[rl].append(r["prompt_type"])

        lines.append(f"    实际检测:")
        for level, tests in sorted(actual_risks.items()):
            lines.append(f"      {level}: {', '.join(tests)}")

    lines.append(f"\n{'='*100}")
    lines.append("五、部署方式评估")
    lines.append("=" * 100)
    lines.append("""
  硬件: RTX 5070 Ti 12GB VRAM + 32GB RAM
  用途: 单用户本地视频内容风控分析

  ┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
  │ 部署方式     │ 速度     │ VRAM开销 │ 12GB可用 │ VLM支持  │ 推荐度   │
  ├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
  │ Ollama       │ 基准     │ ~0.5GB   │ ✅ 完美  │ ✅ 原生  │ ⭐⭐⭐⭐⭐ │
  │ llama.cpp    │ +5-6%    │ ~0.3GB   │ ✅ 可用  │ ⚠️ 手动  │ ⭐⭐⭐    │
  │ vLLM         │ 高并发+  │ ~1.5GB+  │ ❌ OOM   │ ⚠️ 有限  │ ⭐       │
  │ transformers │ -30~50%  │ ~2GB+    │ ⚠️ 勉强  │ ✅ 慢    │ ⭐⭐     │
  │ LM Studio    │ -7%      │ ~0.6GB   │ ✅ 可用  │ ⚠️ 无API │ ⭐⭐⭐    │
  └──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘

  结论: Ollama 是当前硬件配置下的最优选择
  理由:
  1. vLLM的PagedAttention在12GB VRAM下会导致OOM（需16GB+）
  2. llama.cpp仅快5-6%，但VLM模型配置复杂度高
  3. transformers推理速度慢30-50%，不适合生产使用
  4. Ollama基于llama.cpp，性能接近原生，但管理极简
  5. Ollama原生支持OpenAI兼容API，与项目架构完美集成
""")

    lines.append(f"\n{'='*100}")
    lines.append("报告结束")
    lines.append("=" * 100)

    report_text = "\n".join(lines)
    report_path = REPORT_DIR / f"vlm_deep_{safe_model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"可读报告已保存: {report_path}")

    print("\n" + report_text)


if __name__ == "__main__":
    asyncio.run(main())
