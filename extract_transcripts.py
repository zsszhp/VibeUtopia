"""
视频文案预提取脚本 —— 使用whisper从音频文件提取文案并保存

对每个视频案例：
1. 查找同目录下的mp3音频文件
2. 使用whisper进行语音转写
3. 将文案保存到 data/video_transcripts/ 目录
"""

import json
import os
import sys

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

VIDEO_CASES = {
    "ai": {
        "audio_path": os.path.abspath("tests/video/ai/ai_音频.mp3"),
        "video_path": os.path.abspath("tests/video/ai/ai.mp4"),
    },
    "fight": {
        "audio_path": os.path.abspath("tests/video/fight/fight_音频.mp3"),
        "video_path": os.path.abspath("tests/video/fight/fight.mp4"),
    },
    "mhy": {
        "audio_path": os.path.abspath("tests/video/mhy/mhy.mp3"),
        "video_path": os.path.abspath("tests/video/mhy/mhy.mp4"),
    },
    "moon": {
        "audio_path": os.path.abspath("tests/video/moon/moon_音频.mp3"),
        "video_path": os.path.abspath("tests/video/moon/moon.mp4"),
    },
}

OUTPUT_DIR = os.path.abspath("data/video_transcripts")


def extract_with_whisper(audio_path: str) -> dict:
    """使用whisper提取音频转写"""
    result = {"text": "", "language": "", "duration": 0, "segments": [], "engine": ""}

    # 尝试 faster-whisper
    try:
        from faster_whisper import WhisperModel
        print(f"  使用 faster-whisper (base模型)...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments_iter, info = model.transcribe(audio_path, language=None, vad_filter=True)
        texts = []
        for seg in segments_iter:
            if seg.end - seg.start >= 1.0:
                result["segments"].append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
                texts.append(seg.text.strip())
        result["text"] = " ".join(texts)
        result["language"] = info.language
        result["duration"] = info.duration
        result["engine"] = "faster-whisper"
        return result
    except ImportError:
        print(f"  faster-whisper 未安装")
    except Exception as e:
        print(f"  faster-whisper 失败: {e}")

    # 尝试 openai-whisper
    try:
        import whisper
        print(f"  使用 openai-whisper (base模型)...")
        model = whisper.load_model("base")
        transcribe_result = model.transcribe(audio_path, language=None)
        texts = []
        for seg in transcribe_result.get("segments", []):
            if seg["end"] - seg["start"] >= 1.0:
                result["segments"].append({
                    "start": round(seg["start"], 2),
                    "end": round(seg["end"], 2),
                    "text": seg["text"].strip(),
                })
                texts.append(seg["text"].strip())
        result["text"] = " ".join(texts)
        result["language"] = transcribe_result.get("language", "")
        result["duration"] = transcribe_result["segments"][-1]["end"] if transcribe_result["segments"] else 0
        result["engine"] = "openai-whisper"
        return result
    except ImportError:
        print(f"  openai-whisper 未安装")
    except Exception as e:
        print(f"  openai-whisper 失败: {e}")

    return result


def main():
    print("=" * 60)
    print("视频文案预提取")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for case_name, case_info in VIDEO_CASES.items():
        audio_path = case_info["audio_path"]
        video_path = case_info["video_path"]

        output_path = os.path.join(OUTPUT_DIR, f"{case_name}.json")

        # 跳过已存在的转写
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("text"):
                print(f"\n{case_name}: 已有转写 ({len(existing['text'])}字)，跳过")
                continue

        print(f"\n--- {case_name} ---")

        # 查找音频文件
        if not os.path.exists(audio_path):
            # 尝试其他命名
            video_dir = os.path.dirname(video_path)
            found = False
            for f in os.listdir(video_dir):
                if f.lower().endswith(".mp3"):
                    audio_path = os.path.join(video_dir, f)
                    found = True
                    break
            if not found:
                print(f"  未找到音频文件，跳过")
                continue

        audio_size = os.path.getsize(audio_path) / 1024 / 1024
        print(f"  音频: {audio_path} ({audio_size:.1f}MB)")

        # 提取转写
        result = extract_with_whisper(audio_path)

        if result["text"]:
            print(f"  转写成功: {len(result['text'])}字, 语言={result['language']}, 时长={result['duration']:.0f}s")
            print(f"  预览: {result['text'][:200]}...")
        else:
            print(f"  转写失败")
            result["text"] = os.path.splitext(os.path.basename(video_path))[0]
            result["source"] = "filename"

        # 保存
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  已保存: {output_path}")

    print(f"\n所有转写完成！输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
