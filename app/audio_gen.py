"""
Генерация аудио для тренажёра: американский английский (Google Cloud TTS), 5 сек тишины после каждой записи.
HTML для телефона — один файл `review_*_ru.html`, разметка 1:1 как в рабочем примере (inline script в <head>).
Структура: data/audio/sentences_DD_MM_YY/audio/*.mp3 и review_*_ru.html рядом.
"""
import html
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SILENCE_SEC = 5


def audio_session_date_slug(when: date | None = None) -> str:
    """Дата сессии для имён папок и файлов: 13_03_26 (день без ведущего нуля, месяц и год — две цифры)."""
    d = when or date.today()
    return f"{d.day}_{d.month:02d}_{str(d.year)[2:]}"


# Шаблон из рабочего файла data/audio/sentences_13_03_26/review_sentences_13_03_26_ru.html (строки 1–127).
# Плейсхолдер {title_esc} — в <title> и в <h1> (одинаковый текст).
_REVIEW_RU_HEAD = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_esc}</title>

<style>

body{{
font-family:system-ui, -apple-system, Segoe UI, Arial, sans-serif;
max-width:900px;
margin:20px auto;
padding:0 20px;
line-height:1.5;
font-size:17px;
}}

h3{{
margin-bottom:5px;
color:#2c3e50;
}}

p{{
margin:8px 0;
}}

textarea{{
width:100%;
padding:10px;
border:1px solid #bdc3c7;
border-radius:4px;

font-family:inherit;
font-size:17px;
line-height:1.5;

resize:none;
overflow:hidden;
min-height:44px;

box-sizing:border-box;
margin-top:6px;
}}

button{{
padding:8px 14px;
border:none;
border-radius:4px;
cursor:pointer;

font-family:inherit;
font-size:16px;

margin-top:6px;
}}

.clear-btn{{
background:#e67e22;
color:white;
}}

.clear-btn:hover{{
background:#d35400;
}}

.show-btn{{
background:#3498db;
color:white;
}}

.show-btn:hover{{
background:#2980b9;
}}

.en-answer{{

display:none;

background:#ecf0f1;
padding:10px;
border-radius:4px;

font-family:inherit;
font-size:17px;
line-height:1.5;

margin-top:8px;
}}

.exercise{{
margin-bottom:28px;
}}

</style>


<script>

function autoResize(el){{
el.style.height="auto";
el.style.height=(el.scrollHeight)+"px";
}}

function showAnswer(btn){{
let block=btn.closest(".exercise");
block.querySelector(".en-answer").style.display="block";
btn.style.display="none";
}}

function clearInput(btn){{
let block=btn.closest(".exercise");
let input=block.querySelector("textarea");
input.value="";
autoResize(input);
}}

</script>

</head>


<body>

<h1>{title_esc}</h1>

<p><em>Напишите перевод, затем нажмите «Показать английский».</em></p>


"""


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
def generate_words_audio(words: list[dict], out_dir: Path) -> list[Path | None]:
    """Сгенерировать mp3 для каждого слова. Возвращает список той же длины, что words (None если нет english)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path | None] = []
    for i, item in enumerate(words, 1):
        en = item.get("english") or item.get("en") or ""
        if not en:
            paths.append(None)
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

def generate_sentences_audio(sentences: list[dict], out_dir: Path) -> list[Path | None]:
    """Сгенерировать mp3 для каждого предложения. Список той же длины, что sentences."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path | None] = []
    for i, item in enumerate(sentences, 1):
        en = item.get("english") or item.get("en") or ""
        if not en:
            paths.append(None)
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

def write_review_html_ru(items: list[dict], path: Path, title: str = "Предложения (русский → английский)"):
    """Тот же HTML, что в рабочем примере review_*_ru.html: только подставляются title и блоки exercise."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    en_key = "english" if items and ("english" in (items[0] or {})) else "en"
    ru_key = "translation" if items and ("translation" in (items[0] or {})) else "ru"
    title_esc = html.escape(title)
    parts = [_REVIEW_RU_HEAD.format(title_esc=title_esc)]
    for i, item in enumerate(items or [], 1):
        en = (item or {}).get(en_key) or (item or {}).get("en") or ""
        ru = (item or {}).get(ru_key) or (item or {}).get("ru") or ""
        ru_esc = html.escape(ru)
        en_esc = html.escape(en)
        parts.append(f"<!-- {i} -->")
        parts.append('<div class="exercise">')
        parts.append(f"<h3>{i}</h3>")
        parts.append(f"<p><strong>RU:</strong> {ru_esc}</p>")
        parts.append(
            '<textarea placeholder="Ваш перевод..." oninput="autoResize(this)"></textarea>'
        )
        parts.append(
            '<button class="show-btn" onclick="showAnswer(this)">Показать английский</button>'
        )
        parts.append(
            '<button class="clear-btn" onclick="clearInput(this)">Очистить</button>'
        )
        parts.append(f'<p class="en-answer"><strong></strong> {en_esc}</p>')
        parts.append("</div>")
        parts.append("")
    parts.append("\n</body>\n</html>\n")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path