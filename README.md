# Twitter/Grok/Surf/Nansen Research CLI (Template)

## Technology Map

- Purpose: локальный CLI-фреймворк для подключения к любому AI-агенту с доступом к shell/bash-инструменту, который умеет искать в X/Twitter через выбираемый провайдер (Grok/xAI `x_search`, Surf, SocialData), вести широкий crypto research через AskSurfAI/Surf Data и Chat API, и делать ончейн-ресёрч через Nansen API. Прямой доступ к X/Twitter API v2 отключён по умолчанию.
- Languages: Python 3
- Frameworks: нет (стандартная библиотека + `argparse`-CLI)
- Databases: нет; результаты сохраняются как JSON-файлы в `data/runs/` и Markdown-индексы для контент-ресёрча
- Models/providers: Grok через xAI API (`x_search`, фиксированная модель `grok-4.3`); Surf CLI и Surf Data/Chat API (`surf-2.0`); SocialData X/Twitter search API; Nansen Agent (fast/expert) и Nansen POST endpoints
- Bots/usernames: нет, настраиваются пользователем через свои ключи
- Services: `api.x.ai` (xAI/Grok), `api.asksurf.ai` (Surf), `api.socialdata.tools` (SocialData), `api.nansen.ai` (Nansen)
- Run: `python3 -m twitter_research --help`
- Test: `python3 -m unittest discover -s tests -v`

## Что это

Этот репозиторий - безопасный шаблон без чужих API-ключей, без личных данных и без истории конкретного инстанса. Каждый пользователь клонирует его, вставляет свои ключи и подключает к своему AI-агенту с доступом к shell/bash-инструменту.

Проект помогает задавать агенту вопросы вроде: "поищи в Twitter, что сейчас пишут про PUMP", "спроси Surf, что произошло с BTC сегодня" или "спроси Nansen, какие токены накапливает smart money". Если X/Twitter-провайдер не указан, агент сначала должен спросить, чем искать: `GROK / SURF / SOCIALDATA`. Grok-поиск использует xAI API и запрещает web search. Surf-поиск использует локальный Surf CLI и endpoint `search-social-posts`; расширенный Surf-режим умеет запускать любую локальную Surf operation через `surf-call`, прямые Surf Data API endpoints через `surf-api-call` и Surf Chat API Research 2.0 через `surf-ask`. SocialData-поиск использует `GET https://api.socialdata.tools/twitter/search`. Nansen-поиск использует `POST https://api.nansen.ai/api/v1/...` с ключом в заголовке `apikey` и сохраняет результаты в те же JSON-запуски. Прямого доступа к X/Twitter API v2 в проекте нет.

## Agent Tooling

- `AGENTS.md` - единственный и полный свод правил для агента: scope control, выбор провайдера, workflow по каждому провайдеру, форматы ответов. Других файлов с правилами в проекте нет.
- Surf установлен как проектный agent skill в `.agents/skills/surf` и зафиксирован в `skills-lock.json`.
- Расширенные Surf-команды: `surf-list` показывает каталог операций, `surf-call` запускает любую Surf CLI operation, `surf-api-call` вызывает Surf Data API напрямую с `SURF_API_KEY`, `surf-ask` обращается к Surf Chat API Research 2.0.
- Если планируете использовать `surf-search`/`surf-call` через локальный Surf CLI (а не только через `SURF_API_KEY`), установите Surf CLI отдельно и запустите `surf install && surf sync`.

## Setup

```bash
git clone https://github.com/Danferat/twitter-grok-research-cli-template.git && cd twitter-grok-research-cli-template && bash scripts/install_for_agent.sh
```

Скрипт создаст локальное окружение `.venv`, подготовит `.env` из `.env.example`, прогонит тесты и покажет, куда вставить ключи.

Если репозиторий уже скачан, запустите из корня проекта:

```bash
bash scripts/install_for_agent.sh
```

Вручную:

```bash
cp .env.example .env
```

Вставьте ключи для нужных режимов:

```text
XAI_API_KEY=ваш_xai_ключ
SOCIALDATA_API_KEY=ваш_socialdata_ключ
NANSEN_API_KEY=ваш_nansen_ключ
SURF_API_KEY=ваш_surf_ключ
```

Ни один режим не обязателен целиком - настраивайте только те провайдеры, которыми планируете пользоваться. `XAI_API_KEY` нужен для Grok-only поиска. `SOCIALDATA_API_KEY` нужен для SocialData-поиска. `NANSEN_API_KEY` нужен для ончейн-ресёрча через Nansen. `SURF_API_KEY` нужен для прямых Surf API команд `surf-api-call` и `surf-ask`; локальный `surf-call` может использовать авторизацию, настроенную через `surf auth`.

`.env` уже в `.gitignore` - не коммитьте его и не публикуйте нигде. Для Grok-only поиска используется единственная модель `grok-4.3`, выбор модели отсутствует.

`install_for_agent.sh` дополнительно включает локальный git pre-commit hook (`.githooks/pre-commit`), который блокирует коммит, если в staged-файлах случайно оказался `.env` или строка, похожая на реальный API-ключ. Хук работает только локально и ничего никуда не отправляет - это защита от случайного `git add .`.

## Подключение к агенту

Весь свод правил лежит в одном файле [AGENTS.md](AGENTS.md) в корне проекта: scope control, выбор провайдера, workflow по каждому провайдеру, query/answer rules. Положите проект в папку, укажите на неё агента - он читает `AGENTS.md` из корня и следует ему. Других файлов с правилами в проекте нет.

Если пользователь просит искать в Twitter/X и не называет провайдера, агент сначала спрашивает:

```text
Какого провайдера поиска использовать?

1. GROK
2. SURF
3. SOCIALDATA
```

После выбора агент запускает только соответствующий pipeline и не смешивает провайдеров без явного запроса пользователя.

`<PROJECT_ROOT>` в тексте `AGENTS.md` и доков - путь к папке, куда установлен или склонирован этот репозиторий. Агент должен иметь разрешение на локальный shell/tool use. Если shell недоступен, используйте CLI вручную и передавайте агенту сохранённый JSON из `data/runs/` для анализа.

Подробный гайд по механике подключения - в [docs/agent-integration-guide.md](docs/agent-integration-guide.md).

## Terminal Usage

```bash
python3 -m twitter_research grok-search "что сейчас пишут про PUMP token?"
python3 -m twitter_research surf-search "PUMP token since:2026-06-01" --limit 20
python3 -m twitter_research surf-list --category market
python3 -m twitter_research surf-call market-price --param symbol=BTC --param time-range=24h
python3 -m twitter_research surf-api-call market/price --param symbol=BTC --param time_range=24h
python3 -m twitter_research surf-ask "What happened to BTC today?"
python3 -m twitter_research socialdata-search "PUMP token since_time:1770000000" --type Latest
python3 -m twitter_research nansen-ask "Which tokens are smart money accumulating on Ethereum this week?"
python3 -m twitter_research nansen-token-screener --chains ethereum,solana,base --timeframe 24h --per-page 10 --only-smart-money
python3 -m twitter_research nansen-call smart-money/netflow --body-json '{"chains":["ethereum","solana"],"pagination":{"page":1,"per_page":10}}'
python3 -m twitter_research ask "что пишут про PUMP token?" --provider socialdata
python3 -m twitter_research plan-query "почему PUMP токен падает последний месяц?"
python3 -m twitter_research show latest
python3 -m twitter_research content-filter --summary "Краткое содержание найденного материала"
python3 -m twitter_research content-filter --summary "Краткое содержание найденного сервиса" --index-file service_research_index.md
```

## Content Research Automation (опционально)

`content_research/` и `content_research_index.md`, `service_research/` и `service_research_index.md` - опциональная база для дедупликации найденных материалов через `content-filter`. Папки пустые (только `.gitkeep`) - заполняются по мере использования, ничего личного внутри нет.

## README MAP

- `twitter_research/config.py` - чтение `.env`: `XAI_API_KEY`, `SOCIALDATA_API_KEY`, `NANSEN_API_KEY`, `SURF_API_KEY`
- `twitter_research/query_planner.py` - трансформация обычного вопроса в предложенный X query и шаблон `ask ... --provider PROVIDER`
- `twitter_research/grok_client.py` - клиент xAI API для Grok-only поиска только через `x_search`, фиксированная модель `grok-4.3`
- `twitter_research/surf_client.py` - клиент-обёртка над локальным Surf CLI и прямой Surf Data/Chat API клиент
- `twitter_research/socialdata_client.py` - клиент SocialData API для `GET /twitter/search`
- `twitter_research/nansen_client.py` - клиент Nansen API для POST JSON endpoints и SSE-потока Nansen Agent
- `twitter_research/content_filter.py` - фильтр похожих summary для базы контент-ресёрча
- `twitter_research/storage.py` - сохранение и чтение JSON-запусков
- `twitter_research/cli.py` - все CLI-команды
- `twitter_research/__main__.py` - запуск через `python3 -m twitter_research`
- `scripts/install_for_agent.sh` - one-command установка: создаёт `.venv`, `.env`, запускает тесты и показывает, куда вставить ключи
- `tests/` - unit-тесты
- `data/runs/` - локальные результаты поиска (пусто, только `.gitkeep`)
- `content_research_index.md`, `content_research/` - опциональная база контент-ресёрча (пусто)
- `service_research_index.md`, `service_research/` - опциональная база по сервисам и инструментам (пусто)
- `docs/agent-integration-guide.md` - гайд по механике подключения проекта к агенту
- `AGENTS.md` - единственный и полный свод правил для агента: scope control, выбор провайдера, workflow, query/answer rules
- `.agents/skills/surf/SKILL.md` - проектный Surf skill для агентского crypto/web research через Surf CLI
- `skills-lock.json` - lock-файл установленного Surf skill
- `.env.example` - пример настройки xAI, SocialData, Nansen и Surf API ключей (без реальных значений)

## Run/Test Commands

```bash
python3 -m unittest discover -s tests -v
python3 -m twitter_research --help
```
