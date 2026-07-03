# Memory

## 2026-07-03

- Проект создан как безопасный публичный шаблон на основе `twitter-grok-research-cli`: скопирован весь рабочий код (`twitter_research/`, `tests/`, `.agents/skills/surf`, `skills-lock.json`, `AGENTS.md`, `CODEX.md`, `docs/agent-integration-guide.md`, `scripts/install_for_agent.sh`, `requirements.txt`, `.env.example`).
- Не скопированы личные данные исходного проекта: `.env` с реальными ключами, `data/runs/*.json`, `outputs/`, заполненные `content_research/`, `service_research/`, `Memory.md`, `CHANGELOG.md`, `docs/superpowers/`, `.claude/settings.local.json`.
- Найден и исправлен захардкоженный личный абсолютный путь в `twitter_research/storage.py`: `DEFAULT_RUNS_DIR` указывал на конкретную папку автора вне репозитория; заменён на относительный `data/runs`, как описано в README и install-скрипте. В исходном проекте это не трогалось - фикс только в шаблоне.
- `content_research_index.md` и `service_research_index.md` заменены на пустые таблицы (только заголовки) без личных записей.
- README.md переписан: добавлен `## Technology Map` в начало, обобщены упоминания "Codex" на "агент" там, где логика не специфична для одного инструмента, URL клонирования сделан плейсхолдером.
- Проверено: `bash scripts/install_for_agent.sh` внутри шаблона создаёт `.venv`, `.env` из `.env.example` с плейсхолдерами (без реальных ключей), проходит все 70 unit-тестов, `python -m twitter_research --help` работает.
- Секреты проверены grep по всему дереву шаблона (кроме `.venv`) на паттерны реальных ключей xAI/Surf/Nansen/X - не найдены.
