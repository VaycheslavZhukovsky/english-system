"""
Генерация аудио для тренажёра: американский английский (Google Cloud TTS), 5 сек тишины после каждой записи.
Плюс запись HTML-файла для просмотра на телефоне (EN + RU по кнопке).
"""
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SILENCE_SEC = 5

def _safe_filename(text: str, max_len: int = 40) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s\-]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:max_len].strip("_") or "audio"

def _ensure_silence_appended(mp3_path: Path) -> bool:
    """Добавить 5 сек тишины в конец mp3. Требует pydub и ffmpeg."""
    try:
        from pydub import AudioSegment
    except ImportError:
        return False
    try:
        audio = AudioSegment.from_mp3(str(mp3_path))
        silence = AudioSegment.silent(duration=SILENCE_SEC * 1000)
        combined = audio + silence
        combined.export(str(mp3_path), format="mp3")
        return True
    except Exception:
        return False

# ===== Новый блок: Google Cloud TTS =====
try:
    from google.cloud import texttospeech
    _gcloud_client = texttospeech.TextToSpeechClient()
except ImportError:
    _gcloud_client = None
    print("Установи google-cloud-texttospeech: pip install google-cloud-texttospeech")

def _generate_tts(en: str, path: Path):
    """Сгенерировать mp3 через Google Cloud TTS (американский голос)."""
    if not _gcloud_client:
        return False
    input_text = texttospeech.SynthesisInput(text=en)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-D"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = _gcloud_client.synthesize_speech(
        input=input_text,
        voice=voice,
        audio_config=audio_config
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(response.audio_content)
    _ensure_silence_appended(path)
    return True

# ===== Существующие функции генерации =====
def generate_words_audio(words: list[dict], out_dir: Path) -> list[Path]:
    """Сгенерировать mp3 для каждого слова. words: [{"english": "...", "translation": "..."}]."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, item in enumerate(words, 1):
        en = item.get("english") or item.get("en") or ""
        if not en:
            continue
        filename = f"{i:03d}_{_safe_filename(en)}.mp3"
        path = out_dir / filename
        if path.exists():
            paths.append(path)
            continue
        _generate_tts(en, path)
        paths.append(path)
        print(f"  {path.name}")
    return paths

def generate_sentences_audio(sentences: list[dict], out_dir: Path) -> list[Path]:
    """Сгенерировать mp3 для каждого предложения."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, item in enumerate(sentences, 1):
        en = item.get("english") or item.get("en") or ""
        if not en:
            continue
        filename = f"{i:03d}_{_safe_filename(en)}.mp3"
        path = out_dir / filename
        if path.exists():
            paths.append(path)
            continue
        _generate_tts(en, path)
        paths.append(path)
        print(f"  {path.name}")
    return paths

def play_audio(path: Path) -> bool:
    """Воспроизвести аудиофайл (mp3). Пробует mpv, ffplay, aplay."""
    path = Path(path)
    if not path.exists():
        return False
    for cmd in [["mpv", "--no-video", str(path)], ["ffplay", "-nodisp", "-autoexit", str(path)]]:
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return False

def write_review_html(items: list[dict], path: Path, title: str = "Повторение"):
    """Записать HTML для просмотра на телефоне: EN предложение/слово, кнопка «Показать перевод», RU."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    en_key = "english" if items and ("english" in (items[0] or {})) else "en"
    ru_key = "translation" if items and ("translation" in (items[0] or {})) else "ru"
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title></head><body>",
        f"<h1>{html.escape(title)}</h1>",
    ]
    for i, item in enumerate(items or [], 1):
        en = (item or {}).get(en_key) or (item or {}).get("en") or ""
        ru = (item or {}).get(ru_key) or (item or {}).get("ru") or ""
        en_esc = html.escape(en)
        ru_esc = html.escape(ru)
        parts.append(f"<h3>{i}</h3>")
        parts.append(f"<p><strong>EN:</strong> {en_esc}</p>")
        parts.append(
            "<button onclick=\"this.nextElementSibling.style.display='block'; this.style.display='none'\">"
            "Показать перевод</button>"
        )
        parts.append(f"<p style='display:none'><strong>RU:</strong> {ru_esc}</p>")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path