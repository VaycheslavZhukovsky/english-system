#!/usr/bin/env python3
"""
English System — приложение для изучения слов и предложений.
Данные добавляются только через import-json. Порции переключаются вручную.
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import (
    init_db,
    seed_week1,
    get_weekly_sentences,
    get_weekly_words,
    add_weekly_words,
    add_weekly_sentences,
    get_current_portion_id,
    list_portions,
    set_current_portion_id,
    create_next_portion,
    DB_PATH,
)
from app.audio_gen import generate_words_audio, generate_sentences_audio, write_review_html
from app.prep_prompt import extract_json_from_text


def _sentences_to_dict(sentences) -> dict:
    if isinstance(sentences, dict):
        return sentences
    if isinstance(sentences, list):
        return {
            (s.get("en") or s.get("english") or "").strip(): (s.get("ru") or s.get("russian") or s.get("translation") or "").strip()
            for s in sentences if isinstance(s, dict)
        }
    return {}


def _words_to_dict(words) -> dict:
    if isinstance(words, dict):
        return words
    if isinstance(words, list):
        return {
            (w.get("en") or w.get("english") or "").strip(): (w.get("ru") or w.get("russian") or w.get("translation") or "").strip()
            for w in words if isinstance(w, dict)
        }
    return {}


def cmd_import_json():
    """Добавить слова и/или предложения из JSON-файла в текущую порцию."""
    if len(sys.argv) < 3:
        print("Использование: python run.py import-json path/to/file.json")
        return
    path = Path(sys.argv[2])
    if not path.exists():
        print("Файл не найден:", path)
        return
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        print("Ошибка чтения файла:", e)
        return
    data = extract_json_from_text(raw)
    if not data and raw.strip().startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            pass
    if not data:
        print("Не удалось извлечь JSON. Ожидается объект с ключами sentences и/или words.")
        return
    init_db()
    seed_week1()
    portion_id = get_current_portion_id()
    sentences = _sentences_to_dict(data.get("sentences") or {})
    words = _words_to_dict(data.get("words") or {})
    added_s = add_weekly_sentences(portion_id, sentences) if sentences else 0
    added_w = add_weekly_words(portion_id, words) if words else 0
    print(f"Текущая порция: id={portion_id}. Добавлено предложений: {added_s}, слов: {added_w}.")


def cmd_list_portions():
    """Показать список порций (id, номер, предложений, слов)."""
    init_db()
    seed_week1()
    portions = list_portions()
    if not portions:
        print("Нет порций. Добавь данные: python run.py import-json file.json")
        return
    current = get_current_portion_id()
    print("\nПорции (текущая отмечена *):\n")
    print("  id   номер  предложений  слов")
    print("  " + "-" * 35)
    for p in portions:
        mark = " *" if p["id"] == current else ""
        print(f"  {p['id']:<4} {p['week_number']:<6} {p['sentences_count']:<12} {p['words_count']}{mark}")
    print()


def cmd_set_portion():
    """Переключиться на порцию по id: python run.py set-portion <id>"""
    if len(sys.argv) < 3:
        print("Использование: python run.py set-portion <id>")
        return
    try:
        portion_id = int(sys.argv[2])
    except ValueError:
        print("id должен быть числом.")
        return
    init_db()
    seed_week1()
    portions = {p["id"]: p for p in list_portions()}
    if portion_id not in portions:
        print("Порция с таким id не найдена. Список: python run.py list-portions")
        return
    set_current_portion_id(portion_id)
    p = portions[portion_id]
    print(f"Текущая порция: id={portion_id}, предложений: {p['sentences_count']}, слов: {p['words_count']}.")


def cmd_next_portion():
    """Создать новую порцию и переключиться на неё."""
    init_db()
    seed_week1()
    portion_id = create_next_portion()
    print(f"Создана и выбрана новая порция: id={portion_id}. Добавь данные: python run.py import-json file.json")


def cmd_generate_audio():
    """Сгенерировать аудио и HTML для телефона по текущей порции (Google Cloud TTS)."""
    init_db()
    seed_week1()
    portion_id = get_current_portion_id()
    data_dir = DB_PATH.parent
    audio_base = data_dir / "audio"
    print("1 — Слова\n2 — Предложения\n")
    try:
        choice = input("Слова или предложения? [1/2]: ").strip() or "1"
    except (UnicodeDecodeError, UnicodeEncodeError):
        choice = "1"
    if choice == "2":
        items = get_weekly_sentences(portion_id)
        out_dir = audio_base / "sentences"
        if not items:
            print("В текущей порции нет предложений.")
            return
        print("Генерация аудио (Google Cloud TTS, 5 сек тишины)...")
        paths = generate_sentences_audio(items, out_dir)
        write_review_html(items, audio_base / "review_sentences.html", "Предложения")
    else:
        items = get_weekly_words(portion_id)
        out_dir = audio_base / "words"
        if not items:
            print("В текущей порции нет слов.")
            return
        print("Генерация аудио (Google Cloud TTS, 5 сек тишины)...")
        paths = generate_words_audio(items, out_dir)
        write_review_html(items, audio_base / "review_words.html", "Слова")
    if paths:
        print(f"Готово: {len(paths)} файлов. Папка: {out_dir}")
        print("HTML для телефона:", audio_base / ("review_sentences.html" if choice == "2" else "review_words.html"))
    else:
        print("Не удалось сгенерировать аудио (Google Cloud TTS: настройте учётную запись и google-cloud-texttospeech).")


def run_app():
    from desktop_app import main as gui_main
    gui_main()


def main():
    init_db()
    seed_week1()

    if len(sys.argv) < 2:
        portion_id = get_current_portion_id()
        portions = list_portions()
        cur = next((p for p in portions if p["id"] == portion_id), None)
        print("\n" + "=" * 50)
        print("  English System")
        print("=" * 50)
        if cur:
            print(f"  Текущая порция: id={portion_id}  |  предложений: {cur['sentences_count']}  |  слов: {cur['words_count']}")
        print("\nКоманды:")
        print("  app            — открыть приложение")
        print("  import-json    — добавить данные из JSON в текущую порцию: python run.py import-json file.json")
        print("  list-portions  — список порций")
        print("  set-portion    — переключить порцию: python run.py set-portion <id>")
        print("  next-portion   — создать новую порцию и переключиться на неё")
        print("  generate-audio — сгенерировать аудио + HTML для телефона (текущая порция)")
        print()
        return

    cmd = sys.argv[1].lower()
    if cmd == "app" or cmd == "gui":
        run_app()
    elif cmd == "import-json":
        cmd_import_json()
    elif cmd == "list-portions":
        cmd_list_portions()
    elif cmd == "set-portion":
        cmd_set_portion()
    elif cmd == "next-portion":
        cmd_next_portion()
    elif cmd == "generate-audio":
        cmd_generate_audio()
    else:
        print(f"Неизвестная команда: {cmd}")


if __name__ == "__main__":
    main()
