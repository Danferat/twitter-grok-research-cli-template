# Memory

## 2026-07-03 (2)

- Обнаружено и подтверждено: Claude Code читает только `CLAUDE.md`, не `AGENTS.md`/`CODEX.md`; Codex CLI читает только `AGENTS.md`, не `CODEX.md`. `CODEX.md` не подхватывался автоматически ни одним из инструментов - весь его свод правил был "мёртв" для любого агента, который его явно не открыл.
- Свод правил консолидирован в один файл: полное содержимое `CODEX.md` (Provider Selection, Grok/Surf/SocialData/Nansen workflows, Query Rules, Answer Rules) перенесено в `AGENTS.md`, дополнено секцией `Scope Control` из старой версии `AGENTS.md`. `CODEX.md` удалён - двух копий одного свода больше нет, риска расхождения тоже.
- Добавлен `CLAUDE.md` - короткий файл, который Claude Code подхватывает автоматически и который одной строкой отправляет читать `AGENTS.md` целиком. Обнаружено, что даже сторонний Surf-skill (`.agents/skills/surf/SKILL.md`) уже ожидает именно такую пару файлов: он сам ищет `AGENTS.md`, с fallback на `CLAUDE.md`, чтобы дописать туда свой routing-блок при `surf install`.
- README.md и `docs/agent-integration-guide.md` обновлены: все ссылки на `CODEX.md` заменены на `AGENTS.md`, добавлено описание роли `CLAUDE.md`.
- Изменения затронули только шаблон (`twitter-grok-research-cli-template`), уже опубликованный на GitHub; в исходном рабочем проекте `CODEX.md`/`AGENTS.md` не трогались.

## 2026-07-03

- Проект создан как безопасный публичный шаблон на основе `twitter-grok-research-cli`: скопирован весь рабочий код (`twitter_research/`, `tests/`, `.agents/skills/surf`, `skills-lock.json`, `AGENTS.md`, `CODEX.md`, `docs/agent-integration-guide.md`, `scripts/install_for_agent.sh`, `requirements.txt`, `.env.example`).
- Не скопированы личные данные исходного проекта: `.env` с реальными ключами, `data/runs/*.json`, `outputs/`, заполненные `content_research/`, `service_research/`, `Memory.md`, `CHANGELOG.md`, `docs/superpowers/`, `.claude/settings.local.json`.
- Найден и исправлен захардкоженный личный абсолютный путь в `twitter_research/storage.py`: `DEFAULT_RUNS_DIR` указывал на конкретную папку автора вне репозитория; заменён на относительный `data/runs`, как описано в README и install-скрипте. В исходном проекте это не трогалось - фикс только в шаблоне.
- `content_research_index.md` и `service_research_index.md` заменены на пустые таблицы (только заголовки) без личных записей.
- README.md переписан: добавлен `## Technology Map` в начало, обобщены упоминания "Codex" на "агент" там, где логика не специфична для одного инструмента, URL клонирования сделан плейсхолдером.
- Проверено: `bash scripts/install_for_agent.sh` внутри шаблона создаёт `.venv`, `.env` из `.env.example` с плейсхолдерами (без реальных ключей), проходит все 70 unit-тестов, `python -m twitter_research --help` работает.
- Секреты проверены grep по всему дереву шаблона (кроме `.venv`) на паттерны реальных ключей xAI/Surf/Nansen/X - не найдены.
