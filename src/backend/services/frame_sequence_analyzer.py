from __future__ import annotations

"""帧序列分析模块 - V3.4 细粒度视频理解

三大核心能力：
1. 帧序列描述 — 将连续帧组合为片段，以网格图形式发送 VLM 生成叙事描述
2. 时序因果推理 — 分析跨帧事件之间的因果关系
3. 动作/变化检测 — 检测跨帧动作和变化

与 delta_frame_extractor 配合使用，接收 DeltaFrameResult 进行时序维度的深度分析。
"""

import asyncio
import base64
import io
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.services.llm_client import call_llm, call_vlm, parse_llm_json

logger = logging.getLogger(__name__)

_HAS_PIL = False
try:
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class SequenceDescription:
    """帧片段叙事描述"""
    segment_index: int
    start_time: float
    end_time: float
    frame_count: int
    description: str              # VLM 生成的叙事描述
    key_events: list              # 识别出的关键事件列表
    confidence: float


@dataclass
class CausalEvent:
    """因果事件"""
    timestamp: float
    description: str
    event_type: str               # "appearance" | "disappearance" | "change" | "action"
    confidence: float
    segment_index: int


@dataclass
class CausalLink:
    """因果链接"""
    cause: CausalEvent
    effect: CausalEvent
    relation_type: str            # "causes" | "enables" | "prevents" | "correlates"
    confidence: float


@dataclass
class CausalChain:
    """因果链"""
    events: list                  # List[CausalEvent]
    links: list                   # List[CausalLink]
    narrative: str                # LLM 生成的叙事摘要


@dataclass
class ActionEvent:
    """动作/变化事件"""
    start_time: float
    end_time: float
    action_type: str              # "motion" | "gesture" | "expression" | "scene_change" | "state_transition"
    description: str
    before_frame_path: str
    after_frame_path: str
    confidence: float
    risk_relevance: float         # 0-1 与风险评估的相关度


@dataclass
class FrameSequenceResult:
    """帧序列分析总结果"""
    sequence_descriptions: list   # List[SequenceDescription]
    causal_chain: CausalChain
    action_events: list           # List[ActionEvent]
    total_segments: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "segment_size": 6,                    # 每个片段包含的帧数
    "grid_layout": "2x3",                 # 网格布局
    "grid_frame_width": 320,              # 网格中每帧宽度
    "grid_frame_height": 180,             # 网格中每帧高度
    "enable_causal_reasoning": True,
    "enable_action_detection": True,
    "max_concurrent_vlm": 3,              # 最大并发 VLM 调用数
    "context_window": 200,                # 传递给下一段的最大上下文字符数
}


# ---------------------------------------------------------------------------
# VLM 提示词
# ---------------------------------------------------------------------------

_SEQUENCE_DESCRIPTION_PROMPT = """你是一个专业的视频内容分析专家。请仔细观察以下由 {frame_count} 帧组成的视频片段网格图。

这些帧按时间顺序从左到右、从上到下排列，时间范围从 {start_time:.1f}s 到 {end_time:.1f}s。

{context_section}

请分析这个视频片段，完成以下任务：

1. **叙事描述**：用流畅的中文描述这个片段中发生的事情，注意时间顺序和逻辑连贯性
2. **关键事件**：列出片段中出现的关键事件（如人物出现/消失、物体变化、场景切换、动作发生等）

请以JSON格式输出：
```json
{{
    "description": "对片段的叙事描述",
    "key_events": ["事件1", "事件2", "事件3"],
    "confidence": 0.0-1.0
}}
```"""

_CAUSAL_EVENT_EXTRACTION_PROMPT = """你是一个专业的视频时序分析专家。以下是视频按时间顺序划分的多个片段描述，请从中提取关键事件。

【片段描述】
{descriptions}

请提取所有关键事件，每个事件包含：
- timestamp: 事件发生的大致时间（秒）
- description: 事件描述
- event_type: 事件类型，必须是以下之一："appearance"（出现）、"disappearance"（消失）、"change"（变化）、"action"（动作）
- confidence: 置信度 0-1
- segment_index: 所属片段序号

请以JSON格式输出：
```json
{{
    "events": [
        {{
            "timestamp": 0.0,
            "description": "事件描述",
            "event_type": "appearance|disappearance|change|action",
            "confidence": 0.0-1.0,
            "segment_index": 0
        }}
    ]
}}
```"""

_CAUSAL_RELATION_PROMPT = """你是一个专业的因果推理专家。以下是视频中提取的关键事件列表，请分析事件之间的因果关系。

【事件列表】
{events}

请分析这些事件之间的因果关联，每条关联包含：
- cause_index: 原因事件在列表中的索引
- effect_index: 结果事件在列表中的索引
- relation_type: 关系类型，必须是以下之一："causes"（导致）、"enables"（使能）、"prevents"（阻止）、"correlates"（相关）
- confidence: 置信度 0-1

同时请用一段话总结整个因果链的叙事。

请以JSON格式输出：
```json
{{
    "links": [
        {{
            "cause_index": 0,
            "effect_index": 1,
            "relation_type": "causes|enables|prevents|correlates",
            "confidence": 0.0-1.0
        }}
    ],
    "narrative": "因果链叙事摘要"
}}
```"""

_ACTION_DETECTION_PROMPT = """你是一个专业的视频动作检测专家。请对比以下两帧画面，检测其中发生的动作或变化。

【前一帧】时间: {before_time:.1f}s
【后一帧】时间: {after_time:.1f}s

请分析两帧之间的动作或变化，输出JSON：
```json
{{
    "action_type": "motion|gesture|expression|scene_change|state_transition",
    "description": "动作或变化的描述",
    "confidence": 0.0-1.0,
    "risk_relevance": 0.0-1.0
}}
```

action_type 说明：
- motion: 人物或物体的运动
- gesture: 手势或肢体动作
- expression: 表情变化
- scene_change: 场景切换或背景变化
- state_transition: 物体状态转变（如出现/消失/变形）

risk_relevance: 该动作与风险评估的相关程度（0=无关，1=高度相关）

如果没有检测到明显动作或变化，返回 confidence 为 0。"""


# ---------------------------------------------------------------------------
# 核心类
# ---------------------------------------------------------------------------

class FrameSequenceAnalyzer:
    """帧序列分析器 — 提供时序维度的深度视频理解"""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._vlm_semaphore = asyncio.Semaphore(self.config["max_concurrent_vlm"])

    async def analyze(self, delta_result, context: str = "") -> FrameSequenceResult:
        """对 DeltaFrameResult 执行完整的帧序列分析

        Args:
            delta_result: DeltaFrameResult 对象，需包含 frames 属性
                          （每帧需有 file_path, timestamp, frame_type, delta_score 等属性）
            context: 额外上下文信息

        Returns:
            FrameSequenceResult
        """
        try:
            frames = getattr(delta_result, "frames", [])
            if not frames:
                return FrameSequenceResult(
                    sequence_descriptions=[],
                    causal_chain=CausalChain(events=[], links=[], narrative=""),
                    action_events=[],
                    total_segments=0,
                    error="无可用帧数据",
                )

            # 步骤1: 帧序列描述
            descriptions = await self.describe_sequences(frames, context)

            # 步骤2: 时序因果推理
            causal_chain = CausalChain(events=[], links=[], narrative="")
            if self.config["enable_causal_reasoning"] and descriptions:
                causal_chain = await self.reason_causality(descriptions)

            # 步骤3: 动作/变化检测
            action_events = []
            if self.config["enable_action_detection"] and frames:
                action_events = await self.detect_actions(frames, descriptions)

            total_segments = len(descriptions)

            logger.info(
                "帧序列分析完成: %d个片段, %d个因果事件, %d个动作事件",
                total_segments,
                len(causal_chain.events),
                len(action_events),
            )

            return FrameSequenceResult(
                sequence_descriptions=descriptions,
                causal_chain=causal_chain,
                action_events=action_events,
                total_segments=total_segments,
            )

        except Exception as e:
            logger.error("帧序列分析失败: %s", e)
            return FrameSequenceResult(
                sequence_descriptions=[],
                causal_chain=CausalChain(events=[], links=[], narrative=""),
                action_events=[],
                total_segments=0,
                error=str(e),
            )

    async def describe_sequences(
        self, frames: list, context: str = ""
    ) -> list[SequenceDescription]:
        """将帧分组为片段，生成叙事描述

        Args:
            frames: 帧列表，每帧需有 file_path 和 timestamp 属性
            context: 额外上下文

        Returns:
            List[SequenceDescription]
        """
        if not frames:
            return []

        segment_size = self.config["segment_size"]
        segments = self._group_frames_into_segments(frames, segment_size)

        if not segments:
            return []

        results: list[SequenceDescription] = []
        previous_context = context[: self.config["context_window"]] if context else ""

        async def _describe_segment(seg_idx: int, seg_frames: list) -> SequenceDescription:
            async with self._vlm_semaphore:
                return await self._describe_single_segment(
                    seg_idx, seg_frames, previous_context_from=results
                )

        # 顺序处理以传递上下文，但每个片段内部使用 semaphore 控制并发
        for seg_idx, seg_frames in enumerate(segments):
            # 传递前一段的描述作为上下文
            context_for_segment = ""
            if results:
                last_desc = results[-1]
                context_for_segment = f"【前一片段摘要】{last_desc.description}"[
                    : self.config["context_window"]
                ]
            elif previous_context:
                context_for_segment = previous_context

            desc = await self._describe_single_segment(
                seg_idx, seg_frames, context_for_segment
            )
            results.append(desc)

        return results

    async def reason_causality(
        self, descriptions: list[SequenceDescription],
    ) -> CausalChain:
        """从片段描述中提取因果链

        Args:
            descriptions: 片段叙事描述列表

        Returns:
            CausalChain
        """
        if not descriptions:
            return CausalChain(events=[], links=[], narrative="")

        # 步骤1: 提取事件
        events = await self._extract_causal_events(descriptions)
        if not events:
            return CausalChain(events=[], links=[], narrative="无关键事件")

        # 步骤2: 分析因果关系
        links, narrative = await self._analyze_causal_relations(events)

        return CausalChain(events=events, links=links, narrative=narrative)

    async def detect_actions(
        self, frames: list, descriptions: list[SequenceDescription],
    ) -> list[ActionEvent]:
        """检测跨帧动作和变化

        重点关注高 delta_score 的帧对，发送前后帧到 VLM 进行对比分析。

        Args:
            frames: 帧列表，每帧需有 file_path, timestamp, delta_score 等属性
            descriptions: 片段描述列表（用于辅助判断）

        Returns:
            List[ActionEvent]
        """
        if len(frames) < 2:
            return []

        # 筛选高变化帧对
        frame_pairs = self._select_high_delta_pairs(frames)
        if not frame_pairs:
            return []

        action_events: list[ActionEvent] = []

        async def _detect_pair(pair: tuple) -> ActionEvent | None:
            async with self._vlm_semaphore:
                return await self._detect_action_for_pair(pair)

        tasks = [_detect_pair(pair) for pair in frame_pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, ActionEvent):
                action_events.append(result)
            elif isinstance(result, Exception):
                logger.warning("动作检测失败: %s", result)

        # 按开始时间排序
        action_events.sort(key=lambda a: a.start_time)

        logger.info("动作检测完成: 发现 %d 个动作事件", len(action_events))
        return action_events

    # ------------------------------------------------------------------
    # 内部方法: 帧分组
    # ------------------------------------------------------------------

    @staticmethod
    def _group_frames_into_segments(frames: list, segment_size: int) -> list[list]:
        """将帧列表按 segment_size 分组"""
        segments = []
        for i in range(0, len(frames), segment_size):
            segment = frames[i : i + segment_size]
            if segment:
                segments.append(segment)
        return segments

    # ------------------------------------------------------------------
    # 内部方法: 单片段描述
    # ------------------------------------------------------------------

    async def _describe_single_segment(
        self,
        seg_idx: int,
        seg_frames: list,
        context_text: str,
    ) -> SequenceDescription:
        """为单个片段生成叙事描述"""
        # 获取帧属性
        start_time = self._get_frame_attr(seg_frames[0], "timestamp", 0.0)
        end_time = self._get_frame_attr(seg_frames[-1], "timestamp", 0.0)

        # 创建网格拼接图
        try:
            grid_path = await self._create_grid_montage(seg_frames)
        except Exception as e:
            logger.warning("网格图创建失败(片段%d): %s", seg_idx, e)
            return SequenceDescription(
                segment_index=seg_idx,
                start_time=start_time,
                end_time=end_time,
                frame_count=len(seg_frames),
                description=f"网格图创建失败: {e}",
                key_events=[],
                confidence=0.0,
            )

        # 编码为 base64
        image_base64 = self._encode_image_file(grid_path)
        if not image_base64:
            return SequenceDescription(
                segment_index=seg_idx,
                start_time=start_time,
                end_time=end_time,
                frame_count=len(seg_frames),
                description="图片编码失败",
                key_events=[],
                confidence=0.0,
            )

        # 构建提示词
        context_section = ""
        if context_text:
            context_section = f"【前文上下文】\n{context_text}"

        prompt = _SEQUENCE_DESCRIPTION_PROMPT.format(
            frame_count=len(seg_frames),
            start_time=start_time,
            end_time=end_time,
            context_section=context_section,
        )

        # 调用 VLM
        try:
            response = await call_vlm(
                prompt=prompt,
                image_base64=image_base64,
                system="你是一个专业的视频内容分析专家，擅长从连续帧中提取叙事和关键事件。请严格按JSON格式输出。",
                task_type="risk_assessment",
            )

            parsed = parse_llm_json(response, fallback={
                "description": "",
                "key_events": [],
                "confidence": 0.0,
            })

            description = parsed.get("description", "")
            key_events = parsed.get("key_events", [])
            confidence = float(parsed.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

        except Exception as e:
            logger.warning("VLM 调用失败(片段%d): %s", seg_idx, e)
            description = f"VLM分析失败: {e}"
            key_events = []
            confidence = 0.0

        # 清理临时网格图
        try:
            if grid_path and os.path.exists(grid_path):
                os.remove(grid_path)
        except OSError:
            pass

        return SequenceDescription(
            segment_index=seg_idx,
            start_time=start_time,
            end_time=end_time,
            frame_count=len(seg_frames),
            description=description,
            key_events=key_events,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # 内部方法: 因果推理
    # ------------------------------------------------------------------

    async def _extract_causal_events(
        self, descriptions: list[SequenceDescription],
    ) -> list[CausalEvent]:
        """从片段描述中提取因果事件"""
        desc_text = "\n".join(
            f"片段{d.segment_index} ({d.start_time:.1f}s-{d.end_time:.1f}s): {d.description}"
            for d in descriptions
        )

        prompt = _CAUSAL_EVENT_EXTRACTION_PROMPT.format(descriptions=desc_text)

        try:
            response = await call_llm(
                prompt=prompt,
                system="你是一个专业的视频时序分析专家，擅长从描述中提取关键事件。请严格按JSON格式输出。",
                task_type="risk_assessment",
            )

            parsed = parse_llm_json(response, fallback={"events": []})
            raw_events = parsed.get("events", [])

            events: list[CausalEvent] = []
            valid_types = {"appearance", "disappearance", "change", "action"}

            for raw in raw_events:
                event_type = raw.get("event_type", "change")
                if event_type not in valid_types:
                    event_type = "change"

                confidence = float(raw.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))

                events.append(CausalEvent(
                    timestamp=float(raw.get("timestamp", 0.0)),
                    description=raw.get("description", ""),
                    event_type=event_type,
                    confidence=confidence,
                    segment_index=int(raw.get("segment_index", 0)),
                ))

            return events

        except Exception as e:
            logger.warning("因果事件提取失败: %s", e)
            return []

    async def _analyze_causal_relations(
        self, events: list[CausalEvent],
    ) -> tuple[list[CausalLink], str]:
        """分析事件之间的因果关系"""
        if len(events) < 2:
            return [], "事件不足，无法建立因果链"

        events_text = "\n".join(
            f"[{i}] {e.timestamp:.1f}s ({e.event_type}): {e.description}"
            for i, e in enumerate(events)
        )

        prompt = _CAUSAL_RELATION_PROMPT.format(events=events_text)

        try:
            response = await call_llm(
                prompt=prompt,
                system="你是一个专业的因果推理专家，擅长分析事件之间的因果关联。请严格按JSON格式输出。",
                task_type="risk_assessment",
            )

            parsed = parse_llm_json(response, fallback={"links": [], "narrative": ""})
            raw_links = parsed.get("links", [])
            narrative = parsed.get("narrative", "")

            links: list[CausalLink] = []
            valid_relations = {"causes", "enables", "prevents", "correlates"}

            for raw in raw_links:
                cause_idx = int(raw.get("cause_index", -1))
                effect_idx = int(raw.get("effect_index", -1))

                if cause_idx < 0 or effect_idx < 0:
                    continue
                if cause_idx >= len(events) or effect_idx >= len(events):
                    continue
                if cause_idx == effect_idx:
                    continue

                relation_type = raw.get("relation_type", "correlates")
                if relation_type not in valid_relations:
                    relation_type = "correlates"

                confidence = float(raw.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))

                links.append(CausalLink(
                    cause=events[cause_idx],
                    effect=events[effect_idx],
                    relation_type=relation_type,
                    confidence=confidence,
                ))

            return links, narrative

        except Exception as e:
            logger.warning("因果关系分析失败: %s", e)
            return [], f"因果分析失败: {e}"

    # ------------------------------------------------------------------
    # 内部方法: 动作检测
    # ------------------------------------------------------------------

    @staticmethod
    def _select_high_delta_pairs(frames: list, top_k: int = 10) -> list[tuple]:
        """选择高 delta_score 的帧对

        Returns:
            List of (before_frame, after_frame) tuples
        """
        # 获取每帧的 delta_score
        scored_frames = []
        for f in frames:
            score = FrameSequenceAnalyzer._get_frame_attr(f, "delta_score", 0.0)
            scored_frames.append((score, f))

        # 按 delta_score 降序排序，取 top_k
        scored_frames.sort(key=lambda x: x[0], reverse=True)
        top_frames = scored_frames[: top_k]

        pairs = []
        for score, frame in top_frames:
            if score <= 0:
                continue
            # 找到该帧的前一帧
            frame_index = FrameSequenceAnalyzer._get_frame_attr(frame, "index", -1)
            if frame_index < 0:
                # 通过在列表中查找位置
                try:
                    idx = frames.index(frame)
                except ValueError:
                    continue
                if idx > 0:
                    pairs.append((frames[idx - 1], frame))
            else:
                # 通过 index 查找前一帧
                prev_frame = None
                for f in frames:
                    f_idx = FrameSequenceAnalyzer._get_frame_attr(f, "index", -1)
                    if f_idx == frame_index - 1:
                        prev_frame = f
                        break
                if prev_frame is not None:
                    pairs.append((prev_frame, frame))

        return pairs

    async def _detect_action_for_pair(
        self, pair: tuple,
    ) -> ActionEvent | None:
        """检测单对帧之间的动作"""
        before_frame, after_frame = pair

        before_path = self._get_frame_attr(before_frame, "file_path", "")
        after_path = self._get_frame_attr(after_frame, "file_path", "")

        if not before_path or not after_path:
            return None

        if not os.path.exists(before_path) or not os.path.exists(after_path):
            return None

        before_time = self._get_frame_attr(before_frame, "timestamp", 0.0)
        after_time = self._get_frame_attr(after_frame, "timestamp", 0.0)

        # 编码前后帧
        before_b64 = self._encode_image_file(before_path)
        after_b64 = self._encode_image_file(after_path)

        if not before_b64 or not after_b64:
            return None

        # 拼接前后帧为左右对比图
        comparison_b64 = self._create_comparison_image(before_b64, after_b64)

        prompt = _ACTION_DETECTION_PROMPT.format(
            before_time=before_time,
            after_time=after_time,
        )

        try:
            response = await call_vlm(
                prompt=prompt,
                image_base64=comparison_b64,
                system="你是一个专业的视频动作检测专家，擅长对比帧间差异。请严格按JSON格式输出。",
                task_type="risk_assessment",
            )

            parsed = parse_llm_json(response, fallback={
                "action_type": "motion",
                "description": "",
                "confidence": 0.0,
                "risk_relevance": 0.0,
            })

            confidence = float(parsed.get("confidence", 0.0))
            if confidence < 0.1:
                return None

            valid_action_types = {
                "motion", "gesture", "expression", "scene_change", "state_transition",
            }
            action_type = parsed.get("action_type", "motion")
            if action_type not in valid_action_types:
                action_type = "motion"

            risk_relevance = float(parsed.get("risk_relevance", 0.0))
            risk_relevance = max(0.0, min(1.0, risk_relevance))
            confidence = max(0.0, min(1.0, confidence))

            return ActionEvent(
                start_time=before_time,
                end_time=after_time,
                action_type=action_type,
                description=parsed.get("description", ""),
                before_frame_path=before_path,
                after_frame_path=after_path,
                confidence=confidence,
                risk_relevance=risk_relevance,
            )

        except Exception as e:
            logger.warning("动作检测VLM调用失败: %s", e)
            return None

    # ------------------------------------------------------------------
    # 内部方法: 图像处理
    # ------------------------------------------------------------------

    async def _create_grid_montage(self, frames: list, output_path: str = "") -> str:
        """创建帧网格拼接图

        将多个帧按 2x3 网格排列，添加时间戳标签和帧类型边框。

        Args:
            frames: 帧列表
            output_path: 输出路径（默认临时文件）

        Returns:
            拼接图文件路径
        """
        if not _HAS_PIL:
            raise RuntimeError("PIL/Pillow 未安装，无法创建网格图")

        # 解析网格布局
        layout = self.config["grid_layout"]
        rows, cols = self._parse_grid_layout(layout)

        frame_w = self.config["grid_frame_width"]
        frame_h = self.config["grid_frame_height"]

        # 计算画布大小
        canvas_w = cols * frame_w
        canvas_h = rows * frame_h

        # 创建白色画布
        canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

        for idx, frame in enumerate(frames):
            if idx >= rows * cols:
                break

            row = idx // cols
            col = idx % cols

            frame_path = self._get_frame_attr(frame, "file_path", "")
            if not frame_path or not os.path.exists(frame_path):
                # 填充灰色占位
                placeholder = Image.new("RGB", (frame_w, frame_h), (200, 200, 200))
                canvas.paste(placeholder, (col * frame_w, row * frame_h))
                continue

            # 打开并缩放帧图片
            try:
                img = Image.open(frame_path).convert("RGB")
                img = img.resize((frame_w, frame_h), Image.LANCZOS)
            except Exception as e:
                logger.warning("帧图片打开失败 %s: %s", frame_path, e)
                placeholder = Image.new("RGB", (frame_w, frame_h), (200, 200, 200))
                canvas.paste(placeholder, (col * frame_w, row * frame_h))
                continue

            # 添加时间戳标签
            timestamp = self._get_frame_attr(frame, "timestamp", 0.0)
            img = self._add_timestamp_label(img, f"{timestamp:.1f}s")

            # 添加帧类型边框
            frame_type = self._get_frame_attr(frame, "frame_type", "P")
            border_color = self._get_border_color(frame_type)
            img = self._add_border(img, border_color, width=3)

            # 粘贴到画布
            canvas.paste(img, (col * frame_w, row * frame_h))

        # 保存
        if not output_path:
            output_dir = tempfile.mkdtemp(prefix="vibe_grid_")
            output_path = os.path.join(output_dir, "grid_montage.jpg")

        canvas.save(output_path, "JPEG", quality=90)
        return output_path

    @staticmethod
    def _add_timestamp_label(img: "Image.Image", label: str) -> "Image.Image":
        """在帧图片底部添加时间戳标签（白色文字 + 半透明黑色背景）"""
        draw = ImageDraw.Draw(img, "RGBA")
        w, h = img.size

        # 尝试加载字体，失败则用默认
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except (IOError, OSError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except (IOError, OSError):
                font = ImageFont.load_default()

        # 计算文字大小
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # 绘制半透明黑色背景条
        bar_h = text_h + 6
        bar_y = h - bar_h
        draw.rectangle([(0, bar_y), (w, h)], fill=(0, 0, 0, 160))

        # 绘制白色文字
        text_x = (w - text_w) // 2
        text_y = bar_y + 3
        draw.text((text_x, text_y), label, fill=(255, 255, 255, 255), font=font)

        # 转回 RGB
        return img.convert("RGB")

    @staticmethod
    def _add_border(img: "Image.Image", color: tuple, width: int = 3) -> "Image.Image":
        """为帧图片添加彩色边框"""
        w, h = img.size
        new_w = w + 2 * width
        new_h = h + 2 * width

        bordered = Image.new("RGB", (new_w, new_h), color)
        bordered.paste(img, (width, width))
        return bordered

    @staticmethod
    def _get_border_color(frame_type: str) -> tuple:
        """根据帧类型返回边框颜色

        I-frame: 绿色, P-frame: 蓝色, 其他: 灰色
        """
        if frame_type == "I":
            return (0, 180, 0)      # 绿色 - I帧
        elif frame_type == "P":
            return (0, 120, 220)    # 蓝色 - P帧
        else:
            return (160, 160, 160)  # 灰色 - 其他

    @staticmethod
    def _parse_grid_layout(layout: str) -> tuple[int, int]:
        """解析网格布局字符串，如 '2x3' -> (2, 3)"""
        try:
            parts = layout.lower().split("x")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 2, 3

    @staticmethod
    def _create_comparison_image(before_b64: str, after_b64: str) -> str:
        """将前后帧 base64 拼接为左右对比图的 base64"""
        if not _HAS_PIL:
            # 降级：只发送后一帧
            return after_b64

        try:
            before_data = base64.b64decode(before_b64)
            after_data = base64.b64decode(after_b64)

            before_img = Image.open(io.BytesIO(before_data)).convert("RGB")
            after_img = Image.open(io.BytesIO(after_data)).convert("RGB")

            # 统一高度
            target_h = 360
            before_img = before_img.resize(
                (int(before_img.width * target_h / before_img.height), target_h),
                Image.LANCZOS,
            )
            after_img = after_img.resize(
                (int(after_img.width * target_h / after_img.height), target_h),
                Image.LANCZOS,
            )

            # 添加标签
            before_img = FrameSequenceAnalyzer._add_comparison_label(before_img, "前")
            after_img = FrameSequenceAnalyzer._add_comparison_label(after_img, "后")

            # 左右拼接
            gap = 4
            total_w = before_img.width + gap + after_img.width
            comparison = Image.new("RGB", (total_w, target_h), (128, 128, 128))
            comparison.paste(before_img, (0, 0))
            comparison.paste(after_img, (before_img.width + gap, 0))

            # 编码为 base64
            buffer = io.BytesIO()
            comparison.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        except Exception as e:
            logger.warning("对比图创建失败，降级使用后帧: %s", e)
            return after_b64

    @staticmethod
    def _add_comparison_label(img: "Image.Image", label: str) -> "Image.Image":
        """在对比图帧顶部添加标签"""
        draw = ImageDraw.Draw(img, "RGBA")
        w, h = img.size

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except (IOError, OSError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except (IOError, OSError):
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        bar_h = text_h + 6
        draw.rectangle([(0, 0), (w, bar_h)], fill=(0, 0, 0, 160))
        draw.text(((w - text_w) // 2, 3), label, fill=(255, 255, 255, 255), font=font)

        return img.convert("RGB")

    # ------------------------------------------------------------------
    # 内部方法: 工具函数
    # ------------------------------------------------------------------

    @staticmethod
    def _get_frame_attr(frame, attr: str, default):
        """安全获取帧属性，支持 dataclass 和 dict 两种形式"""
        if isinstance(frame, dict):
            return frame.get(attr, default)
        return getattr(frame, attr, default)

    @staticmethod
    def _encode_image_file(image_path: str, max_size: int = 1536) -> Optional[str]:
        """将图片文件编码为 base64，自动压缩大图"""
        if not os.path.exists(image_path):
            return None

        try:
            if _HAS_PIL:
                img = Image.open(image_path).convert("RGB")
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.LANCZOS)

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
            else:
                with open(image_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error("图片编码失败 %s: %s", image_path, e)
            return None
