#!/usr/bin/env python3
"""
English System — десктопное приложение.
Таймер (25/5 мин), тренажёр перевода RU→EN по текущей порции. Данные только из import-json.
"""
import sys
import time
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import (
    init_db,
    seed_week1,
    get_current_portion_id,
    list_portions,
    set_current_portion_id,
    create_next_portion,
    get_weekly_sentences,
    get_weekly_words,
    add_translation_error,
    add_manual_translation_error,
    add_typing_stat,
    DB_PATH,
    POMODORO_WORK,
    POMODORO_BREAK,
)
from app.checker import check_translation, format_error_display

SOUNDS_DIR = DB_PATH.parent / "sounds"
START_WAV = SOUNDS_DIR / "start.wav"
END_WAV = SOUNDS_DIR / "end.wav"


def _play_sound(path: Path, widget: tk.Widget = None):
    """Воспроизвести WAV; если файла нет — системный beep (widget.bell())."""
    if path.exists():
        try:
            subprocess.run(
                ["aplay", "-q", str(path)],
                check=False, capture_output=True, timeout=2
            )
            return
        except FileNotFoundError:
            pass
        try:
            subprocess.run(
                ["paplay", str(path)],
                check=False, capture_output=True, timeout=2
            )
            return
        except FileNotFoundError:
            pass
    if widget:
        try:
            widget.bell()
        except Exception:
            pass


class TimerState:
    IDLE = "idle"
    WORK = "work"
    BREAK = "break"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db()
        seed_week1()
        self.title("English System")
        self.geometry("720x560")
        self.minsize(560, 420)

        self.timer_state = TimerState.IDLE
        self.timer_remaining = 0
        self.timer_job = None
        self.phase_name = ""

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Шапка: таймер справа (как раньше), слева — порция и кнопки
        header = ttk.Frame(main)
        header.pack(fill=tk.X)
        # Сначала таймер справа, чтобы не уезжал за край при узком окне
        f_timer = ttk.LabelFrame(header, text="Помодоро 25 — 5 — 25")
        f_timer.pack(side=tk.RIGHT, padx=(12, 0))
        row = ttk.Frame(f_timer)
        row.pack(fill=tk.X)
        self.lbl_timer = ttk.Label(row, text="25:00", font=("", 20))
        self.lbl_timer.pack(side=tk.LEFT, padx=(0, 8))
        self.lbl_phase = ttk.Label(row, text="", font=("", 11))
        self.lbl_phase.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row, text="25 мин", command=lambda: self._start_timer(POMODORO_WORK, "Работа")).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="5 мин", command=lambda: self._start_timer(POMODORO_BREAK, "Перерыв")).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="Стоп", command=self._stop_timer).pack(side=tk.LEFT, padx=2)

        left = ttk.Frame(header)
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_portion = ttk.Label(left, text="", font=("", 11))
        self.lbl_portion.pack(side=tk.LEFT)
        ttk.Button(left, text="Сменить порцию", command=self._choose_portion).pack(side=tk.LEFT, padx=8)
        ttk.Button(left, text="Следующая порция", command=self._next_portion).pack(side=tk.LEFT, padx=2)

        self._build_trainer_tab(main)
        self._refresh_portion_label()

    def _refresh_portion_label(self):
        portion_id = get_current_portion_id()
        portions = list_portions()
        cur = next((p for p in portions if p["id"] == portion_id), None)
        if cur:
            self.lbl_portion.config(
                text=f"Порция id={portion_id}  |  предложений: {cur['sentences_count']}  |  слов: {cur['words_count']}"
            )
        else:
            self.lbl_portion.config(text=f"Порция id={portion_id}")

    def _choose_portion(self):
        portions = list_portions()
        if not portions:
            messagebox.showinfo("", "Нет порций. Добавь данные: python run.py import-json file.json")
            return
        current = get_current_portion_id()
        win = tk.Toplevel(self)
        win.title("Выбор порции")
        win.geometry("360x280")
        ttk.Label(win, text="Выбери порцию (двойной клик или выбери и кнопка):", font=("", 10)).pack(anchor=tk.W, padx=8, pady=8)
        listbox = tk.Listbox(win, height=10, font=("", 11))
        listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        for p in portions:
            mark = " *" if p["id"] == current else ""
            listbox.insert(tk.END, f"id={p['id']}  предложений: {p['sentences_count']}  слов: {p['words_count']}{mark}")
        if portions:
            listbox.selection_set(0)

        def on_apply():
            sel = listbox.curselection()
            if not sel:
                return
            idx = int(sel[0])
            set_current_portion_id(portions[idx]["id"])
            self._refresh_portion_label()
            self._train_load()
            win.destroy()

        ttk.Button(win, text="Применить", command=on_apply).pack(pady=8)
        listbox.bind("<Double-Button-1>", lambda e: on_apply())

    def _next_portion(self):
        create_next_portion()
        self._refresh_portion_label()
        self._train_load()
        messagebox.showinfo("", "Создана новая порция. Добавь данные: python run.py import-json file.json")

    def _start_timer(self, minutes: int, phase: str):
        self._stop_timer()
        _play_sound(START_WAV, self)
        self.timer_remaining = minutes * 60
        self.phase_name = phase
        self.lbl_phase.config(text=phase)
        self._tick()

    def _stop_timer(self):
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.lbl_timer.config(text="25:00")
        self.lbl_phase.config(text="")

    def _tick(self):
        if self.timer_remaining <= 0:
            _play_sound(END_WAV, self)
            self._stop_timer()
            messagebox.showinfo("Помодоро", "Время вышло!")
            return
        m, s = divmod(self.timer_remaining, 60)
        self.lbl_timer.config(text=f"{m:02d}:{s:02d}")
        self.timer_remaining -= 1
        self.timer_job = self.after(1000, self._tick)

    def _build_trainer_tab(self, parent):
        f = ttk.Frame(parent, padding=8)
        f.pack(fill=tk.BOTH, expand=True)
        self.train_items = []
        self.train_index = 0
        self.train_first_attempt = []  # None / True / False
        self.train_peeked = []  # True если нажал «Посмотреть ответ»
        self.train_type = "sentences"

        row_mode = ttk.Frame(f)
        row_mode.pack(fill=tk.X)
        ttk.Label(row_mode, text="Режим:").pack(side=tk.LEFT)
        self.train_mode_var = tk.StringVar(value="sentences")
        ttk.Radiobutton(row_mode, text="Предложения", variable=self.train_mode_var, value="sentences", command=self._train_load).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(row_mode, text="Слова", variable=self.train_mode_var, value="words", command=self._train_load).pack(side=tk.LEFT, padx=4)

        ttk.Label(f, text="Перевод (RU → EN). Если нажал «Посмотреть ответ» — пункт не идёт в процент успешных.", font=("", 9)).pack(anchor=tk.W)
        ttk.Label(f, text="Перевод (RU → EN):").pack(anchor=tk.W)
        self.train_ru_label = ttk.Label(f, text="—", font=("", 12))
        self.train_ru_label.pack(anchor=tk.W, pady=4)

        # Кнопка «Посмотреть ответ» / «Скрыть ответ»
        self.train_answer_visible = False
        self.train_answer_label = ttk.Label(f, text="", font=("", 11), foreground="gray")
        self.train_show_btn = ttk.Button(f, text="Посмотреть ответ", command=self._train_toggle_answer)
        self.train_show_btn.pack(anchor=tk.W, pady=2)
        self.train_answer_label.pack(anchor=tk.W, pady=2)

        self.train_en_entry = ttk.Entry(f, width=60)
        self.train_en_entry.pack(fill=tk.X, pady=4)
        self.train_en_entry.bind("<Return>", lambda e: self._train_check())

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Проверить", command=self._train_check).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Дальше", command=self._train_next).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Начать круг заново", command=self._train_restart_round).pack(side=tk.LEFT, padx=8)

        self.train_result = ttk.Label(f, text="", wraplength=560)
        self.train_result.pack(anchor=tk.W, pady=4)
        self.train_error_btn = ttk.Button(f, text="Записать ошибку", command=self._train_record_error)
        self.train_error_btn.pack(anchor=tk.W, pady=2)
        self.train_error_btn_visible = False

        self.train_progress_label = ttk.Label(f, text="")
        self.train_progress_label.pack(anchor=tk.W)

        self._train_load()

    def _train_toggle_answer(self):
        if not self.train_items or self.train_index >= len(self.train_items):
            return
        self.train_answer_visible = not self.train_answer_visible
        item = self.train_items[self.train_index]
        en = item.get("english", "")
        if self.train_answer_visible:
            self.train_answer_label.config(text=f"Ответ: {en}", foreground="gray")
            self.train_show_btn.config(text="Скрыть ответ")
            idx = self.train_index
            if idx < len(self.train_peeked):
                self.train_peeked[idx] = True
        else:
            self.train_answer_label.config(text="")
            self.train_show_btn.config(text="Посмотреть ответ")
        self.train_answer_label.pack(anchor=tk.W, pady=2) if self.train_answer_visible else self.train_answer_label.pack_forget()

    def _train_load(self):
        self.train_type = self.train_mode_var.get()
        portion_id = get_current_portion_id()
        self.train_items = get_weekly_sentences(portion_id) if self.train_type == "sentences" else get_weekly_words(portion_id)
        self.train_index = 0
        self.train_first_attempt = [None] * len(self.train_items) if self.train_items else []
        self.train_peeked = [False] * len(self.train_items) if self.train_items else []
        self._train_show_current()

    def _train_restart_round(self):
        self.train_index = 0
        self.train_first_attempt = [None] * len(self.train_items) if self.train_items else []
        self.train_peeked = [False] * len(self.train_items) if self.train_items else []
        self._train_show_current()

    def _train_show_current(self):
        self.train_answer_visible = False
        self.train_answer_label.config(text="")
        self.train_show_btn.config(text="Посмотреть ответ")
        self.train_answer_label.pack_forget()
        self.train_result.config(text="")
        self._hide_record_error_btn()

        if not self.train_items or self.train_index >= len(self.train_items):
            # Успех только по пунктам без «посмотреть ответ»
            total = sum(1 for i in range(len(self.train_first_attempt)) if not self.train_peeked[i] and self.train_first_attempt[i] is not None)
            correct = sum(1 for i in range(len(self.train_first_attempt)) if not self.train_peeked[i] and self.train_first_attempt[i] is True)
            pct = (100 * correct / total) if total else 0
            self.train_ru_label.config(text="Круг закончен.")
            self.train_en_entry.delete(0, tk.END)
            self.train_progress_label.config(
                text=f"Верно (без подсказки): {correct}/{total} ({pct:.0f}%). Процент только для информации."
            )
            return

        item = self.train_items[self.train_index]
        self.train_ru_label.config(text=item.get("translation", ""))
        self.train_en_entry.delete(0, tk.END)
        self.train_start_time = time.time()
        self.train_progress_label.config(text=f"{self.train_index + 1} / {len(self.train_items)}")

    def _hide_record_error_btn(self):
        self.train_error_btn.pack_forget()
        self.train_error_btn_visible = False

    def _show_record_error_btn(self):
        if not self.train_error_btn_visible:
            self.train_error_btn.pack(anchor=tk.W, pady=2)
            self.train_error_btn_visible = True

    def _train_record_error(self):
        if not self.train_items or self.train_index >= len(self.train_items):
            return
        item = self.train_items[self.train_index]
        en_ref = item.get("english", "")
        answer = self.train_en_entry.get().strip()
        if not en_ref:
            return
        add_manual_translation_error(en_ref, answer or "(пусто)")
        messagebox.showinfo("", "Ошибка записана в БД.")
        self._hide_record_error_btn()

    def _train_check(self):
        if not self.train_items or self.train_index >= len(self.train_items):
            return
        item = self.train_items[self.train_index]
        en_ref = item.get("english", "")
        answer = self.train_en_entry.get().strip()
        if not answer:
            return
        time_taken = time.time() - getattr(self, "train_start_time", time.time())
        char_count = len(answer)
        portion_id = get_current_portion_id()
        result = check_translation(en_ref, answer)

        if self.train_first_attempt[self.train_index] is None:
            self.train_first_attempt[self.train_index] = result.ok
        add_typing_stat(portion_id, self.train_type, en_ref, time_taken, char_count, result.ok)

        if result.ok:
            self.train_result.config(font=("TkDefaultFont", 10), text="✓ Верно.")
            self._hide_record_error_btn()
            self.after(300, self._train_next)
        else:
            txt = format_error_display(en_ref, answer, result)
            if result.hint:
                txt += "\n" + result.hint
            self.train_result.config(font=("Courier", 10), text=txt)
            add_translation_error(en_ref, answer, result.error_type or "grammar", result.problem_place)
            self._show_record_error_btn()

    def _train_next(self):
        if self.train_index < len(self.train_items):
            self.train_index += 1
        self._train_show_current()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
