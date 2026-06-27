# English System App

Приложение для изучения слов и предложений. Данные добавляются только через **import-json**; ИИ в этом приложении не используется.

## Запуск

```bash
python run.py app
python run.py                  # меню команд
```

## Команды

| Команда | Описание |
|---------|----------|
| `app` | Открыть десктопное приложение (таймер + тренажёр) |
| `import-json` | Добавить данные из JSON в текущую порцию: `python run.py import-json path/to/file.json` |
| `list-portions` | Показать список порций (id, предложений, слов), текущая отмечена * |
| `set-portion` | Переключиться на порцию: `python run.py set-portion <id>` |
| `next-portion` | Создать новую порцию и сделать её текущей |
| `generate-audio` | Сгенерировать аудио (Google Cloud TTS) + HTML для телефона по текущей порции |

## Данные

- **SQLite:** `data/english_system.db`
- **Порции:** данные разбиты на порции (пакеты). Текущая порция выбирается в приложении или через `set-portion` / `next-portion`.
- **Импорт:** только из JSON-файла. Формат: `{"sentences": [{"english": "...", "translation": "..."}, ...], "words": [...]}` (или ключи `en`/`ru`).

## Генерация аудио (Google Cloud TTS)

Аудио генерируется через **Google Cloud Text-to-Speech** (американский английский, en-US-Wavenet-D), к каждой записи добавляется 5 сек тишины. Требуется:

- Учётная запись Google Cloud, включённый API **Cloud Text-to-Speech**
- `pip install google-cloud-texttospeech`
- Переменная окружения `GOOGLE_APPLICATION_CREDENTIALS` с путём к JSON-ключу сервисного аккаунта

HTML и mp3: `data/audio/sentences_DD_MM_YY/` или `words_DD_MM_YY/` — подпапка `audio/` с mp3 и `review_*_DD_MM_YY_ru.html`.

## Звуки таймера

При старте таймера воспроизводится `data/sounds/start.wav`, по окончании — `data/sounds/end.wav`. Если файлов нет или воспроизведение не удаётся — системный beep. Можно положить свои WAV-файлы в `data/sounds/`.

## Проблемы

- **ModuleNotFoundError: tkinter:** на Linux: `sudo apt install python3-tk`.
