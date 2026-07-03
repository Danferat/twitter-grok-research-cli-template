# Agent Integration Guide

Как физически подключить этот проект к Codex, Claude или другому локальному агенту. Все правила по выбору провайдера, границам режимов и формату ответов описаны один раз в [CODEX.md](../CODEX.md) - этот гайд их не повторяет, а объясняет только механику подключения и проверку результата.

## 1. Что должен уметь агент

Агенту нужен доступ к локальной папке проекта и возможность запускать команды в терминале из корня проекта:

```bash
cd "<PROJECT_ROOT>"
python3 -m twitter_research --help
```

`<PROJECT_ROOT>` - путь к папке, куда установлен или склонирован этот репозиторий.

Секреты хранятся только в локальном `.env`, который не нужно коммитить в GitHub:

```text
XAI_API_KEY=...
SOCIALDATA_API_KEY=...
NANSEN_API_KEY=...
SURF_API_KEY=...
```

## 2. Codex

Codex CLI автоматически читает `AGENTS.md` из корня репозитория. Детальные provider-workflow правила (какую команду запускать для GROK/SURF/SOCIALDATA/Nansen, что запрещено смешивать) лежат отдельно в `CODEX.md` - это не стандартное имя файла, поэтому его нужно явно подключить через custom instructions:

```text
When the user asks to search through Twitter/X, Grok, Surf, SocialData, or Nansen
on-chain data, use the local project at <PROJECT_ROOT> and follow the rules in
CODEX.md before running any command.
```

Если хочется оформить это как отдельный Codex skill, создайте короткий `SKILL.md`, который содержит этот блок и ссылку на `CODEX.md`.

## 3. Claude

Claude Code читает только `CLAUDE.md` и не подхватывает `AGENTS.md`/`CODEX.md` автоматически. Вставьте в Claude Project Instructions или system prompt блок ниже - он самодостаточен, чтобы работать даже без файлового доступа к `CODEX.md`:

```text
You have access to a local Twitter/Grok/Surf/Nansen research CLI project at:
<PROJECT_ROOT>

Use it whenever the user explicitly asks to search through Twitter/X, Grok, Surf,
SocialData, or Nansen on-chain data.

For generic Twitter/X search requests, ask the user to choose one provider first:
GROK, SURF, or SOCIALDATA.

For Grok requests, run:
python3 -m twitter_research grok-search "USER QUESTION"
(model is always grok-4.3, no model flag)

For Surf X/Twitter post search, run:
python3 -m twitter_research surf-search "QUERY" --limit LIMIT

For broad Surf crypto research, run:
python3 -m twitter_research surf-ask "USER QUESTION"

For SocialData X/Twitter search, run:
python3 -m twitter_research socialdata-search "QUERY" --type Latest

For Nansen on-chain research, run:
python3 -m twitter_research nansen-ask "USER QUESTION"

Keep modes isolated: never mix providers unless the user explicitly asks to
combine sources. Grok-only never uses web search unless explicitly requested.
```

Claude должен иметь разрешение на локальный shell/tool use. Если shell недоступен, используйте этот проект вручную через терминал и отдавайте Claude сохранённый JSON из `data/runs/` для анализа.

## 4. Быстрый тест интеграции

Проверка выбора провайдера:

```text
найди в Twitter, почему PUMP token падает за последнюю неделю
```

Ожидаемое поведение агента: сначала спросить `GROK / SURF / SOCIALDATA`, затем запустить выбранный pipeline.

Проверка Grok-only:

```text
найди через Grok, что сейчас пишут про PUMP token
```

Ожидаемое поведение агента: сразу запустить `grok-search` через модель `grok-4.3` без вопроса о модели, не использовать обычный web search.

Проверка Nansen:

```text
спроси через Nansen, какие токены smart money покупает на Ethereum
```

Ожидаемое поведение агента: запустить `nansen-ask`, использовать `NANSEN_API_KEY`, не обращаться к Twitter/X, Grok, Surf или SocialData, затем вернуть оформленный ответ в чате.

Проверка широкого Surf research:

```text
спроси через Surf, что произошло с BTC сегодня
```

Ожидаемое поведение агента: запустить `surf-ask` при наличии `SURF_API_KEY`; команда сама упакует вопрос в Surf research prompt, выберет effort и вернёт читабельный ответ. Для точных структурированных данных сначала посмотреть операции через `surf-list`, затем использовать `surf-call` или `surf-api-call`.

## 5. Частые ошибки

- Агент сразу запускает Grok на общий Twitter/X-запрос: нужно усилить правило "provider selection first" из `CODEX.md`.
- Агент делает web search после Grok: разрешать это только при явной просьбе пользователя.
- Агент отвечает на ончейн-вопрос через Twitter/X chatter: для Nansen/он-чейн запросов из чата использовать `nansen-ask`, а `nansen-call` оставлять для конкретных endpoints.
- Агент отвечает на широкий Surf-запрос через `surf-search`: для market/wallet/token/project/onchain/news/search/prediction использовать `surf-ask`, `surf-call` или `surf-api-call`, а `surf-search` оставлять для X/Twitter posts.
- Агент просит пользователя запускать команды вручную: в Codex/Claude с shell-доступом агент должен запускать CLI сам.
- В GitHub попал `.env`: удалить из истории репозитория и оставить только `.env.example`.
