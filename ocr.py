# -*- coding: utf-8 -*-
"""
ocr.py  —  调用 Windows 10 自带 OCR 引擎读出图片里的数字与字母。
依赖 winsdk（已装）。无引擎或失败时优雅返回 None，不影响主程序。
"""
import asyncio
import os
import re
import tempfile
import threading

from PIL import Image

_AVAILABLE = None


def available():
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            from winsdk.windows.media.ocr import OcrEngine  # noqa
            _AVAILABLE = True
        except Exception:
            _AVAILABLE = False
    return _AVAILABLE


async def _ocr_async(path, lang_tag):
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage import StorageFile, FileAccessMode

    f = await StorageFile.get_file_from_path_async(path)
    stream = await f.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = None
    if lang_tag:
        try:
            engine = OcrEngine.try_create_from_language(Language(lang_tag))
        except Exception:
            engine = None
    if engine is None:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return ""

    result = await engine.recognize_async(bitmap)
    return result.text or ""


def _run_in_thread(coro_factory, timeout):
    """在独立线程（非 Tk 的 STA 单元）里跑 asyncio，带超时，避免 COM 死锁。"""
    box = {"text": ""}

    def worker():
        try:
            box["text"] = asyncio.run(coro_factory())
        except Exception:
            box["text"] = ""

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():        # 超时：放弃，让线程自生自灭，主程序继续
        return ""
    return box["text"]


def ocr_text(path, lang_tag="en", timeout=20):
    """识别图片文本；自动缩放过大图片。失败/超时返回空串，绝不卡死。"""
    if not available():
        return ""
    tmp = None
    try:
        img = Image.open(path).convert("RGB")
        if max(img.size) > 2200:
            scale = 2200 / max(img.size)
            img = img.resize((int(img.width * scale), int(img.height * scale)))
        # 存成临时文件给 WinRT 读（需绝对路径）
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(tmp)
        abspath = os.path.abspath(tmp)
        text = _run_in_thread(lambda: _ocr_async(abspath, lang_tag), timeout)
        return text
    except Exception:
        return ""
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def extract_tokens(text):
    """从识别文本中抽出数字串与字母串。
    返回 {'numbers': [...], 'letters': [...], 'raw': text}。"""
    numbers = re.findall(r"\d{2,}", text)          # 长度≥2 的数字串
    # 去重保序，并把最长的排前
    seen, nums = set(), []
    for n in sorted(numbers, key=len, reverse=True):
        if n not in seen:
            seen.add(n); nums.append(n)

    letters = re.findall(r"[A-Za-z]{1,}", text)
    letters = [w.upper() for w in letters if len(w) >= 1]
    # 单独字母也收集（用于字母界）
    single = re.findall(r"[A-Za-z]", text)
    return {
        "numbers": nums[:6],
        "letters": letters[:8],
        "single_letters": "".join(dict.fromkeys([c.upper() for c in single]))[:12],
        "raw": text.strip(),
    }
