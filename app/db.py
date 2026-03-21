"""
SQLite database for English System.
All data stored here — no manual file writing.
"""
import sqlite3
from pathlib import Path
from datetime import date, datetime
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "english_system.db"

# Pomodoro: 25 min work, 5 min break, 25 min work
POMODORO_WORK = 25
POMODORO_BREAK = 5


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS weeks (
                id INTEGER PRIMARY KEY,
                week_number INTEGER NOT NULL,
                year INTEGER NOT NULL,
                goal TEXT,
                listening_source TEXT,
                error_focus TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(week_number, year)
            );

            CREATE TABLE IF NOT EXISTS daily_questions (
                id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,  -- 0=Mon .. 6=Sun
                question TEXT NOT NULL,
                is_test INTEGER DEFAULT 0,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            CREATE TABLE IF NOT EXISTS daily_log (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL UNIQUE,
                question TEXT,
                answer TEXT,
                answer_context_ru TEXT,
                is_speaking_test INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS listening_log (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                material TEXT,
                duration_min INTEGER,
                understood_pct INTEGER,
                unknown_words TEXT,
                unclear TEXT,
                pain_difficulty TEXT,
                thoughts TEXT,
                sentences_to_practice TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY,
                date TEXT,
                incorrect TEXT,
                correct TEXT,
                error_type TEXT,
                repeated INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS weekly_sentences (
                id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                english TEXT NOT NULL,
                translation TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                avg_response_sentences REAL,
                longest_speech_sec INTEGER,
                errors_per_10_sentences INTEGER,
                fluency_self_rating INTEGER,
                listening_pct INTEGER,
                active_words INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            CREATE TABLE IF NOT EXISTS weekly_reviews (
                id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                what_worked TEXT,
                what_difficult TEXT,
                main_problem TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            CREATE TABLE IF NOT EXISTS portrait (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                content TEXT,
                source_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ai_daily_message (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL UNIQUE,
                message TEXT NOT NULL,
                lesson_focus TEXT,
                tone_rating INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS words_to_learn (
                id INTEGER PRIMARY KEY,
                russian_phrase TEXT NOT NULL,
                english_phrase TEXT,
                date TEXT NOT NULL,
                source TEXT DEFAULT 'speaking',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS weekly_words (
                id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                english TEXT NOT NULL,
                translation TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            CREATE TABLE IF NOT EXISTS translation_errors (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                week_number INTEGER NOT NULL,
                year INTEGER NOT NULL,
                reference_text TEXT NOT NULL,
                user_answer TEXT NOT NULL,
                error_type TEXT NOT NULL,
                problem_place TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS block_progress (
                id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL UNIQUE,
                sentences_last_attempted INTEGER DEFAULT 0,
                sentences_last_correct INTEGER DEFAULT 0,
                sentences_passed INTEGER DEFAULT 0,
                sentences_rounds_done INTEGER DEFAULT 0,
                words_last_attempted INTEGER DEFAULT 0,
                words_last_correct INTEGER DEFAULT 0,
                words_passed INTEGER DEFAULT 0,
                words_rounds_done INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            CREATE TABLE IF NOT EXISTS audio_files (
                id INTEGER PRIMARY KEY,
                week_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                text_en TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            CREATE TABLE IF NOT EXISTS typing_stats (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                week_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                reference_text TEXT NOT NULL,
                time_seconds REAL NOT NULL,
                char_count INTEGER NOT NULL,
                correct INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (week_id) REFERENCES weeks(id)
            );

            INSERT OR IGNORE INTO settings (key, value) VALUES
                ('pomodoro_work', '25'),
                ('pomodoro_break', '5');
        """)
        _migrate_add_columns(conn)


def _migrate_add_columns(conn):
    """Add new columns if they don't exist (for existing DBs)."""
    for table, col, typ in [
        ("daily_log", "answer_context_ru", "TEXT"),
        ("listening_log", "unclear", "TEXT"),
        ("listening_log", "pain_difficulty", "TEXT"),
        ("listening_log", "thoughts", "TEXT"),
        ("listening_log", "sentences_to_practice", "TEXT"),
        ("block_progress", "sentences_rounds_done", "INTEGER DEFAULT 0"),
        ("block_progress", "words_rounds_done", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass


def get_today() -> date:
    return date.today()


def get_current_week_number(d: date = None) -> int:
    d = d or date.today()
    return d.isocalendar()[1]


def get_current_year(d: date = None) -> int:
    return (d or date.today()).year


def get_day_of_week(d: date = None) -> int:
    """0=Monday, 6=Sunday."""
    return (d or date.today()).weekday()


def get_or_create_week(week_num: int, year: int) -> int:
    """Return week_id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM weeks WHERE week_number = ? AND year = ?",
            (week_num, year)
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO weeks (week_number, year) VALUES (?, ?)",
            (week_num, year)
        )
        return cur.lastrowid


# --- Порции (пакеты слов/предложений для изучения) ---
CURRENT_PORTION_KEY = "current_portion_id"


def get_current_portion_id() -> int:
    """ID текущей порции (week_id). По умолчанию — первая порция в БД."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (CURRENT_PORTION_KEY,)
        ).fetchone()
        if row and row["value"]:
            return int(row["value"])
        first = conn.execute("SELECT id FROM weeks ORDER BY id LIMIT 1").fetchone()
        if first:
            wid = first["id"]
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (CURRENT_PORTION_KEY, str(wid))
            )
            return wid
    # Нет ни одной порции — создаём первую
    year = get_current_year()
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO weeks (week_number, year) VALUES (1, ?)", (year,))
        wid = cur.lastrowid
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (CURRENT_PORTION_KEY, str(wid))
        )
        return wid


def set_current_portion_id(week_id: int):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (CURRENT_PORTION_KEY, str(week_id))
        )


def list_portions() -> list[dict]:
    """Список порций: id, week_number, year, sentences_count, words_count."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT w.id, w.week_number, w.year,
                      (SELECT COUNT(*) FROM weekly_sentences WHERE week_id = w.id) AS sentences_count,
                      (SELECT COUNT(*) FROM weekly_words WHERE week_id = w.id) AS words_count
               FROM weeks w ORDER BY w.id"""
        ).fetchall()
        return [dict(zip(r.keys(), r)) for r in rows]


def create_next_portion() -> int:
    """Создать новую порцию (следующий week_number за последним) и сделать её текущей."""
    year = get_current_year()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(week_number), 0) + 1 AS next_num FROM weeks WHERE year = ?",
            (year,)
        ).fetchone()
        next_num = row["next_num"] if row else 1
        cur = conn.execute(
            "INSERT INTO weeks (week_number, year) VALUES (?, ?)",
            (next_num, year)
        )
        wid = cur.lastrowid
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (CURRENT_PORTION_KEY, str(wid))
        )
        return wid


def get_todays_question() -> str | None:
    """Get today's speaking question from weekly plan."""
    today = get_today()
    week_num = get_current_week_number(today)
    year = get_current_year(today)
    day = get_day_of_week(today)
    with get_connection() as conn:
        week_id = get_or_create_week(week_num, year)
        row = conn.execute(
            "SELECT question FROM daily_questions WHERE week_id = ? AND day_of_week = ?",
            (week_id, day)
        ).fetchone()
        return row["question"] if row else None


def save_speaking_answer(question: str, answer: str, is_test: bool = False):
    today = str(get_today())
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT answer_context_ru FROM daily_log WHERE date = ?", (today,)
        ).fetchone()
        ctx = existing["answer_context_ru"] if existing and existing["answer_context_ru"] else ""
        conn.execute(
            """INSERT OR REPLACE INTO daily_log (date, question, answer, answer_context_ru, is_speaking_test)
               VALUES (?, ?, ?, ?, ?)""",
            (today, question, answer, ctx, 1 if is_test else 0)
        )
    for phrase in extract_russian_from_text(answer):
        if phrase.strip():
            add_word_to_learn(phrase.strip(), "", today, "speaking")


def extract_russian_from_text(text: str) -> list[str]:
    """Русские вставки в тексте = слова, которые пользователь не знает по-английски."""
    if not text:
        return []
    import re
    chunks = re.findall(r"[а-яёА-ЯЁ\s\-]+", text)
    return [c.strip() for c in chunks if len(c.strip()) > 0]


def add_word_to_learn(russian_phrase: str, english_phrase: str, date: str = None, source: str = "speaking"):
    date = date or str(get_today())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO words_to_learn (russian_phrase, english_phrase, date, source) VALUES (?, ?, ?, ?)",
            (russian_phrase.strip(), (english_phrase or "").strip(), date, source)
        )


def get_words_to_learn(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT russian_phrase, english_phrase, date, source FROM words_to_learn ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_last_listening_sentences() -> str:
    """Текст предложений для закрепления из последней записи listening."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT sentences_to_practice FROM listening_log WHERE sentences_to_practice IS NOT NULL AND sentences_to_practice != '' ORDER BY date DESC LIMIT 1"
        ).fetchone()
        return (row["sentences_to_practice"] or "").strip() if row else ""


def save_listening(material: str, duration_min: int, understood_pct: int, unknown_words: str = "",
                  unclear: str = "", pain_difficulty: str = "", thoughts: str = "",
                  sentences_to_practice: str = ""):
    today = str(get_today())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO listening_log (
                   date, material, duration_min, understood_pct, unknown_words,
                   unclear, pain_difficulty, thoughts, sentences_to_practice)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (today, material, duration_min, understood_pct, unknown_words,
             unclear, pain_difficulty, thoughts, sentences_to_practice)
        )


def add_error(incorrect: str, correct: str, error_type: str = "grammar"):
    today = str(get_today())
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO errors (date, incorrect, correct, error_type) VALUES (?, ?, ?, ?)",
            (today, incorrect, correct, error_type)
        )


def get_weekly_sentences(week_id: int = None) -> list[dict]:
    """Предложения порции. Если week_id не указан — текущая порция."""
    if week_id is None:
        week_id = get_current_portion_id()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT english, translation FROM weekly_sentences WHERE week_id = ? ORDER BY sort_order",
            (week_id,)
        ).fetchall()
        return [dict(zip(r.keys(), r)) for r in rows]


def get_recent_errors(limit: int = 7) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT incorrect, correct FROM errors ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_yesterday_answer() -> str | None:
    from datetime import timedelta
    yesterday = get_today() - timedelta(days=1)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT answer FROM daily_log WHERE date = ?",
            (str(yesterday),)
        ).fetchone()
        return row["answer"] if row else None


def get_last_answer_with_context():
    """Для повтора: последний ответ (англ.) + контекст/перевод на русском."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT date, question, answer, answer_context_ru
               FROM daily_log WHERE answer IS NOT NULL AND answer != ''
               ORDER BY date DESC LIMIT 1"""
        ).fetchone()
        if not row:
            return None
        return {
            "date": row["date"],
            "question": row["question"],
            "answer": row["answer"],
            "context_ru": (row["answer_context_ru"] or "").strip(),
        }


def set_answer_context_ru(log_date: str, context_ru: str):
    """Записать контекст/перевод от ИИ для ответа за указанную дату."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE daily_log SET answer_context_ru = ? WHERE date = ?",
            (context_ru.strip(), log_date)
        )


def get_prep_data(days_back: int = 7) -> dict:
    """Данные для ИИ-агента: подготовка урока на сегодня."""
    today = get_today()
    with get_connection() as conn:
        from datetime import timedelta
        start = today - timedelta(days=days_back)
        start_s = str(start)
        logs = conn.execute(
            """SELECT date, question, answer, answer_context_ru
               FROM daily_log WHERE date >= ? ORDER BY date DESC""",
            (start_s,)
        ).fetchall()
        listenings = conn.execute(
            """SELECT date, material, duration_min, understood_pct, unknown_words,
                      unclear, pain_difficulty, thoughts, sentences_to_practice
               FROM listening_log WHERE date >= ? ORDER BY date DESC""",
            (start_s,)
        ).fetchall()
        errs = conn.execute(
            "SELECT date, incorrect, correct FROM errors ORDER BY id DESC LIMIT 20"
        ).fetchall()
        words = conn.execute(
            "SELECT russian_phrase, english_phrase FROM words_to_learn ORDER BY id DESC LIMIT 30"
        ).fetchall()
    return {
        "today": str(today),
        "daily_logs": [dict(r) for r in logs],
        "listening_logs": [dict(r) for r in listenings],
        "errors": [dict(r) for r in errs],
        "words_to_learn": [dict(r) for r in words],
    }


def apply_ai_response(data: dict) -> list[str]:
    """
    Применить ответ ИИ (JSON) к БД. Возвращает список сообщений об ошибках (пусто = всё ок).
    data: dict с полями errors, answer_context?, daily_message, lesson_focus?, questions_to_user?
    """
    today = str(get_today())
    errors_out = []
    try:
        with get_connection() as conn:
            if data.get("errors"):
                for e in data["errors"]:
                    inc = e.get("incorrect") or ""
                    corr = e.get("correct") or ""
                    if inc and corr:
                        conn.execute(
                            "INSERT INTO errors (date, incorrect, correct, error_type) VALUES (?, ?, ?, ?)",
                            (today, inc, corr, e.get("type") or "grammar")
                        )
            if data.get("answer_context"):
                ac = data["answer_context"]
                conn.execute(
                    "UPDATE daily_log SET answer_context_ru = ? WHERE date = ?",
                    (ac.get("context_ru", "").strip(), ac.get("date", today))
                )
            msg = (data.get("daily_message") or "").strip()
            focus = (data.get("lesson_focus") or "").strip()
            if msg:
                conn.execute(
                    """INSERT OR REPLACE INTO ai_daily_message (date, message, lesson_focus)
                       VALUES (?, ?, ?)""",
                    (today, msg, focus)
                )
            for w in data.get("words_to_learn") or []:
                ru = (w.get("russian") or w.get("russian_phrase") or "").strip()
                en = (w.get("english") or w.get("english_phrase") or "").strip()
                if ru and en:
                    conn.execute(
                        """INSERT INTO words_to_learn (russian_phrase, english_phrase, date, source)
                           VALUES (?, ?, ?, 'ai')""",
                        (ru, en, today)
                    )
    except Exception as ex:
        errors_out.append(str(ex))
    return errors_out


def get_todays_message() -> dict | None:
    """Сообщение от ИИ на сегодня (daily_message + lesson_focus)."""
    today = str(get_today())
    with get_connection() as conn:
        row = conn.execute(
            "SELECT message, lesson_focus FROM ai_daily_message WHERE date = ?",
            (today,)
        ).fetchone()
        if not row:
            return None
        return {"message": row["message"], "lesson_focus": row["lesson_focus"]}


def set_tone_rating(rating: int):
    """Оценка тона сегодняшнего сообщения (1–5)."""
    today = str(get_today())
    with get_connection() as conn:
        conn.execute(
            "UPDATE ai_daily_message SET tone_rating = ? WHERE date = ?",
            (max(1, min(5, rating)), today)
        )


def get_stats() -> dict:
    """Basic statistics."""
    with get_connection() as conn:
        total_days = conn.execute(
            "SELECT COUNT(*) FROM daily_log"
        ).fetchone()[0]
        total_listening = conn.execute(
            "SELECT COUNT(*) FROM listening_log"
        ).fetchone()[0]
        total_errors = conn.execute(
            "SELECT COUNT(*) FROM errors"
        ).fetchone()[0]
        streak = 0
        d = get_today()
        while True:
            row = conn.execute(
                "SELECT 1 FROM daily_log WHERE date = ?",
                (str(d),)
            ).fetchone()
            if not row:
                break
            streak += 1
            d = d - __import__("datetime").timedelta(days=1)
        return {
            "total_speaking_days": total_days,
            "total_listening_sessions": total_listening,
            "total_errors": total_errors,
            "current_streak": streak,
        }


# --- Тренажёр перевода (RU→EN), блоки 80%, аудио ---

def get_weekly_words(week_id: int = None) -> list[dict]:
    """Слова порции. Если week_id не указан — текущая порция."""
    if week_id is None:
        week_id = get_current_portion_id()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT english, translation FROM weekly_words WHERE week_id = ? ORDER BY sort_order",
            (week_id,)
        ).fetchall()
        return [dict(zip(r.keys(), r)) for r in rows]


def add_weekly_words(week_id: int, words: dict) -> int:
    """Добавить слова недели. words: {english: translation}. Возвращает количество добавленных (без дубликатов)."""
    added = 0
    with get_connection() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM weekly_words WHERE week_id = ?", (week_id,)
        ).fetchone()[0]
        for i, (en, ru) in enumerate(words.items()):
            en, ru = en.strip(), (ru or "").strip()
            if not en:
                continue
            cur = conn.execute(
                "SELECT 1 FROM weekly_words WHERE week_id = ? AND LOWER(TRIM(english)) = LOWER(?)",
                (week_id, en)
            ).fetchone()
            if not cur:
                conn.execute(
                    "INSERT INTO weekly_words (week_id, english, translation, sort_order) VALUES (?, ?, ?, ?)",
                    (week_id, en, ru, max_order + 1 + i)
                )
                added += 1
    return added


def add_weekly_sentences(week_id: int, sentences: dict) -> int:
    """Добавить предложения недели. sentences: {english: translation}. Без дубликатов по english."""
    added = 0
    with get_connection() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM weekly_sentences WHERE week_id = ?", (week_id,)
        ).fetchone()[0]
        for i, (en, ru) in enumerate(sentences.items()):
            en, ru = (en or "").strip(), (ru or "").strip()
            if not en:
                continue
            cur = conn.execute(
                "SELECT 1 FROM weekly_sentences WHERE week_id = ? AND LOWER(TRIM(english)) = LOWER(?)",
                (week_id, en)
            ).fetchone()
            if not cur:
                conn.execute(
                    "INSERT INTO weekly_sentences (week_id, english, translation, sort_order) VALUES (?, ?, ?, ?)",
                    (week_id, en, ru, max_order + 1 + i)
                )
                added += 1
    return added


def add_translation_error(reference_text: str, user_answer: str, error_type: str, problem_place: str = None):
    today = str(get_today())
    week_num = get_current_week_number()
    year = get_current_year()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO translation_errors (date, week_number, year, reference_text, user_answer, error_type, problem_place)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (today, week_num, year, reference_text.strip(), user_answer.strip(), error_type, (problem_place or "").strip())
        )
    add_error(user_answer, reference_text, error_type)


def add_manual_translation_error(reference_text: str, user_answer: str):
    """Ручная запись ошибки: правильный и неправильный вариант (без типа ошибки). Использует текущую порцию."""
    today = str(get_today())
    portion_id = get_current_portion_id()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT week_number, year FROM weeks WHERE id = ?", (portion_id,)
        ).fetchone()
        week_num = row["week_number"] if row else 1
        year = row["year"] if row else get_current_year()
        conn.execute(
            """INSERT INTO translation_errors (date, week_number, year, reference_text, user_answer, error_type, problem_place)
               VALUES (?, ?, ?, ?, ?, 'manual', '')""",
            (today, week_num, year, reference_text.strip(), user_answer.strip())
        )


def get_recent_translation_errors(limit: int = 30) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT reference_text, user_answer, error_type, problem_place, date
               FROM translation_errors ORDER BY id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_block_progress(week_id: int = None) -> dict:
    if week_id is None:
        today = get_today()
        week_num = get_current_week_number(today)
        year = get_current_year(today)
        week_id = get_or_create_week(week_num, year)
    with get_connection() as conn:
        row = conn.execute(
            """SELECT sentences_last_attempted, sentences_last_correct, sentences_passed,
                      sentences_rounds_done, words_last_attempted, words_last_correct, words_passed, words_rounds_done
               FROM block_progress WHERE week_id = ?""",
            (week_id,)
        ).fetchone()
        if not row:
            return {
                "sentences_last_attempted": 0, "sentences_last_correct": 0, "sentences_passed": 0, "sentences_rounds_done": 0,
                "words_last_attempted": 0, "words_last_correct": 0, "words_passed": 0, "words_rounds_done": 0,
            }
        return dict(zip(row.keys(), row))


def set_block_progress(week_id: int, block_type: str, attempted: int, correct: int):
    """Записать результат прохода блока. passed=1 если correct/attempted >= 0.8. Увеличивает счётчик кругов."""
    passed = (correct / attempted >= 0.8) if attempted else False
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO block_progress (week_id, sentences_last_attempted, sentences_last_correct, sentences_passed,
                  sentences_rounds_done, words_last_attempted, words_last_correct, words_passed, words_rounds_done, updated_at)
               VALUES (?, 0, 0, 0, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP)""",
            (week_id,)
        )
        if block_type == "sentences":
            conn.execute(
                """UPDATE block_progress SET sentences_rounds_done = sentences_rounds_done + 1,
                   sentences_last_attempted = ?, sentences_last_correct = ?,
                   sentences_passed = ?, updated_at = CURRENT_TIMESTAMP WHERE week_id = ?""",
                (attempted, correct, 1 if passed else 0, week_id)
            )
        else:
            conn.execute(
                """UPDATE block_progress SET words_rounds_done = words_rounds_done + 1,
                   words_last_attempted = ?, words_last_correct = ?,
                   words_passed = ?, updated_at = CURRENT_TIMESTAMP WHERE week_id = ?""",
                (attempted, correct, 1 if passed else 0, week_id)
            )
    return passed


def add_typing_stat(week_id: int, content_type: str, reference_text: str, time_seconds: float, char_count: int, correct: bool):
    today = str(get_today())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO typing_stats (date, week_id, content_type, reference_text, time_seconds, char_count, correct)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (today, week_id, content_type, reference_text.strip(), time_seconds, char_count, 1 if correct else 0)
        )


def get_typing_stats(week_id: int = None, limit: int = 100) -> dict:
    """Средняя скорость: символов в минуту общая и только по правильным ответам."""
    if week_id is None:
        week_id = get_or_create_week(get_current_week_number(), get_current_year())
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT time_seconds, char_count, correct FROM typing_stats WHERE week_id = ? ORDER BY id DESC LIMIT ?""",
            (week_id, limit)
        ).fetchall()
    if not rows:
        return {"chars_per_min_all": 0, "chars_per_min_correct": 0, "count_all": 0, "count_correct": 0}
    total_sec = sum(r["time_seconds"] for r in rows)
    total_chars = sum(r["char_count"] for r in rows)
    correct_rows = [r for r in rows if r["correct"]]
    correct_sec = sum(r["time_seconds"] for r in correct_rows)
    correct_chars = sum(r["char_count"] for r in correct_rows)
    chars_per_min_all = (total_chars / total_sec * 60) if total_sec > 0 else 0
    chars_per_min_correct = (correct_chars / correct_sec * 60) if correct_sec > 0 else 0
    return {
        "chars_per_min_all": round(chars_per_min_all, 1),
        "chars_per_min_correct": round(chars_per_min_correct, 1),
        "count_all": len(rows),
        "count_correct": len(correct_rows),
    }


def seed_week1():
    """Seed Week 1 data from existing plan. Only if week has no questions yet."""
    today = get_today()
    week_num = get_current_week_number(today)
    year = get_current_year(today)
    with get_connection() as conn:
        week_id = get_or_create_week(week_num, year)
        # Skip if already seeded
        has_questions = conn.execute(
            "SELECT 1 FROM daily_questions WHERE week_id = ?", (week_id,)
        ).fetchone()
        if has_questions:
            return
        conn.execute(
            "UPDATE weeks SET goal = ?, listening_source = ?, error_focus = ? WHERE id = ?",
            (
                "Закрепить фразы про расписание и «вчера» без ошибок по орфографии и времени.",
                "6 Minute English (BBC) / English with Lucy (YouTube) / куски из книги с TTS",
                "hour/hours, usually, again, everything, from … to, until; present simple для привычек",
                week_id
            )
        )
        questions = [
            (0, "What do you usually do in the morning? (4–7 предложений)", 0),
            (1, "What time do you start work? What time do you finish? (2–4 предложения)", 0),
            (2, "What did you do yesterday? (только past simple: I worked, I learned, I went…)", 0),
            (3, "Why do you learn English? (2–3 предложения, используй I'm a programmer / I have to)", 0),
            (4, "Describe your day today. (from … to, until; present simple)", 0),
            (5, "Повтор: What did you do yesterday? ещё раз, без подглядывания", 0),
            (6, "Speaking-тест: (1) Daily routine, (2) What did you do yesterday?", 1),
        ]
        for day, q, is_test in questions:
            conn.execute(
                "INSERT OR IGNORE INTO daily_questions (week_id, day_of_week, question, is_test) VALUES (?, ?, ?, ?)",
                (week_id, day, q, is_test)
            )
        sentences = [
            ("I usually work from 6 a.m. to 10 a.m.", "Я обычно работаю с 6 до 10 утра."),
            ("Then I learn English for one hour.", "Потом я учу английский один час."),
            ("I learn programming around 5 p.m.", "Я учу программирование около 5 вечера."),
            ("Then I go to work again.", "Потом я снова иду на работу."),
            ("I work until 9 p.m. there.", "Там я работаю до 9 вечера."),
            ("Then I go to bed.", "Потом я иду спать."),
            ("I'm a programmer and I have to know English.", "Я программист, и мне нужно знать английский."),
            ("I don't know what is the most difficult. I like everything.", "Не знаю, что сложнее всего. Мне нравится всё."),
            ("Yesterday I followed my usual daily routine.", "Вчера я делал то же, что обычно — следовал своему распорядку дня."),
            ("I start work at 6 a.m. and finish before 10 a.m.", "Я начинаю работу в 6 утра и заканчиваю до 10 утра."),
        ]
        for i, (en, ru) in enumerate(sentences):
            conn.execute(
                "INSERT OR IGNORE INTO weekly_sentences (week_id, english, translation, sort_order) VALUES (?, ?, ?, ?)",
                (week_id, en, ru, i)
            )
