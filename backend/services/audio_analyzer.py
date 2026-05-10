from __future__ import annotations

"""音频分析模块 - V2.R4

从视频中提取音频，进行语音转写和情感分析。
支持 faster-whisper（首选）和 openai-whisper（备选）。
情感分析使用LLM判断，可选SER模型增强。
"""

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# 检测可用转录引擎
_HAS_FASTER_WHISPER = False
_HAS_WHISPER = False
_HAS_FFMPEG = False

try:
    from faster_whisper import WhisperModel
    _HAS_FASTER_WHISPER = True
except ImportError:
    pass

try:
    import whisper
    _HAS_WHISPER = True
except ImportError:
    pass

try:
    import ffmpeg as _ffmpeg
    _HAS_FFMPEG = True
except ImportError:
    pass


@dataclass
class TranscriptSegment:
    """语音转写片段"""
    start: float            # 开始时间(秒)
    end: float              # 结束时间(秒)
    text: str               # 转写文本


@dataclass
class SentimentResult:
    """情感分析结果"""
    sentiment: str          # positive/neutral/negative/mixed
    emotion: str = ""       # 具体情绪: happy/angry/sad/fearful/surprised/disgusted/neutral
    intensity: float = 0.5  # 情感强度 0-1
    confidence: float = 0.5 # 置信度 0-1
    description: str = ""   # 情感描述


@dataclass
class AudioAnalysisResult:
    """音频分析完整结果"""
    audio_path: str = ""
    duration: float = 0.0
    language: str = ""
    segments: list = field(default_factory=list)  # List[TranscriptSegment]
    full_text: str = ""
    sentiment: Optional[SentimentResult] = None
    engine_used: str = ""
    risk_text: str = ""     # 送入文字风控的文本
    error: Optional[str] = None


# ─── 默认配置 ────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "whisper_model": "base",          # whisper模型大小: tiny/base/small/medium/large
    "whisper_device": "cpu",          # 计算设备: cpu/cuda
    "whisper_compute_type": "int8",   # 计算精度: float16/int8
    "language": None,                  # 指定语言(None=自动检测)
    "min_segment_length": 2,          # 最短片段时长(秒)
    "enable_sentiment": True,         # 是否启用情感分析
}


class AudioAnalyzer:
    """音频分析器"""

    def __init__(self, config: dict | None = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._faster_whisper_model = None
        self._whisper_model = None
        self._sentiment_prompt = self._load_sentiment_prompt()

    def _load_sentiment_prompt(self) -> str:
        """加载情感分析prompt模板"""
        prompt_path = PROMPTS_DIR / "audio_sentiment.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        return """分析以下语音转写文本中的说话者情感倾向。

请以JSON格式返回：
```json
{
  "sentiment": "positive|neutral|negative|mixed",
  "emotion": "happy|angry|sad|fearful|surprised|disgusted|neutral",
  "intensity": 0.0-1.0,
  "confidence": 0.0-1.0,
  "description": "情感描述"
}
```

转写文本：
{text}"""

    async def analyze(self, video_path: str) -> AudioAnalysisResult:
        """分析视频音频

        Args:
            video_path: 视频文件路径

        Returns:
            AudioAnalysisResult
        """
        result = AudioAnalysisResult()

        # 1. 提取音频
        audio_path = await self._extract_audio(video_path)
        if not audio_path:
            result.error = "无法提取音频（需要ffmpeg）"
            return result

        result.audio_path = audio_path

        # 2. 语音转写
        transcript = await self._transcribe(audio_path)
        if transcript.error:
            result.error = transcript.error
            return result

        result.segments = transcript.segments
        result.full_text = transcript.full_text
        result.language = transcript.language
        result.engine_used = transcript.engine_used
        result.duration = transcript.duration

        # 3. 情感分析
        if self.config["enable_sentiment"] and result.full_text:
            sentiment = await self._analyze_sentiment(result.full_text)
            result.sentiment = sentiment

        # 4. 准备送入文字风控的文本
        result.risk_text = result.full_text

        return result

    async def _extract_audio(self, video_path: str) -> Optional[str]:
        """从视频提取音频为WAV"""
        if not os.path.exists(video_path):
            return None

        if not _HAS_FFMPEG:
            # 尝试使用OpenCV判断是否有音轨
            logger.warning("ffmpeg未安装，无法提取音频")
            return None

        try:
            tmp_dir = tempfile.mkdtemp(prefix="vibe_audio_")
            audio_path = os.path.join(tmp_dir, "audio.wav")

            import ffmpeg
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: (
                    ffmpeg
                    .input(video_path)
                    .output(audio_path, acodec="pcm_s16le", ac=1, ar="16k")
                    .overwrite_output()
                    .run(quiet=True)
                ),
            )

            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                return audio_path

        except Exception as e:
            logger.warning("音频提取失败: %s", e)

        return None

    async def _transcribe(self, audio_path: str) -> AudioAnalysisResult:
        """语音转写"""
        loop = asyncio.get_event_loop()
        result = AudioAnalysisResult(audio_path=audio_path)

        # 优先faster-whisper
        if _HAS_FASTER_WHISPER:
            try:
                model = self._get_faster_whisper_model()
                if model:
                    segments_iter, info = await loop.run_in_executor(
                        None,
                        lambda: model.transcribe(
                            audio_path,
                            language=self.config["language"],
                            vad_filter=True,
                        ),
                    )

                    segments = []
                    texts = []
                    for seg in segments_iter:
                        if seg.end - seg.start >= self.config["min_segment_length"]:
                            segments.append(TranscriptSegment(
                                start=round(seg.start, 2),
                                end=round(seg.end, 2),
                                text=seg.text.strip(),
                            ))
                            texts.append(seg.text.strip())

                    result.segments = segments
                    result.full_text = " ".join(texts)
                    result.language = info.language
                    result.duration = info.duration
                    result.engine_used = "faster-whisper"
                    return result

            except Exception as e:
                logger.warning("faster-whisper转写失败: %s", e)

        # 降级openai-whisper
        if _HAS_WHISPER:
            try:
                model = self._get_whisper_model()
                if model:
                    transcribe_result = await loop.run_in_executor(
                        None,
                        lambda: model.transcribe(
                            audio_path,
                            language=self.config["language"],
                        ),
                    )

                    segments = []
                    texts = []
                    for seg in transcribe_result.get("segments", []):
                        if seg["end"] - seg["start"] >= self.config["min_segment_length"]:
                            segments.append(TranscriptSegment(
                                start=round(seg["start"], 2),
                                end=round(seg["end"], 2),
                                text=seg["text"].strip(),
                            ))
                            texts.append(seg["text"].strip())

                    result.segments = segments
                    result.full_text = " ".join(texts)
                    result.language = transcribe_result.get("language", "")
                    result.duration = segments[-1].end if segments else 0.0
                    result.engine_used = "openai-whisper"
                    return result

            except Exception as e:
                logger.warning("openai-whisper转写失败: %s", e)

        result.error = "无可用语音转写引擎（需要faster-whisper或openai-whisper）"
        return result

    def _get_faster_whisper_model(self):
        """懒加载faster-whisper模型"""
        if self._faster_whisper_model is None and _HAS_FASTER_WHISPER:
            try:
                self._faster_whisper_model = WhisperModel(
                    self.config["whisper_model"],
                    device=self.config["whisper_device"],
                    compute_type=self.config["whisper_compute_type"],
                )
            except Exception as e:
                logger.error("faster-whisper模型加载失败: %s", e)
        return self._faster_whisper_model

    def _get_whisper_model(self):
        """懒加载openai-whisper模型"""
        if self._whisper_model is None and _HAS_WHISPER:
            try:
                self._whisper_model = whisper.load_model(self.config["whisper_model"])
            except Exception as e:
                logger.error("openai-whisper模型加载失败: %s", e)
        return self._whisper_model

    async def _analyze_sentiment(self, text: str) -> SentimentResult:
        """使用LLM分析情感"""
        try:
            from backend.services.llm_client import call_llm

            prompt = self._sentiment_prompt.replace("{text}", text[:2000])
            system = "你是一个专业的语音情感分析专家，请严格按照JSON格式输出分析结果。"

            response = await call_llm(prompt, system, task_type="default")

            return self._parse_sentiment(response)

        except Exception as e:
            logger.warning("LLM情感分析失败: %s", e)
            return SentimentResult(
                sentiment="neutral",
                emotion="neutral",
                intensity=0.5,
                confidence=0.3,
                description=f"情感分析降级: {e}"
            )

    def _parse_sentiment(self, response: str) -> SentimentResult:
        """解析情感分析结果"""
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        try:
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(json_str[start:end])
            else:
                data = {}
        except json.JSONDecodeError:
            logger.warning("情感分析JSON解析失败: %s", response[:200])
            data = {}

        return SentimentResult(
            sentiment=data.get("sentiment", "neutral"),
            emotion=data.get("emotion", "neutral"),
            intensity=float(data.get("intensity", 0.5)),
            confidence=float(data.get("confidence", 0.5)),
            description=data.get("description", ""),
        )


def get_audio_status() -> dict:
    """获取音频分析可用状态"""
    return {
        "faster_whisper": _HAS_FASTER_WHISPER,
        "openai_whisper": _HAS_WHISPER,
        "ffmpeg": _HAS_FFMPEG,
        "recommended": (
            "faster-whisper" if _HAS_FASTER_WHISPER else
            "openai-whisper" if _HAS_WHISPER else
            "none"
        ),
    }
