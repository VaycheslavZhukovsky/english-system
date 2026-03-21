"""
Генерация промпта для ИИ и применение ответа.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_prep_data, get_todays_question, get_stats


def build_prep_prompt() -> str:
    """Полный промпт для ИИ: инструкция + данные. Ответ — только JSON."""
    data = get_prep_data()
    question_today = get_todays_question()
    stats = get_stats()

    prompt = """Ты — ИИ-коуч английского в системе english-system. Ученик перед занятием отправил тебе данные. Твоя задача:

1. Разобрать последний ответ (daily_log): выписать ВСЕ ошибки (орфография, грамматика, словоупотребление).
2. Если сегодня вопрос-повтор — дать перевод его прошлого ответа на русский (контекст для повтора).
3. Написать одну короткую реплику daily_message: подбадривание ИЛИ замечание ИЛИ лёгкая шутка — СТРОГО из текущего состояния (его ошибки, listening %, прогресс, серия). Никаких общих фраз. Всё по делу.
4. lesson_focus: на чём сосредоточиться сегодня (1–2 предложения).
5. При необходимости — questions_to_user: массив вопросов к нему.
6. Слова для заучивания: если в ответах были русские вставки — ученик не знал этих слов по-английски. В блоке «Русские в ответе» перечислены такие фразы. Добавь для каждой английский эквивалент в words_to_learn.

Ответь ТОЛЬКО одним JSON-объектом (без markdown, без ```json). Формат:

{
  "errors": [ {"incorrect": "...", "correct": "...", "type": "grammar|vocab|spelling"} ],
  "answer_context": { "date": "YYYY-MM-DD", "context_ru": "перевод на русском" },
  "daily_message": "реплика по делу",
  "lesson_focus": "фокус на сегодня",
  "questions_to_user": [],
  "words_to_learn": [ {"russian": "фраза из ответа", "english": "English equivalent"} ]
}

Если ответ не повтор — answer_context может быть пустым объектом или с context_ru "".
date в answer_context — дата того ответа, для которого перевод (обычно последний в логе).

---
ДАННЫЕ:
"""
    prompt += f"\nСегодня: {data['today']}\n"
    prompt += f"Вопрос на сегодня: {question_today or '(нет)'}\n"
    prompt += f"Серия дней: {stats['current_streak']} | Speaking всего: {stats['total_speaking_days']} | Listening: {stats['total_listening_sessions']}\n\n"

    prompt += "Последние ответы (daily_log):\n"
    for L in data["daily_logs"]:
        prompt += f"  [{L['date']}] {L['question']}\n"
        prompt += f"    Ответ: {L['answer'] or '-'}\n"
        if L.get("answer_context_ru"):
            prompt += f"    Контекст уже: {L['answer_context_ru'][:80]}...\n"

    prompt += "\nПоследние listening:\n"
    for L in data["listening_logs"][:7]:
        prompt += f"  [{L['date']}] {L['material']} | {L['understood_pct']}%\n"
        for k in ("unclear", "pain_difficulty", "thoughts", "sentences_to_practice"):
            if L.get(k):
                prompt += f"    {k}: {L[k][:100]}...\n" if len(L.get(k, "")) > 100 else f"    {k}: {L[k]}\n"

    prompt += "\nПоследние ошибки (уже в базе):\n"
    for e in data["errors"][:15]:
        prompt += f"  {e['incorrect']} → {e['correct']}\n"

    words_raw = data.get("words_to_learn") or []
    if words_raw:
        prompt += "\nРусские в ответе (ученик не знал по-английски — добавь в words_to_learn с английским эквивалентом):\n"
        for w in words_raw[:25]:
            ru = w.get("russian_phrase") or ""
            en = w.get("english_phrase") or ""
            prompt += f"  «{ru}»" + (f" → {en}" if en else " (нужен английский)") + "\n"

    prompt += "\n---\nОтветь только JSON. НЕ показывай JSON пользователю: сохрани его в файл data/last_ai_response.json и выполни команду python3 run.py apply-ai data/last_ai_response.json. Пользователь не должен получать JSON в ответе — только примени ответ через команду."
    return prompt


def extract_json_from_text(text: str) -> dict | None:
    """Достать JSON из ответа ИИ (может быть обёрнут в markdown)."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def build_fix_export_prompt(text: str) -> str:
    """Промпт для ИИ: исправить текст с ошибками и русскими вставками, разбить на предложения, выдать JSON."""
    return f"""Текст ученика (возможны ошибки и русские слова вместо английских). Задачи:
1. Исправь все ошибки и замени русские вставки на корректный английский.
2. Разбей результат на корректные английские предложения.
3. Для каждого предложения дай перевод на русский.
4. Выпиши отдельно слова/фразы, в которых были ошибки или которые были по-русски (незнакомые) — в формате английское → русское.

Ответь ТОЛЬКО одним JSON-объектом (без markdown, без ```json):
{{
  "sentences": {{ "English sentence 1": "Русский перевод 1", "English sentence 2": "Русский перевод 2", ... }},
  "words": {{ "english_word": "русское", ... }}
}}

ТЕКСТ:
---
{text.strip()}
---
Ответь только JSON."""


def build_listening_export_prompt(sentences_text: str) -> str:
    """Промпт для ИИ: предложения для закрепления (англ. или англ. | рус.) → нормализовать в JSON en→ru."""
    return f"""Предложения для закрепления (могут быть в формате "English | Русский" или только английские). Задачи:
1. Разбей на отдельные предложения.
2. Для каждого предложения дай корректный английский вариант и перевод на русский.
3. Выпиши незнакомые/ошибочные слова как words: английское → русское.

Ответь ТОЛЬКО одним JSON-объектом (без markdown, без ```json):
{{
  "sentences": {{ "English sentence 1": "Русский перевод 1", ... }},
  "words": {{ "english_word": "русское", ... }}
}}

ТЕКСТ:
---
{sentences_text.strip()}
---
Ответь только JSON."""
