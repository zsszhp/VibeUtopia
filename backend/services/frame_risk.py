from __future__ import annotations

"""画面风险评估模块 - V2.R4

使用LLM视觉模型分析视频关键帧画面内容，
检测敏感图像、不当着装、争议符号等视觉风险。
"""

import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


@dataclass
class FrameRiskItem:
    """单个画面风险项"""
    risk_type: str             # 风险类型: sensitive_image/inappropriate_dress/controversial_symbol/violence/other
    description: str           # 风险描述
    severity: str              # 严重程度: high/medium/low
    confidence: float          # 置信度 0-1
    location: str = ""         # 画面位置描述
    suggestion: str = ""       # 修改建议


@dataclass
class FrameRiskResult:
    """单帧风险评估结果"""
    frame_path: str = ""
    frame_index: int = 0
    timestamp: float = 0.0
    risks: list = field(default_factory=list)  # List[FrameRiskItem]
    risk_level: str = "safe"   # safe/low/medium/high/critical
    summary: str = ""
    error: Optional[str] = None


@dataclass
class VideoRiskResult:
    """视频全部帧风险评估结果"""
    total_frames: int = 0
    frame_results: list = field(default_factory=list)  # List[FrameRiskResult]
    overall_risk_level: str = "safe"
    high_risk_frames: int = 0
    risk_summary: str = ""
    error: Optional[str] = None


# ─── 风险等级映射 ──────────────────────────────────────────────

RISK_SCORE_MAP = {
    "critical": 100,
    "high": 75,
    "medium": 50,
    "low": 25,
    "safe": 0,
}

RISK_LEVEL_ORDER = ["safe", "low", "medium", "high", "critical"]


class FrameRiskAssessor:
    """画面风险评估器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        """加载画面风险评估prompt模板"""
        prompt_path = PROMPTS_DIR / "frame_risk.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # 内置默认模板
        return """你是一个专业的视频画面风险评估专家。请分析给定的视频关键帧画面，从以下维度检测潜在风险：

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
      "risk_type": "sensitive_image|inappropriate_dress|controversial_symbol|violence|other",
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

如果画面安全无风险，返回 risk_level 为 "safe"，risks 为空数组。"""

    async def assess_frame(self, frame_path: str, frame_index: int = 0,
                           timestamp: float = 0.0) -> FrameRiskResult:
        """评估单帧画面风险

        Args:
            frame_path: 帧图片路径
            frame_index: 帧序号
            timestamp: 时间戳

        Returns:
            FrameRiskResult
        """
        if not os.path.exists(frame_path):
            return FrameRiskResult(
                frame_path=frame_path,
                frame_index=frame_index,
                timestamp=timestamp,
                error=f"帧图片不存在: {frame_path}"
            )

        # 编码图片为base64
        image_base64 = self._encode_image(frame_path)
        if not image_base64:
            return FrameRiskResult(
                frame_path=frame_path,
                frame_index=frame_index,
                timestamp=timestamp,
                error="无法读取图片文件"
            )

        # 调用视觉模型
        try:
            response = await self._call_vision_model(image_base64)
            result = self._parse_response(response)

            return FrameRiskResult(
                frame_path=frame_path,
                frame_index=frame_index,
                timestamp=timestamp,
                risks=result.get("risks", []),
                risk_level=result.get("risk_level", "safe"),
                summary=result.get("summary", ""),
            )
        except Exception as e:
            logger.warning("LLM视觉模型不可用，使用规则降级: %s", e)
            return self._rule_based_assess(frame_path, frame_index, timestamp)

    async def assess_video_frames(self, frames: list) -> VideoRiskResult:
        """评估视频所有关键帧

        Args:
            frames: KeyFrame列表

        Returns:
            VideoRiskResult
        """
        from backend.services.keyframe_extractor import KeyFrame

        video_result = VideoRiskResult(total_frames=len(frames))
        max_risk_score = 0
        high_risk_count = 0
        summaries = []

        for frame in frames:
            if not isinstance(frame, KeyFrame):
                continue

            result = await self.assess_frame(
                frame.file_path,
                frame.index,
                frame.timestamp,
            )

            if result.error:
                continue

            video_result.frame_results.append(result)

            risk_score = RISK_SCORE_MAP.get(result.risk_level, 0)
            if risk_score > max_risk_score:
                max_risk_score = risk_score

            if result.risk_level in ("high", "critical"):
                high_risk_count += 1

            if result.summary:
                summaries.append(f"[{result.timestamp:.1f}s] {result.summary}")

        video_result.high_risk_frames = high_risk_count
        video_result.overall_risk_level = self._score_to_level(max_risk_score)
        video_result.risk_summary = "\n".join(summaries) if summaries else "未检测到画面风险"

        return video_result

    @staticmethod
    def _encode_image(frame_path: str) -> Optional[str]:
        """将图片编码为base64"""
        try:
            with open(frame_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error("图片编码失败: %s", e)
            return None

    async def _call_vision_model(self, image_base64: str) -> str:
        """调用视觉模型分析图片"""
        # 尝试使用模型路由系统的vision任务
        try:
            return await self._call_routed_vision(image_base64)
        except Exception as e:
            logger.warning("路由视觉模型调用失败，尝试降级: %s", e)

        # 降级：直接使用配置的API
        return await self._call_direct_vision(image_base64)

    async def _call_routed_vision(self, image_base64: str) -> str:
        """通过模型路由调用视觉模型"""
        from backend.services.llm_client import registry, router

        if not registry.is_loaded:
            raise RuntimeError("模型路由未加载")

        # 查找支持vision的端点
        tried = set()
        while True:
            endpoint = router.route("risk_assessment", exclude=tried)
            if endpoint is None:
                break

            key = f"{endpoint.provider}:{endpoint.model_id}"
            tried.add(key)

            try:
                result = await self._vision_api_call(
                    endpoint.base_url,
                    endpoint.api_key,
                    endpoint.model_id,
                    image_base64,
                )
                return result
            except Exception as e:
                logger.warning("视觉模型 %s 调用失败: %s", key, e)
                from backend.services.llm_client import QuotaExhaustedError
                if isinstance(e, QuotaExhaustedError):
                    router.mark_unavailable(endpoint.provider, endpoint.model_id)

        raise RuntimeError(f"所有视觉模型不可用，已尝试: {tried}")

    async def _call_direct_vision(self, image_base64: str) -> str:
        """直接调用视觉API（降级模式）— 优先使用支持视觉的模型"""
        api_key = settings.DEEPSEEK_API_KEY
        base_url = settings.DEEPSEEK_BASE_URL

        if not api_key:
            raise RuntimeError("API Key 未配置")

        vision_models = [
            (settings.QWEN_API_KEY, settings.QWEN_BASE_URL, settings.QWEN_VL_MODEL),
            (settings.GLM_API_KEY, settings.GLM_BASE_URL, getattr(settings, "GLM_VL_MODEL", "glm-4v-flash")),
        ]

        for v_api_key, v_base_url, v_model in vision_models:
            if v_api_key and v_base_url and v_model:
                try:
                    return await self._vision_api_call(v_base_url, v_api_key, v_model, image_base64)
                except Exception as e:
                    logger.warning("视觉降级模型 %s 调用失败: %s", v_model, e)
                    continue

        raise RuntimeError("无可用的视觉模型API")

    async def _vision_api_call(self, base_url: str, api_key: str,
                                model_id: str, image_base64: str) -> str:
        """调用OpenAI兼容的视觉API"""
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 判断图片格式
        image_url = f"data:image/jpeg;base64,{image_base64}"

        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的视频画面风险评估专家，请严格按照JSON格式输出分析结果。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self._prompt_template,
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                },
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }

        if _HAS_HTTPX:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT * 2) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        else:
            import urllib.request
            payload_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
            loop = asyncio.get_event_loop()
            resp_data = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT * 2),
            )
            data = json.loads(resp_data.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> dict:
        """解析LLM返回的JSON"""
        # 尝试从markdown代码块中提取JSON
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试更宽松的解析
            try:
                # 找到第一个 { 和最后一个 }
                start = json_str.find("{")
                end = json_str.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(json_str[start:end])
                else:
                    logger.warning("无法解析画面风险JSON: %s", response[:200])
                    return {"risk_level": "safe", "risks": [], "summary": "解析失败"}
            except json.JSONDecodeError:
                logger.warning("画面风险JSON解析失败: %s", response[:200])
                return {"risk_level": "safe", "risks": [], "summary": "解析失败"}

        # 验证并转换risk items
        risks = []
        for item in data.get("risks", []):
            risks.append(FrameRiskItem(
                risk_type=item.get("risk_type", "other"),
                description=item.get("description", ""),
                severity=item.get("severity", "low"),
                confidence=float(item.get("confidence", 0.5)),
                location=item.get("location", ""),
                suggestion=item.get("suggestion", ""),
            ))

        return {
            "risk_level": data.get("risk_level", "safe"),
            "risks": risks,
            "summary": data.get("summary", ""),
        }

    @staticmethod
    def _score_to_level(score: int) -> str:
        """分数转风险等级"""
        if score >= 100:
            return "critical"
        elif score >= 75:
            return "high"
        elif score >= 50:
            return "medium"
        elif score >= 25:
            return "low"
        return "safe"

    def _rule_based_assess(self, frame_path: str, frame_index: int,
                           timestamp: float) -> "FrameRiskResult":
        """规则降级评估：当LLM视觉模型不可用时，基于图片基本特征做简单判断"""
        risk_level = "safe"
        summary = "视觉模型不可用，已跳过画面风险评估（规则降级模式）"
        risks = []

        # 基于文件大小的简单启发式（大图可能内容更丰富）
        try:
            file_size = os.path.getsize(frame_path)
            if file_size > 500_000:  # >500KB
                summary = "视觉模型不可用，图片较大建议人工复查（规则降级模式）"
                risk_level = "low"
        except Exception:
            pass

        return FrameRiskResult(
            frame_path=frame_path,
            frame_index=frame_index,
            timestamp=timestamp,
            risks=risks,
            risk_level=risk_level,
            summary=summary,
        )
