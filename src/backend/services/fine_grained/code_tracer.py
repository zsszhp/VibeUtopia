from __future__ import annotations

"""代码溯源检测器 - V3.4 细粒度视频理解

检测视频中展示的代码/文件夹是否来自开源项目。
即使画面仅出现几帧、文件夹名仅占画面小区域也能检测。

方案：OCR提取代码/文件夹名 → 特征提取 → GitHub Search API搜索 → 匹配度评估
"""

import asyncio
import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeFeature:
    """代码特征"""
    feature_type: str          # project_name / file_path / code_snippet / license_info
    text: str
    confidence: float = 0.0


@dataclass
class CodeMatch:
    """代码匹配结果"""
    source: str                # github / gitlab / local
    project_name: str
    project_url: str
    license_type: str = ""
    similarity: float = 0.0
    match_type: str = ""       # exact_name / path_match / code_match
    description: str = ""


@dataclass
class CodeTraceResult:
    """代码溯源结果"""
    frame_path: str = ""
    timestamp: float = 0.0
    extracted_texts: list = field(default_factory=list)
    code_features: list = field(default_factory=list)
    matches: list = field(default_factory=list)
    is_likely_opensource: bool = False
    confidence: float = 0.0
    risk_level: str = "safe"
    description: str = ""


@dataclass
class VideoCodeTraceResult:
    """视频代码溯源总结果"""
    video_path: str = ""
    frames_with_code: int = 0
    trace_results: list = field(default_factory=list)
    has_opensource_risk: bool = False
    max_risk_level: str = "safe"
    error: Optional[str] = None


CODE_AUDIT_PROMPT = """请仔细识别这张图片中展示的代码编辑器/终端/文件夹内容。
特别注意：
1. 项目名称或文件夹名称
2. 文件路径和文件名（如 src/models/detector.py）
3. 代码片段内容
4. 是否有GitHub/GitLab等开源平台标识
5. 是否有LICENSE文件或开源协议标识
6. 编辑器主题或IDE名称

请严格以JSON格式输出：
{
    "has_code": true/false,
    "project_name": "项目名",
    "file_paths": ["文件路径1", "文件路径2"],
    "code_snippets": ["代码片段1"],
    "has_open_source_indicator": true/false,
    "platform": "GitHub/GitLab/其他/无",
    "license_info": "许可证信息",
    "ide_name": "编辑器名称",
    "confidence": 0.0-1.0
}"""

KNOWN_OPEN_SOURCE_PROJECTS = {
    "bytetrack": "https://github.com/ifzhang/ByteTrack",
    "yolov5": "https://github.com/ultralytics/yolov5",
    "yolov8": "https://github.com/ultralytics/ultralytics",
    "stable-diffusion": "https://github.com/CompVis/stable-diffusion",
    "whisper": "https://github.com/openai/whisper",
    "ffmpeg": "https://github.com/FFmpeg/FFmpeg",
    "opencv": "https://github.com/opencv/opencv",
    "pytorch": "https://github.com/pytorch/pytorch",
    "tensorflow": "https://github.com/tensorflow/tensorflow",
    "transformers": "https://github.com/huggingface/transformers",
    "langchain": "https://github.com/langchain-ai/langchain",
    "flask": "https://github.com/pallets/flask",
    "django": "https://github.com/django/django",
    "fastapi": "https://github.com/tiangolo/fastapi",
    "react": "https://github.com/facebook/react",
    "vue": "https://github.com/vuejs/vue",
    "next.js": "https://github.com/vercel/next.js",
    "paddleocr": "https://github.com/PaddlePaddle/PaddleOCR",
    "mediapipe": "https://github.com/google/mediapipe",
    "comfyui": "https://github.com/comfyanonymous/ComfyUI",
    "automatic1111": "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
    "sd-webui": "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
    "open-interpreter": "https://github.com/OpenInterpreter/open-interpreter",
    "ollama": "https://github.com/ollama/ollama",
    "llama.cpp": "https://github.com/ggerganov/llama.cpp",
    "vllm": "https://github.com/vllm-project/vllm",
    "deepspeed": "https://github.com/microsoft/DeepSpeed",
    "ray": "https://github.com/ray-project/ray",
    "mlflow": "https://github.com/mlflow/mlflow",
    "wandb": "https://github.com/wandb/wandb",
}

PROJECT_NAME_PATTERNS = [
    re.compile(r'\b([A-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)\b'),
    re.compile(r'/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)\.\w+$'),
]

FILE_PATH_PATTERN = re.compile(r'(?:^|[/\\])([\w.-]+[/\\][\w.-]+(?:\.\w+)?)')

CODE_INDICATORS = [
    'import ', 'from ', 'def ', 'class ', 'function ', 'const ',
    'return ', 'if ', 'else ', 'for ', 'while ', '#include',
    'package ', 'module ', 'export ',
]


class CodeOriginTracer:
    """代码溯源检测器——检测视频中的代码是否来自开源项目"""

    def __init__(self, config: dict | None = None, vlm_client=None):
        self.config = config or {}
        self.vlm_client = vlm_client

    async def trace_frame(self, frame_path: str, timestamp: float = 0.0) -> CodeTraceResult:
        """溯源单帧中的代码来源

        Args:
            frame_path: 帧图片路径
            timestamp: 时间戳

        Returns:
            CodeTraceResult
        """
        if not os.path.exists(frame_path):
            return CodeTraceResult(
                frame_path=frame_path,
                timestamp=timestamp,
                description=f"帧图片不存在: {frame_path}",
            )

        vlm_result = await self._vlm_analyze_code(frame_path)

        if not vlm_result or not vlm_result.get("has_code", False):
            return CodeTraceResult(
                frame_path=frame_path,
                timestamp=timestamp,
                risk_level="safe",
                description="该帧未检测到代码内容",
            )

        code_features = self._extract_code_features(vlm_result)
        matches = await self._search_opensource(code_features)

        is_likely_opensource = len(matches) > 0
        confidence = self._compute_confidence(matches, code_features)

        risk_level = "safe"
        if is_likely_opensource:
            if confidence > 0.7:
                risk_level = "high"
            elif confidence > 0.4:
                risk_level = "medium"

        return CodeTraceResult(
            frame_path=frame_path,
            timestamp=timestamp,
            extracted_texts=vlm_result.get("file_paths", []) + vlm_result.get("code_snippets", []),
            code_features=code_features,
            matches=matches,
            is_likely_opensource=is_likely_opensource,
            confidence=confidence,
            risk_level=risk_level,
            description=self._build_description(vlm_result, matches),
        )

    async def trace_video_frames(self, frame_paths: list[str], timestamps: list[float] = None) -> VideoCodeTraceResult:
        """溯源视频多帧中的代码来源"""
        if timestamps is None:
            timestamps = [0.0] * len(frame_paths)

        trace_results = []
        frames_with_code = 0
        has_opensource_risk = False
        max_risk_level = "safe"
        risk_order = {"safe": 0, "medium": 1, "high": 2, "critical": 3}

        for frame_path, timestamp in zip(frame_paths, timestamps):
            result = await self.trace_frame(frame_path, timestamp)
            trace_results.append(result)

            if result.code_features:
                frames_with_code += 1

            if result.is_likely_opensource:
                has_opensource_risk = True
                if risk_order.get(result.risk_level, 0) > risk_order.get(max_risk_level, 0):
                    max_risk_level = result.risk_level

        return VideoCodeTraceResult(
            frames_with_code=frames_with_code,
            trace_results=trace_results,
            has_opensource_risk=has_opensource_risk,
            max_risk_level=max_risk_level,
        )

    def _extract_code_features(self, vlm_result: dict) -> list[CodeFeature]:
        """从VLM分析结果中提取代码特征"""
        features = []

        project_name = vlm_result.get("project_name", "")
        if project_name:
            features.append(CodeFeature(
                feature_type="project_name",
                text=project_name,
                confidence=0.8,
            ))

        for path in vlm_result.get("file_paths", []):
            if path and len(path) > 3:
                features.append(CodeFeature(
                    feature_type="file_path",
                    text=path,
                    confidence=0.7,
                ))

        for snippet in vlm_result.get("code_snippets", []):
            if snippet and len(snippet) > 10:
                features.append(CodeFeature(
                    feature_type="code_snippet",
                    text=snippet,
                    confidence=0.6,
                ))

        license_info = vlm_result.get("license_info", "")
        if license_info:
            features.append(CodeFeature(
                feature_type="license_info",
                text=license_info,
                confidence=0.9,
            ))

        return features

    async def _search_opensource(self, code_features: list[CodeFeature]) -> list[CodeMatch]:
        """在开源代码库中搜索匹配"""
        matches = []

        for feature in code_features:
            if feature.feature_type == "project_name":
                name_matches = self._search_known_projects(feature.text)
                matches.extend(name_matches)

                api_matches = await self._search_github_api(feature.text)
                matches.extend(api_matches)

            elif feature.feature_type == "file_path":
                path_matches = self._search_by_file_path(feature.text)
                matches.extend(path_matches)

        return self._deduplicate_matches(matches)

    def _search_known_projects(self, project_name: str) -> list[CodeMatch]:
        """在已知开源项目库中搜索"""
        matches = []
        name_lower = project_name.lower().replace(" ", "-")

        for known_name, url in KNOWN_OPEN_SOURCE_PROJECTS.items():
            if known_name == name_lower or known_name in name_lower or name_lower in known_name:
                matches.append(CodeMatch(
                    source="known_database",
                    project_name=known_name,
                    project_url=url,
                    match_type="exact_name",
                    similarity=1.0 if known_name == name_lower else 0.8,
                    description=f"项目名'{project_name}'匹配已知开源项目'{known_name}'",
                ))

        return matches

    async def _search_github_api(self, query: str) -> list[CodeMatch]:
        """使用GitHub Search API搜索"""
        try:
            import aiohttp

            github_token = self.config.get("github_token", "")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            url = f"https://api.github.com/search/repositories?q={query}&per_page=5"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        matches = []
                        for item in data.get("items", [])[:3]:
                            matches.append(CodeMatch(
                                source="github",
                                project_name=item.get("full_name", ""),
                                project_url=item.get("html_url", ""),
                                license_type=item.get("license", {}).get("spdx_id", "") if item.get("license") else "",
                                match_type="github_search",
                                similarity=0.6,
                                description=f"GitHub搜索匹配: {item.get('full_name', '')} (⭐{item.get('stargazers_count', 0)})",
                            ))
                        return matches
        except Exception as e:
            logger.debug("GitHub API搜索失败: %s", e)

        return []

    def _search_by_file_path(self, file_path: str) -> list[CodeMatch]:
        """通过文件路径模式匹配开源项目"""
        matches = []

        path_lower = file_path.lower()

        path_signatures = {
            "src/models/": ["ultralytics/ultralytics", "facebookresearch/detectron2"],
            "stable_diffusion/": ["CompVis/stable-diffusion", "stability-ai/generative-models"],
            "pipelines/": ["huggingface/diffusers", "CompVis/stable-diffusion"],
            "langchain/": ["langchain-ai/langchain"],
            "transformers/": ["huggingface/transformers"],
        }

        for signature, projects in path_signatures.items():
            if signature in path_lower:
                for project in projects:
                    name_parts = project.split("/")
                    matches.append(CodeMatch(
                        source="path_signature",
                        project_name=project,
                        project_url=f"https://github.com/{project}",
                        match_type="path_match",
                        similarity=0.5,
                        description=f"文件路径'{file_path}'匹配开源项目'{project}'",
                    ))

        return matches

    @staticmethod
    def _compute_confidence(matches: list[CodeMatch], features: list[CodeFeature]) -> float:
        """计算溯源置信度"""
        if not matches:
            return 0.0

        max_similarity = max(m.similarity for m in matches)
        feature_bonus = min(len(features) * 0.1, 0.3)

        return min(max_similarity + feature_bonus, 1.0)

    @staticmethod
    def _deduplicate_matches(matches: list[CodeMatch]) -> list[CodeMatch]:
        """去重匹配结果"""
        seen = set()
        unique = []
        for m in matches:
            key = f"{m.source}:{m.project_name}"
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return sorted(unique, key=lambda x: x.similarity, reverse=True)

    @staticmethod
    def _build_description(vlm_result: dict, matches: list[CodeMatch]) -> str:
        """构建溯源描述"""
        parts = []

        project_name = vlm_result.get("project_name", "")
        if project_name:
            parts.append(f"检测到项目名: {project_name}")

        if vlm_result.get("has_open_source_indicator"):
            parts.append("检测到开源平台标识")

        if matches:
            match_names = [m.project_name for m in matches[:3]]
            parts.append(f"匹配到开源项目: {', '.join(match_names)}")
        else:
            parts.append("未匹配到已知开源项目")

        return "; ".join(parts)

    async def _vlm_analyze_code(self, frame_path: str) -> Optional[dict]:
        """使用VLM分析代码区域"""
        try:
            from backend.services.llm_client import call_vlm, parse_llm_json

            with open(frame_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")

            response = await call_vlm(
                prompt=CODE_AUDIT_PROMPT,
                image_base64=img_data,
                task_type="code_trace",
            )

            result = parse_llm_json(response)
            if result:
                return result

            return {"has_code": False}
        except Exception as e:
            logger.warning("VLM代码分析失败: %s", e)
            return None

    def get_status(self) -> dict:
        """获取检测器可用状态"""
        return {
            "available": True,
            "known_projects": len(KNOWN_OPEN_SOURCE_PROJECTS),
            "github_api": bool(self.config.get("github_token", "")),
            "vlm_required": True,
        }
