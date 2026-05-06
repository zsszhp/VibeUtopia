import logging
import re

from backend.services.llm_client import parse_llm_json

logger = logging.getLogger(__name__)

try:
    import yt_dlp
    _HAS_YTDLP = True
except ImportError:
    _HAS_YTDLP = False


async def extract_video_text(url: str) -> dict:
    """从视频链接提取文案文本

    Returns:
        {
            "title": str,
            "description": str,
            "subtitles": str | None,
            "text": str,  # 最终可用文案(字幕>描述>标题)
            "source": str,  # "subtitles" | "description" | "title"
        }
    """
    if not _HAS_YTDLP:
        return {
            "title": "",
            "description": "",
            "subtitles": None,
            "text": "",
            "source": "",
            "error": "yt-dlp 未安装，请运行 pip install yt-dlp",
        }

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        import asyncio
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(
            None,
            lambda: _extract_info(url, ydl_opts),
        )

        if not info:
            return {"title": "", "description": "", "subtitles": None, "text": "", "source": "", "error": "无法获取视频信息"}

        title = info.get("title", "")
        description = info.get("description", "") or ""

        # 尝试提取字幕
        subtitle_text = _extract_subtitles(info)

        # 确定最终文案
        if subtitle_text:
            text = subtitle_text
            source = "subtitles"
        elif description and len(description.strip()) >= 20:
            text = description.strip()
            source = "description"
        else:
            text = title
            source = "title"

        return {
            "title": title,
            "description": description,
            "subtitles": subtitle_text,
            "text": text,
            "source": source,
        }

    except Exception as e:
        logger.error("视频信息提取失败: %s", e)
        return {"title": "", "description": "", "subtitles": None, "text": "", "source": "", "error": f"提取失败: {e}"}


def _extract_info(url: str, ydl_opts: dict) -> dict | None:
    """同步提取视频信息"""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def _extract_subtitles(info: dict) -> str | None:
    """从视频信息中提取字幕文本"""
    # 优先手动字幕
    subtitles = info.get("subtitles", {})
    if subtitles:
        return _download_subtitle(subtitles)

    # 其次自动字幕
    auto_captions = info.get("automatic_captions", {})
    if auto_captions:
        return _download_subtitle(auto_captions)

    return None


def _download_subtitle(subtitle_dict: dict) -> str | None:
    """下载并解析字幕，返回纯文本"""
    # 优先中文
    for lang in ["zh-Hans", "zh-CN", "zh", "en"]:
        if lang in subtitle_dict:
            subs = subtitle_dict[lang]
            if subs:
                # 取第一个可用格式
                sub_info = subs[0]
                sub_url = sub_info.get("url") or sub_info.get("path")
                if sub_url:
                    try:
                        import httpx
                        resp = httpx.get(sub_url, timeout=10)
                        if resp.status_code == 200:
                            text = _clean_subtitle(resp.text)
                            if text and len(text.strip()) >= 10:
                                return text
                    except Exception:
                        pass
    return None


def _clean_subtitle(raw: str) -> str:
    """清理字幕文件，提取纯文本"""
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', raw)
    # 移除时间戳行 (SRT/VTT 格式)
    text = re.sub(r'\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}', '', text)
    # 移除序号行
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    # 移除 WEBVTT 头部
    text = re.sub(r'^WEBVTT.*$', '', text, flags=re.MULTILINE)
    # 合并多余空行
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()
