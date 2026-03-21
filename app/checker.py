"""
Проверка перевода RU→EN: сравнение с эталоном, тип ошибки, место ошибки.
Типы: spelling, missing_word, extra_word, word_order, grammar.
"""
import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class CheckResult:
    ok: bool
    error_type: str | None  # spelling | missing_word | extra_word | word_order | grammar
    problem_place: str | None
    hint: str | None  # пояснение для пользователя


def _normalize(s: str) -> str:
    return " ".join(s.split()).strip().lower()


def _strip_punctuation(s: str) -> str:
    """Убрать знаки препинания для сравнения (ошибка только в пунктуации не считается)."""
    return re.sub(r"[^\w\s]", "", s).strip()


def _tokenize(s: str) -> List[str]:
    return re.findall(r"\S+", s.lower())


def _levenshtein(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        cur = [i + 1]
        for j, cb in enumerate(b):
            cur.append(min(prev[j] + (0 if ca == cb else 1), prev[j + 1] + 1, cur[-1] + 1))
        prev = cur
    return prev[-1]


def _find_spelling_error(ref_words: List[str], user_words: List[str]) -> Tuple[str | None, str | None]:
    """Если одна опечатка (одно слово отличается на 1–2 символа), вернуть (ref_word, user_word)."""
    if len(ref_words) != len(user_words):
        return None, None
    for r, u in zip(ref_words, user_words):
        if r != u and len(r) > 0 and len(u) > 0:
            dist = _levenshtein(r, u)
            if 1 <= dist <= 2:
                return r, u
    return None, None


def _find_missing_word(ref_words: List[str], user_words: List[str]) -> str | None:
    """Пропущенное слово: в эталоне на одно слово больше, остальные совпадают по порядку."""
    if len(ref_words) != len(user_words) + 1:
        return None
    missing = None
    ui = 0
    for ri, r in enumerate(ref_words):
        if ui < len(user_words) and r == user_words[ui]:
            ui += 1
        else:
            if missing is not None:
                return None
            missing = r
    return missing


def _find_extra_word(ref_words: List[str], user_words: List[str]) -> str | None:
    if len(user_words) != len(ref_words) + 1:
        return None
    extra = None
    ri = 0
    for ui, u in enumerate(user_words):
        if ri < len(ref_words) and u == ref_words[ri]:
            ri += 1
        else:
            if extra is not None:
                return None
            extra = u
    return extra


def _word_order_wrong(ref_words: List[str], user_words: List[str]) -> bool:
    """Порядок слов нарушен при том же наборе (например what I should do vs what should I do)."""
    if len(ref_words) != len(user_words):
        return False
    return sorted(ref_words) == sorted(user_words) and ref_words != user_words


def _question_word_order_hint(ref: str, user: str) -> str | None:
    """Подсказка для типичной ошибки порядка в вопросе: Question word + auxiliary + subject + verb."""
    ref_l = ref.lower()
    user_l = user.lower()
    if "what" in ref_l and "should" in ref_l and " i " in ref_l:
        if "what i should" in user_l or "what i " in user_l:
            return "Question word + auxiliary + subject + verb\nWhat + should + I + do?"
    return None


def check_translation(reference: str, user_answer: str) -> CheckResult:
    """
    Сравнить ответ пользователя с эталоном. Эталон и ответ — английские предложения.
    Точка (и ? !) в конце не учитываются — забыл поставить не считается ошибкой.
    Троеточие (...) в эталоне не требуется вводить — не считается ошибкой.
    Если расхождение только в знаках препинания — не считается ошибкой.
    """
    ref_n = _normalize(reference).replace("...", "").rstrip(".!? ")
    user_n = _normalize(user_answer).replace("...", "").rstrip(".!? ")
    if ref_n == user_n:
        return CheckResult(ok=True, error_type=None, problem_place=None, hint=None)
    # Ошибка только в пунктуации?
    if _strip_punctuation(ref_n) == _strip_punctuation(user_n):
        return CheckResult(ok=True, error_type=None, problem_place=None, hint=None)

    ref_words = _tokenize(ref_n)
    user_words = _tokenize(user_n)

    # 1) Орфография: одно слово с опечаткой (расстояние Левенштейна 1–2)
    rw, uw = _find_spelling_error(ref_words, user_words)
    if rw is not None:
        pos = ref_n.find(rw)
        return CheckResult(
            ok=False,
            error_type="spelling",
            problem_place=rw,
            hint=f'пропущена буква "u"' if "u" in rw and "u" not in uw else f"ожидалось: {rw}",
        )

    # 2) Пропущенное слово
    missing = _find_missing_word(ref_words, user_words)
    if missing is not None:
        return CheckResult(
            ok=False,
            error_type="missing_word",
            problem_place=missing,
            hint=f"Пропущено слово: {missing}",
        )

    # 3) Лишнее слово
    extra = _find_extra_word(ref_words, user_words)
    if extra is not None:
        return CheckResult(
            ok=False,
            error_type="extra_word",
            problem_place=extra,
            hint=f"Лишнее слово: {extra}",
        )

    # 4) Порядок слов (тот же набор, другой порядок)
    if _word_order_wrong(ref_words, user_words):
        order_hint = _question_word_order_hint(reference, user_answer)
        return CheckResult(
            ok=False,
            error_type="word_order",
            problem_place=user_answer,
            hint=order_hint or "Неправильный порядок слов.",
        )

    # 5) Грамматика / прочее
    return CheckResult(
        ok=False,
        error_type="grammar",
        problem_place=user_answer,
        hint="Проверь грамматику и порядок слов.",
    )


def format_error_display(reference: str, user_answer: str, result: CheckResult) -> str:
    """Текстовый вывод с одинаковой длиной строк и посимвольным выравниванием (для моноширинного шрифта)."""
    PREFIX_USER = "Ваш ответ:    "
    PREFIX_REF = "Правильный:   "
    line_user = PREFIX_USER + user_answer
    line_ref = PREFIX_REF + reference
    max_len = max(len(line_user), len(line_ref), 50)
    line_user = line_user.ljust(max_len)
    line_ref = line_ref.ljust(max_len)
    lines = [line_user, line_ref]
    if result.error_type == "spelling" and result.problem_place:
        idx = reference.lower().find(result.problem_place.lower())
        if idx >= 0:
            caret_pos = len(PREFIX_REF) + idx
            caret_line = (" " * caret_pos) + "↑"
            if result.hint:
                caret_line += "  " + result.hint
            lines.append(caret_line.ljust(max_len))
    ref_words = _tokenize(_normalize(reference))
    user_words = _tokenize(_normalize(user_answer))
    diffs = []
    for i, (r, u) in enumerate(zip(ref_words, user_words)):
        if r != u:
            diffs.append((i + 1, r, u))
    if len(ref_words) != len(user_words) or diffs:
        if diffs:
            lines.append("")
            for i, r, u in diffs[:10]:
                lines.append(f"  Слово {i}: эталон «{r}» — у вас «{u}»")
        if len(ref_words) != len(user_words):
            lines.append(f"  Количество слов: эталон {len(ref_words)}, у вас {len(user_words)}")
    lines.append("")
    lines.append(f"Тип ошибки: {result.error_type}")
    return "\n".join(lines)
