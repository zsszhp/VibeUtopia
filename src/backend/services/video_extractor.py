from __future__ import annotations

"""本地视频文案提取模块

仅支持本地视频文件的文案提取。
在线视频下载功能(yt-dlp)已移除，按设计文档仅支持本地视频输入。
"""

import logging
import os

logger = logging.getLogger(__name__)


async def extract_video_text(video_path: str) -> dict:
    """从本地视频文件提取文案文本

    通过多模态管线提取：关键帧OCR + 音频转写 → 合并文案

    Args:
        video_path: 本地视频文件路径

    Returns:
        {
            "title": str,         # 文件名作为标题
            "description": str,   # 空字符串
            "subtitles": str | None,
            "text": str,          # 最终可用文案
            "source": str,        # "ocr" | "audio" | "filename"
        }
    """
    if not os.path.exists(video_path):
        return {
            "title": "",
            "description": "",
            "subtitles": None,
            "text": "",
            "source": "",
            "error": f"视频文件不存在: {video_path}（仅支持本地视频文件）",
        }

    title = os.path.splitext(os.path.basename(video_path))[0]
    combined_texts = []
    sources = []

    # 尝试通过关键帧OCR提取文字
    try:
        from backend.services.keyframe_extractor import KeyframeExtractor
        from backend.services.frame_ocr import FrameOCR

        extractor = KeyframeExtractor()
        frame_result = await extractor.extract(video_path)

        if frame_result.frames and not frame_result.error:
            ocr = FrameOCR()
            ocr_result = await ocr.extract_video_text(frame_result.frames)

            if ocr_result.all_text:
                combined_texts.append(ocr_result.all_text)
                sources.append("ocr")
                logger.info("OCR提取文字: %d字", len(ocr_result.all_text))
    except Exception as e:
        logger.warning("关键帧OCR提取失败: %s", e)

    # 尝试通过音频转写提取文字
    try:
        from backend.services.audio_analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer()
        transcription = await analyzer.analyze(video_path)

        if transcription and transcription.full_text:
            combined_texts.append(transcription.full_text)
            sources.append("audio")
            logger.info("音频转写文字: %d字", len(transcription.full_text))
    except Exception as e:
        logger.warning("音频转写失败: %s", e)

    # 合并文案
    if combined_texts:
        text = "\n".join(combined_texts)
        source = "+".join(sources)
    else:
        text = title
        source = "filename"

    return {
        "title": title,
        "description": "",
        "subtitles": None,
        "text": text,
        "source": source,
    }
