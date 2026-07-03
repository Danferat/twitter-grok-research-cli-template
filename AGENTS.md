# AGENTS.md

Universal rules for any AI agent with shell/tool access using this project's research CLI. This file is the single source of truth for scope, provider selection, workflows, and answer format. Read it fully before handling any Twitter/X, Grok, Surf, SocialData, or Nansen research request.

## Scope Control

- Use only the tools, APIs, providers, and data sources explicitly requested by the operator.
- Search only for the information the operator explicitly asked for.
- Do not expand the task to adjacent sources, extra verification, alternative APIs, web search, on-chain tools, dashboards, or other providers without operator approval.
- If the requested tool is missing, unavailable, incomplete, or likely insufficient, report that limitation first and ask before using any substitute.
- Keep results scoped to the requested question. Do not add extra investigations just because they may be useful.

This project has four separate research paths - Grok/xAI, Surf, SocialData, and Nansen. Keep them isolated: never call one provider while another was selected, unless the user explicitly asks to combine sources.

## Provider Selection

- Generic Twitter/X search: if the user asks to search Twitter/X and does not name a provider, ask them to choose `GROK`, `SURF`, or `SOCIALDATA` before running anything.
- Grok-only: use when the user says "через Grok", "Grok", or chooses `GROK`. Run only xAI/Grok API with `x_search`. Do not call X/Twitter API. Do not use Grok web search.
- Surf X/Twitter posts: use when the user says "через Surf" or chooses `SURF` for Twitter/X posts. Run `surf-search`. Do not call Grok. Do not call SocialData.
- Surf broad crypto research: use when the user asks for crypto market, wallet, token, project, social analytics, onchain, news, web/search, fund, exchange, Hyperliquid, or prediction-market data through Surf/AskSurfAI. Prefer `surf-ask` for open-ended natural-language answers, `surf-call` for local Surf CLI operations, and `surf-api-call` for direct Surf Data API endpoints when `SURF_API_KEY` is configured.
- SocialData X/Twitter search: use when the user says "через SocialData" or chooses `SOCIALDATA`. Run `socialdata-search`. Do not call Grok. Do not call Surf.
- Nansen on-chain research: use when the user says "через Nansen", "Nansen", "ончейн", "on-chain", or asks for wallet/token/smart-money data that should come from Nansen. For chat questions, run `nansen-ask` yourself and answer from its output. Use `nansen-agent`, `nansen-token-screener`, or `nansen-call` only for manual endpoint work. Do not call Grok, Surf, or SocialData.
- There is no direct X/Twitter API v2 access in this project. If the user explicitly asks for "Twitter API" or direct API access, tell them it does not exist here and ask whether they want `GROK`, `SURF`, or `SOCIALDATA` instead.

When the provider is missing, ask exactly this and wait for the user's choice:

```text
Какого провайдера поиска использовать?

1. GROK
2. SURF
3. SOCIALDATA
```

After the user replies with a number or provider name, run only that provider's workflow.

## Grok-Only Workflow

Run:

```bash
python3 -m twitter_research grok-search "USER QUESTION"
```

Grok always runs on a single fixed model, `grok-4.3`. There is no `--model` flag and no model-selection prompt; never ask the user which model to use.

Read the saved JSON from `data/runs/` if needed. Answer from Grok output and label it as Grok/xAI X/Twitter search output.

The Grok workflow is restricted to X/Twitter search inside Grok:

- The xAI request must include only the `x_search` tool.
- Do not include or use `web_search`.
- Do not run separate internet browsing to supplement or verify Grok-only answers unless the user explicitly asks for web verification.
- If xAI returns usage showing `web_search_calls > 0`, reject the result.
- If xAI returns usage showing `x_search_calls == 0`, reject the result because Grok did not search X/Twitter.

## Surf X/Twitter Posts Workflow

Run:

```bash
python3 -m twitter_research surf-search "QUERY" --limit 20
```

Use X/Twitter advanced-search operators supported by Surf when useful:

- `from:handle`
- `@handle`
- `#hashtag`
- `-word`
- `min_faves:N`
- `min_retweets:N`
- `min_replies:N`
- `since:YYYY-MM-DD`
- `until:YYYY-MM-DD`
- double-quoted exact phrases

Read the saved JSON from `data/runs/` if needed. Answer from the Surf results and label them as Surf X/Twitter post search output, not verified fact.

Surf-search boundaries:

- Do not call Grok.
- Do not call direct X/Twitter API.
- If Surf returns no posts, say that Surf found no posts for that query and suggest narrowing or changing the query operators.

## Surf Broad Crypto Research Workflow

Use Surf for live crypto data when the question is not specifically a Twitter/X post search: market data, wallet balances/transfers, token holders/transfers/unlocks, project profiles, DeFi metrics, social analytics, news, web/search, fund data, exchange data, Hyperliquid, onchain SQL, and prediction markets.

Discovery:

```bash
python3 -m twitter_research surf-list --category market
```

Local Surf CLI operation:

```bash
python3 -m twitter_research surf-call market-price --param symbol=BTC --param time-range=24h
python3 -m twitter_research surf-call wallet-detail --param address=0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 --param chain=ethereum
python3 -m twitter_research surf-call onchain-sql --body-json '{"sql":"SELECT 1"}'
```

Direct Surf Data API endpoint:

```bash
python3 -m twitter_research surf-api-call market/price --param symbol=BTC
python3 -m twitter_research surf-api-call onchain/sql --method POST --body-json '{"sql":"SELECT 1"}'
```

Surf Chat API Research 2.0 for open-ended questions:

```bash
python3 -m twitter_research surf-ask "What happened to BTC today?"
python3 -m twitter_research surf-ask "How has BTC ETF flow shifted this week, and what is driving it?" --effort high
```

`surf-ask` is the agent-facing Surf workflow, usable from any agent with shell access. It wraps the user's plain question into a Russian Surf research prompt, sends that prompt to Surf Chat API Research 2.0, saves both the original question and the sent prompt, and prints a readable answer. It chooses `medium` effort automatically for straightforward questions and `high` for deep research, comparison, explanation, weekly/monthly, investigation, or due-diligence wording. Override `--effort` only when needed.

Surf config:

- `surf-api-call` and `surf-ask` require `SURF_API_KEY` in `.env` or the shell environment.
- `surf-call` uses the local Surf CLI and can use `surf auth` configuration.
- Surf Data API base URL is `https://api.asksurf.ai/gateway/v1`.
- Surf Chat API Research 2.0 uses `POST /responses` with `model: surf-2.0` and nested `reasoning.effort`.
- For exact Surf CLI operation names and parameters, consult `.agents/skills/surf/SKILL.md` or run `surf-list`/`surf --help`.

Surf broad-research boundaries:

- Do not call Grok, SocialData, Nansen, or direct X/Twitter API unless the user explicitly asks to combine sources.
- For operation parameters, run `surf-list` or the Surf CLI help when unsure; flag names vary by endpoint.
- For onchain SQL, keep queries read-only and include required partition filters for large tables.
- Label results as Surf/AskSurfAI output, not independently verified fact.
- In chat, do not ask the user to run commands manually. Run `surf-ask` yourself for simple Surf questions, read the output, then answer in a concise human format.

## SocialData X/Twitter Search Workflow

Run:

```bash
python3 -m twitter_research socialdata-search "QUERY" --type Latest
```

SocialData config:

- Requires `SOCIALDATA_API_KEY` in `.env` or the shell environment.
- Endpoint: `GET https://api.socialdata.tools/twitter/search?query=...&type=Latest`.
- Auth: `Authorization: Bearer SOCIALDATA_API_KEY`.
- `--type` can be `Latest` or `Top`.

Use Twitter search operators inside the query string, not as separate flags:

- `from:USERNAME`
- `from:USERNAME -filter:replies`
- `@USERNAME -from:USERNAME`
- `since_time:TIMESTAMP`
- `until_time:TIMESTAMP`
- `since_id:TWEET_ID`
- `max_id:TWEET_ID`
- `conversation_id:TWEET_ID`

Read the saved JSON from `data/runs/` if needed. Answer from the SocialData results and label them as SocialData X/Twitter search output, not verified fact.

SocialData-search boundaries:

- Do not call Grok.
- Do not call Surf.
- Do not call direct X/Twitter API.
- If SocialData returns an insufficient balance or limited access error, report the provider limitation plainly.

## Nansen On-Chain Research Workflow

Use Nansen only for on-chain data, token screening, wallet/entity research, smart-money flows, and natural-language questions that should be answered from Nansen API data.

Config:

- Requires `NANSEN_API_KEY` in `.env` or the shell environment.
- Base URL: `https://api.nansen.ai/api/v1`.
- Auth: `apikey: NANSEN_API_KEY`.
- Nansen Agent endpoints stream SSE from `/agent/fast` or `/agent/expert`.

Chat-native natural-language question:

```bash
python3 -m twitter_research nansen-ask "Which tokens are smart money accumulating on Ethereum this week?"
```

`nansen-ask` wraps the user's question into a Nansen Agent prompt that requests a readable Russian answer with: short conclusion, data observations, why it matters, data limits, and next checks. It chooses `fast` automatically for simple questions and `expert` for deep/research/comparison/time-window wording. Override only when needed:

```bash
python3 -m twitter_research nansen-ask "Explain the on-chain story behind SOL inflows this week" --mode expert
```

Token screener:

```bash
python3 -m twitter_research nansen-token-screener --chains ethereum,solana,base --timeframe 24h --per-page 10 --only-smart-money
```

Any documented Nansen POST endpoint:

```bash
python3 -m twitter_research nansen-call smart-money/netflow --body-json '{"chains":["ethereum"],"pagination":{"page":1,"per_page":10}}'
```

Nansen boundaries:

- Do not call Grok, Surf, SocialData, or direct X/Twitter API.
- In chat, do not ask the user to run commands manually. Run `nansen-ask` yourself, read the output, then answer in a concise human format.
- If `NANSEN_API_KEY` is missing, tell the user to add it to `.env`; do not ask them to paste the key into chat.
- If Nansen returns 401/403/402/429, report the provider limitation plainly.
- Label answers as Nansen on-chain data output, not Twitter/X chatter.

## Ask Provider Selector

`ask` is a provider selector for Grok/Surf/SocialData:

```bash
python3 -m twitter_research ask "USER QUESTION"
python3 -m twitter_research ask "USER QUESTION" --provider surf
python3 -m twitter_research ask "USER QUESTION" --provider socialdata
```

`plan-query` remains available because it does not call any API.

## Terminal Fallback

If the user wants terminal Twitter/X search, use `ask` when provider selection is desired. Use `surf-search`, `socialdata-search`, or `grok-search` when the provider is already known. If the user wants broad crypto research through Surf, use `surf-ask`, `surf-call`, or `surf-api-call`.

## Content Research Duplicate Filter

For educational crypto content automation, check each accepted candidate before adding it to the final output:

```bash
python3 -m twitter_research content-filter --summary "CANDIDATE MATERIAL SUMMARY"
```

The command compares the candidate summary with existing summaries in `content_research_index.md`.

- If output contains `Status: irrelevant_duplicate`, do not include the material in the final output.
- If output contains `Status: relevant_new`, the material may be added if it passes the editorial and safety filters.
- The default duplicate threshold is more than `80%` semantic/content similarity.
- Use this summary filter in addition to URL, topic, and file duplicate checks.

## Query Rules

- For token questions, include both ticker and `token` when useful: `PUMP token`.
- For decline questions, include terms like `dump`, `down`, `bearish`, `selloff`, `unlock`, `scam`, `volume`, `whale`.
- For growth questions, include terms like `pump`, `rally`, `bullish`, `listing`, `launch`, `volume`, `whale`.
- For mixed questions, include both growth and decline terms.
- For "today", use `--days 1`.
- For "week" or "неделя", use `--days 7`.
- For "month" or "месяц", use `--days 30`.
- If X API rejects full-archive search for `--days 30`, retry with `--days 7 --mode recent` and clearly tell the user that the API plan limited the search window.

## Answer Rules

- Do not present tweet chatter as verified fact.
- Summarize repeated narratives and cite local tweet numbers from `show latest`.
- Highlight uncertainty when the result count is low.
- If the API returns an error, report the API limitation plainly and suggest the narrower recent-search fallback.
- If using Grok output, label it as Grok/xAI X/Twitter search output, not verified fact.
- If using Surf output, label it as Surf X/Twitter post search output, not verified fact.
- If using broad Surf output, label it as Surf/AskSurfAI output, not verified fact.
- If using SocialData output, label it as SocialData X/Twitter search output, not verified fact.
- If using Nansen output, label it as Nansen on-chain data output and keep the final answer readable: short conclusion, key data points, limits, and what to check next.
