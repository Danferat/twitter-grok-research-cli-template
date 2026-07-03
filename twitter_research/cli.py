from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, load_config
from .content_filter import (
    DEFAULT_CONTENT_INDEX,
    DEFAULT_SIMILARITY_THRESHOLD,
    find_similar_summary,
    load_content_index,
)
from .grok_client import GROK_MODEL, GrokApiError, GrokClient
from .nansen_client import NansenClient, NansenError
from .query_planner import plan_query
from .socialdata_client import SocialDataClient, SocialDataError
from .storage import DEFAULT_RUNS_DIR, latest_run_path, load_run, save_run
from .surf_client import SurfApiClient, SurfClient, SurfError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="twitter-research",
        description="Run Twitter/X research through Grok, Surf, or SocialData, plus on-chain research through Nansen.",
    )
    parser.add_argument("--env-file", default=".env", help="Path to .env with API keys.")
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR), help="Directory for saved JSON runs.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    grok_search = subparsers.add_parser(
        "grok-search",
        help="Grok-only search through xAI API tools. X/Twitter API is not used.",
    )
    grok_search.add_argument("question", help="Natural-language question for Grok search.")
    grok_search.add_argument(
        "--max-search-results",
        type=int,
        default=20,
        help="Maximum sources Grok may consider.",
    )

    surf_search = subparsers.add_parser(
        "surf-search",
        help="Search X/Twitter posts through Surf CLI. Direct X/Twitter API and Grok are not used.",
    )
    surf_search.add_argument("query", help="Surf social post query, including supported X operators.")
    surf_search.add_argument("--limit", type=int, default=20, help="Maximum posts to collect.")
    surf_search.add_argument(
        "--surf-binary",
        default=None,
        help="Path to the Surf CLI binary. Defaults to PATH lookup or ~/.local/bin/surf.",
    )

    surf_list = subparsers.add_parser(
        "surf-list",
        help="List available Surf operations from the local Surf CLI catalog.",
    )
    surf_list.add_argument("--category", default=None, help="Optional Surf operation category filter.")
    surf_list.add_argument(
        "--surf-binary",
        default=None,
        help="Path to the Surf CLI binary. Defaults to PATH lookup or ~/.local/bin/surf.",
    )

    surf_call = subparsers.add_parser(
        "surf-call",
        help="Run any Surf CLI operation and save the JSON result.",
    )
    surf_call.add_argument("operation", help="Surf operation id, for example market-price or wallet-detail.")
    surf_call.add_argument(
        "--param",
        action="append",
        default=[],
        help="Operation parameter as key=value. Repeat for multiple parameters.",
    )
    surf_call.add_argument("--body-json", default=None, help="JSON object to send on stdin for POST-like Surf operations.")
    surf_call.add_argument(
        "--surf-binary",
        default=None,
        help="Path to the Surf CLI binary. Defaults to PATH lookup or ~/.local/bin/surf.",
    )

    surf_api_call = subparsers.add_parser(
        "surf-api-call",
        help="Call any Surf Data API endpoint directly with SURF_API_KEY.",
    )
    surf_api_call.add_argument("endpoint", help="Endpoint path, for example market/price or /gateway/v1/market/price.")
    surf_api_call.add_argument("--method", choices=["GET", "POST"], default="GET", help="HTTP method.")
    surf_api_call.add_argument(
        "--param",
        action="append",
        default=[],
        help="Query parameter as key=value. Repeat for multiple parameters.",
    )
    surf_api_call.add_argument("--body-json", default=None, help="JSON object to send as request body.")
    surf_api_call.add_argument("--max-rows", type=int, default=10, help="Maximum data rows to print.")

    surf_ask = subparsers.add_parser(
        "surf-ask",
        help="Agent-facing Surf workflow: ask a natural crypto/on-chain question and print a readable answer.",
    )
    surf_ask.add_argument("question", help="Natural-language crypto research question.")
    surf_ask.add_argument("--model", default="surf-2.0", help="Surf Chat API model.")
    surf_ask.add_argument(
        "--effort",
        choices=["auto", "none", "minimal", "low", "medium", "high", "xhigh"],
        default="auto",
        help="Research 2.0 reasoning effort. Auto uses high for deeper research wording.",
    )

    socialdata_search = subparsers.add_parser(
        "socialdata-search",
        help="Search X/Twitter posts through SocialData API. Direct X/Twitter API and Grok are not used.",
    )
    socialdata_search.add_argument("query", help="SocialData search query with supported Twitter operators.")
    socialdata_search.add_argument(
        "--type",
        choices=["Latest", "Top"],
        default="Latest",
        help="SocialData search type.",
    )
    socialdata_search.add_argument("--limit", type=int, default=20, help="Maximum posts to print after saving.")

    nansen_agent = subparsers.add_parser(
        "nansen-agent",
        help="Ask Nansen Agent an on-chain research question and save the streamed answer.",
    )
    nansen_agent.add_argument("question", help="Natural-language on-chain research question for Nansen Agent.")
    nansen_agent.add_argument(
        "--mode",
        choices=["fast", "expert"],
        default="fast",
        help="Nansen Agent mode: fast for quick lookups, expert for deeper synthesis.",
    )
    nansen_agent.add_argument(
        "--conversation-id",
        default=None,
        help="Optional Nansen conversation ID for follow-up questions.",
    )

    nansen_ask = subparsers.add_parser(
        "nansen-ask",
        help="Agent-facing Nansen workflow: ask a natural on-chain question and print a readable answer.",
    )
    nansen_ask.add_argument("question", help="Natural-language on-chain question from the user.")
    nansen_ask.add_argument(
        "--mode",
        choices=["auto", "fast", "expert"],
        default="auto",
        help="Nansen Agent mode. Auto uses expert for deep research wording.",
    )
    nansen_ask.add_argument(
        "--conversation-id",
        default=None,
        help="Optional Nansen conversation ID for follow-up questions.",
    )

    nansen_token_screener = subparsers.add_parser(
        "nansen-token-screener",
        help="Fetch Nansen token screener data for selected chains.",
    )
    nansen_token_screener.add_argument(
        "--chains",
        required=True,
        help="Comma-separated Nansen chain values, for example ethereum,solana,base.",
    )
    nansen_token_screener.add_argument(
        "--timeframe",
        choices=["5m", "10m", "1h", "6h", "24h", "7d", "30d"],
        default="24h",
        help="Nansen token screener timeframe.",
    )
    nansen_token_screener.add_argument("--page", type=int, default=1, help="Pagination page.")
    nansen_token_screener.add_argument("--per-page", type=int, default=10, help="Rows per page.")
    nansen_token_screener.add_argument(
        "--only-smart-money",
        action="store_true",
        help="Filter to tokens with smart money activity.",
    )
    nansen_token_screener.add_argument(
        "--filters-json",
        default=None,
        help="Additional JSON object for Nansen filters.",
    )
    nansen_token_screener.add_argument(
        "--order-by-json",
        default=None,
        help='Nansen order_by JSON array, for example [{"field":"volume","direction":"DESC"}].',
    )

    nansen_call = subparsers.add_parser(
        "nansen-call",
        help="Call any Nansen POST endpoint with a JSON body and save the raw response.",
    )
    nansen_call.add_argument("endpoint", help="Endpoint path, for example smart-money/netflow or token-screener.")
    nansen_call.add_argument("--body-json", required=True, help="JSON object to POST to Nansen.")
    nansen_call.add_argument("--max-rows", type=int, default=10, help="Maximum response rows to print.")

    plan = subparsers.add_parser("plan-query", help="Transform a natural question into a suggested X search.")
    plan.add_argument("question", help="Natural-language question to transform.")

    ask = subparsers.add_parser("ask", help="Choose a search provider, run it, save, and show a short summary.")
    ask.add_argument("question", help="Natural-language question to search through X/Twitter.")
    ask.add_argument(
        "--provider",
        choices=["grok", "surf", "socialdata"],
        default=None,
        help="Search provider. Required in non-interactive mode.",
    )
    ask.add_argument(
        "--max-search-results",
        type=int,
        default=20,
        help="Maximum sources Grok may consider when provider is grok.",
    )
    ask.add_argument("--limit", type=int, default=None, help="Override planned tweet limit.")
    ask.add_argument("--days", type=int, default=None, help="Override planned search window.")
    ask.add_argument(
        "--mode",
        choices=["auto", "recent", "all"],
        default="auto",
        help="Search endpoint: recent, full archive, or auto.",
    )
    ask.add_argument("--max-tweets", type=int, default=10, help="Maximum tweets to print after saving.")
    ask.add_argument(
        "--type",
        choices=["Latest", "Top"],
        default="Latest",
        help="SocialData search type when provider is socialdata.",
    )
    ask.add_argument(
        "--surf-binary",
        default=None,
        help="Path to the Surf CLI binary when provider is surf.",
    )

    show = subparsers.add_parser("show", help="Show a saved run.")
    show.add_argument("target", choices=["latest"], help="Which run to show.")
    show.add_argument("--max-tweets", type=int, default=20, help="Maximum tweets to print.")

    content_filter = subparsers.add_parser(
        "content-filter",
        help="Compare a candidate material summary with the content research index.",
    )
    content_filter.add_argument("--summary", required=True, help="Candidate material summary to check.")
    content_filter.add_argument(
        "--index-file",
        default=str(DEFAULT_CONTENT_INDEX),
        help="Path to content_research_index.md.",
    )
    content_filter.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help="Similarity threshold for duplicate detection.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)

    try:
        if args.command == "grok-search":
            return _grok_search(args, runs_dir)
        if args.command == "surf-search":
            return _surf_search(args, runs_dir)
        if args.command == "surf-list":
            return _surf_list(args)
        if args.command == "surf-call":
            return _surf_call(args, runs_dir)
        if args.command == "surf-api-call":
            return _surf_api_call(args, runs_dir)
        if args.command == "surf-ask":
            return _surf_ask(args, runs_dir)
        if args.command == "socialdata-search":
            return _socialdata_search(args, runs_dir)
        if args.command == "nansen-agent":
            return _nansen_agent(args, runs_dir)
        if args.command == "nansen-ask":
            return _nansen_ask(args, runs_dir)
        if args.command == "nansen-token-screener":
            return _nansen_token_screener(args, runs_dir)
        if args.command == "nansen-call":
            return _nansen_call(args, runs_dir)
        if args.command == "plan-query":
            return _plan_query(args)
        if args.command == "ask":
            return _ask(args, runs_dir)
        if args.command == "show":
            return _show(args, runs_dir)
        if args.command == "content-filter":
            return _content_filter(args)
    except (ConfigError, GrokApiError, SurfError, SocialDataError, NansenError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _grok_search(args: argparse.Namespace, runs_dir: Path) -> int:
    config = load_config(env_path=args.env_file)
    client = GrokClient(api_key=config.xai_api_key, model=GROK_MODEL)
    result = client.search(args.question, max_search_results=args.max_search_results)
    run_path = save_run(
        {
            "query": args.question,
            "source": "grok",
            "mode": "grok-search",
            "model": GROK_MODEL,
            "max_search_results": args.max_search_results,
            "answer": result["answer"],
            "citations": result.get("citations", []),
            "usage": result.get("usage", {}),
            "raw_response": result.get("raw_response", {}),
        },
        runs_dir=runs_dir,
    )

    print(f"Grok-only search: saved result to {run_path}")
    print("")
    print(result["answer"])
    citations = result.get("citations", [])
    if citations:
        print("")
        print("Citations:")
        for index, citation in enumerate(citations, start=1):
            print(f"{index}. {citation}")
    return 0


def _surf_search(args: argparse.Namespace, runs_dir: Path) -> int:
    client = SurfClient(binary_path=args.surf_binary)
    result = client.search_social_posts(args.query, limit=args.limit)
    posts = result.get("data", [])
    run_path = save_run(
        {
            "query": args.query,
            "source": "surf",
            "mode": "surf-search",
            "requested_limit": args.limit,
            "fetched": len(posts),
            "surf_data": result,
        },
        runs_dir=runs_dir,
    )

    print(f"Surf search: saved {len(posts)} posts to {run_path}")
    print("")
    _print_surf_posts(posts, max_posts=min(args.limit, 10))
    return 0


def _surf_list(args: argparse.Namespace) -> int:
    client = SurfClient(binary_path=args.surf_binary)
    result = client.list_operations(category=args.category)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _surf_call(args: argparse.Namespace, runs_dir: Path) -> int:
    params = _parse_key_value_pairs(args.param)
    body = _parse_json_object(args.body_json, "--body-json") if args.body_json else None
    client = SurfClient(binary_path=args.surf_binary)
    result = client.call_operation(args.operation, params=params, body=body)
    rows = result.get("data", [])
    fetched = len(rows) if isinstance(rows, list) else None
    run_path = save_run(
        {
            "query": f"surf-call {args.operation}",
            "source": "surf",
            "mode": "surf-call",
            "operation": args.operation,
            "params": params,
            "request_body": body,
            "fetched": fetched,
            "surf_data": result,
        },
        runs_dir=runs_dir,
    )

    label = f"{fetched} rows" if fetched is not None else "raw response"
    print(f"Surf operation: saved {label} to {run_path}")
    print("")
    _print_generic_surf_result(result, max_rows=10)
    return 0


def _surf_api_client(env_file: str) -> SurfApiClient:
    config = load_config(env_path=env_file)
    if not config.surf_api_key:
        raise ConfigError("Missing SURF_API_KEY. Add it to .env or export it in the shell.")
    return SurfApiClient(api_key=config.surf_api_key)


def _surf_api_call(args: argparse.Namespace, runs_dir: Path) -> int:
    params = _parse_key_value_pairs(args.param)
    body = _parse_json_object(args.body_json, "--body-json") if args.body_json else None
    client = _surf_api_client(args.env_file)
    result = client.request(args.method, args.endpoint, params=params, body=body)
    rows = result.get("data", [])
    fetched = len(rows) if isinstance(rows, list) else None
    run_path = save_run(
        {
            "query": f"surf-api-call {args.endpoint}",
            "source": "surf",
            "mode": "surf-api-call",
            "endpoint": args.endpoint,
            "method": args.method,
            "params": params,
            "request_body": body,
            "fetched": fetched,
            "surf_data": result,
        },
        runs_dir=runs_dir,
    )

    label = f"{fetched} rows" if fetched is not None else "raw response"
    print(f"Surf API: saved {label} to {run_path}")
    print("")
    _print_generic_surf_result(result, max_rows=args.max_rows)
    return 0


def _surf_ask(args: argparse.Namespace, runs_dir: Path) -> int:
    client = _surf_api_client(args.env_file)
    selected_effort = _select_surf_effort(args.question, args.effort)
    prompt = _build_surf_chat_prompt(args.question)
    result = client.chat_response(prompt, model=args.model, effort=selected_effort)
    answer = _extract_surf_answer(result)
    run_path = save_run(
        {
            "query": args.question,
            "source": "surf",
            "mode": "surf-ask",
            "model": args.model,
            "effort": selected_effort,
            "answer": answer,
            "surf_prompt": prompt,
            "surf_data": result,
        },
        runs_dir=runs_dir,
    )

    print(f"Surf/AskSurfAI answer: saved result to {run_path}")
    print(f"Effort: {selected_effort}")
    print("")
    print(answer if answer else json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _socialdata_search(args: argparse.Namespace, runs_dir: Path) -> int:
    config = load_config(env_path=args.env_file)
    if not config.socialdata_api_key:
        raise ConfigError("Missing SOCIALDATA_API_KEY. Add it to .env or export it in the shell.")

    client = SocialDataClient(api_key=config.socialdata_api_key)
    result = client.search(args.query, search_type=args.type)
    tweets = result.get("tweets", [])
    run_path = save_run(
        {
            "query": args.query,
            "source": "socialdata",
            "mode": "socialdata-search",
            "search_type": args.type,
            "fetched": len(tweets),
            "socialdata_data": result,
        },
        runs_dir=runs_dir,
    )

    print(f"SocialData search: saved {len(tweets)} posts to {run_path}")
    print("")
    _print_socialdata_posts(tweets, max_posts=args.limit)
    return 0


def _nansen_client(env_file: str) -> NansenClient:
    config = load_config(env_path=env_file)
    if not config.nansen_api_key:
        raise ConfigError("Missing NANSEN_API_KEY. Add it to .env or export it in the shell.")
    return NansenClient(api_key=config.nansen_api_key)


def _nansen_agent(args: argparse.Namespace, runs_dir: Path) -> int:
    client = _nansen_client(args.env_file)
    result = client.agent_research(
        args.question,
        mode=args.mode,
        conversation_id=args.conversation_id,
    )
    run_path = save_run(
        {
            "query": args.question,
            "source": "nansen",
            "mode": "nansen-agent",
            "nansen_mode": args.mode,
            "conversation_id": result.get("conversation_id"),
            "tool_calls": result.get("tool_calls", []),
            "answer": result.get("answer", ""),
            "events": result.get("events", []),
        },
        runs_dir=runs_dir,
    )

    print(f"Nansen agent: saved result to {run_path}")
    if result.get("conversation_id"):
        print(f"Conversation ID: {result['conversation_id']}")
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        print(f"Tools: {', '.join(str(tool) for tool in tool_calls)}")
    print("")
    print(result.get("answer", ""))
    return 0


def _nansen_ask(args: argparse.Namespace, runs_dir: Path) -> int:
    selected_mode = _select_nansen_mode(args.question, args.mode)
    prompt = _build_nansen_chat_prompt(args.question)
    client = _nansen_client(args.env_file)
    result = client.agent_research(
        prompt,
        mode=selected_mode,
        conversation_id=args.conversation_id,
    )
    run_path = save_run(
        {
            "query": args.question,
            "source": "nansen",
            "mode": "nansen-ask",
            "nansen_mode": selected_mode,
            "conversation_id": result.get("conversation_id"),
            "tool_calls": result.get("tool_calls", []),
            "answer": result.get("answer", ""),
            "nansen_prompt": prompt,
            "events": result.get("events", []),
        },
        runs_dir=runs_dir,
    )

    print(f"Nansen on-chain answer: saved result to {run_path}")
    print(f"Mode: {selected_mode}")
    if result.get("conversation_id"):
        print(f"Conversation ID: {result['conversation_id']}")
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        print(f"Tools: {', '.join(str(tool) for tool in tool_calls)}")
    print("")
    print(result.get("answer", ""))
    return 0


def _nansen_token_screener(args: argparse.Namespace, runs_dir: Path) -> int:
    filters = _parse_json_object(args.filters_json, "--filters-json") if args.filters_json else {}
    if args.only_smart_money:
        filters["only_smart_money"] = True

    body: dict[str, object] = {
        "chains": _parse_csv(args.chains),
        "timeframe": args.timeframe,
        "pagination": {"page": args.page, "per_page": args.per_page},
    }
    if filters:
        body["filters"] = filters
    if args.order_by_json:
        body["order_by"] = _parse_json_value(args.order_by_json, "--order-by-json")

    client = _nansen_client(args.env_file)
    result = client.post_json("token-screener", body)
    rows = result.get("data", [])
    fetched = len(rows) if isinstance(rows, list) else 0
    run_path = save_run(
        {
            "query": f"nansen-token-screener {','.join(body['chains'])}",
            "source": "nansen",
            "mode": "nansen-token-screener",
            "endpoint": "token-screener",
            "request_body": body,
            "fetched": fetched,
            "nansen_data": result,
        },
        runs_dir=runs_dir,
    )

    print(f"Nansen token screener: saved {fetched} rows to {run_path}")
    print("")
    _print_nansen_rows(rows if isinstance(rows, list) else [], max_rows=args.per_page)
    return 0


def _nansen_call(args: argparse.Namespace, runs_dir: Path) -> int:
    body = _parse_json_object(args.body_json, "--body-json")
    client = _nansen_client(args.env_file)
    result = client.post_json(args.endpoint, body)
    rows = result.get("data", [])
    fetched = len(rows) if isinstance(rows, list) else None
    run_path = save_run(
        {
            "query": f"nansen-call {args.endpoint}",
            "source": "nansen",
            "mode": "nansen-call",
            "endpoint": args.endpoint,
            "request_body": body,
            "fetched": fetched,
            "nansen_data": result,
        },
        runs_dir=runs_dir,
    )

    row_text = f"{fetched} rows" if fetched is not None else "raw response"
    print(f"Nansen call: saved {row_text} to {run_path}")
    print("")
    if isinstance(rows, list) and rows:
        _print_nansen_rows(rows, max_rows=args.max_rows)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _select_nansen_mode(question: str, explicit_mode: str) -> str:
    if explicit_mode in {"fast", "expert"}:
        return explicit_mode

    lowered = question.lower()
    expert_markers = (
        "deep",
        "глуб",
        "разбор",
        "исслед",
        "research",
        "explain",
        "объясни",
        "причин",
        "story",
        "недел",
        "месяц",
        "month",
        "week",
        "compare",
        "сравни",
    )
    if any(marker in lowered for marker in expert_markers):
        return "expert"
    return "fast"


def _select_surf_effort(question: str, explicit_effort: str) -> str:
    if explicit_effort != "auto":
        return explicit_effort

    lowered = question.lower()
    high_markers = (
        "deep",
        "глуб",
        "разбор",
        "исслед",
        "research",
        "explain",
        "объясни",
        "причин",
        "story",
        "недел",
        "месяц",
        "month",
        "week",
        "compare",
        "сравни",
        "due diligence",
        "расслед",
        "investigate",
    )
    if any(marker in lowered for marker in high_markers):
        return "high"
    return "medium"


def _build_surf_chat_prompt(question: str) -> str:
    return (
        "Ты Surf/AskSurfAI crypto research agent. Ответь на русском, кратко и прикладно.\n\n"
        "Исходный вопрос пользователя:\n"
        f"{question}\n\n"
        "Используй Surf Chat API Research 2.0 и доступные Surf data sources для crypto, market, wallet, "
        "token, project, social, news, exchange, Hyperliquid, prediction-market и on-chain данных. "
        "Если вопрос про кошелек, транзакции, holders, DEX trades, flows или smart money, приоритизируй "
        "on-chain факты и явно отделяй их от рыночной или социальной интерпретации. "
        "Не используй Grok, SocialData, Nansen или прямой X/Twitter API. Не выдумывай метрики, которых нет в данных.\n\n"
        "Верни ответ строго в такой структуре:\n"
        "1. Короткий вывод: 1-3 предложения с главным смыслом.\n"
        "2. Что видно в данных: 3-6 пунктов с конкретными токенами, сетями, кошельками, протоколами, flows, "
        "периодами или метриками.\n"
        "3. Почему это важно: практическая интерпретация без инвестиционных обещаний.\n"
        "4. Ограничения данных: что Surf/AskSurfAI не подтвердил, где данные могут быть неполными или запаздывать.\n"
        "5. Что проверить дальше: 2-4 следующих проверки через Surf operations или on-chain SQL.\n"
    )


def _build_nansen_chat_prompt(question: str) -> str:
    return (
        "Ты Nansen on-chain research analyst. Ответь на русском, кратко и прикладно.\n\n"
        "Исходный вопрос пользователя:\n"
        f"{question}\n\n"
        "Используй Nansen API data и Nansen Agent tools, если они доступны для вопроса. "
        "Не используй Twitter/X chatter и не выдумывай метрики, которых нет в данных.\n\n"
        "Верни ответ строго в такой структуре:\n"
        "1. Короткий вывод: 1-3 предложения с главным смыслом.\n"
        "2. Что видно в данных: 3-6 пунктов с конкретными токенами, сетями, кошельками, flows, периодами или метриками.\n"
        "3. Почему это важно: практическая интерпретация без инвестиционных обещаний.\n"
        "4. Ограничения данных: что Nansen не подтвердил или где мало данных.\n"
        "5. Что проверить дальше: 2-4 следующих ончейн-проверки.\n"
    )


def _select_search_provider(explicit_provider: str | None) -> str:
    if explicit_provider:
        return explicit_provider

    providers = ["grok", "surf", "socialdata"]
    provider_list = "\n".join(f"{i}. {provider.upper()}" for i, provider in enumerate(providers, start=1))
    if not sys.stdin.isatty():
        raise ValueError(
            f"Провайдер поиска не указан. Передайте --provider PROVIDER.\n\nДоступные провайдеры:\n{provider_list}"
        )

    print("Какого провайдера поиска использовать?\n")
    print(provider_list)
    print("")

    choice = input("Введите номер провайдера: ").strip()
    try:
        provider_index = int(choice) - 1
        return providers[provider_index]
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Invalid search provider choice: {choice}") from exc


def _plan_query(args: argparse.Namespace) -> int:
    plan = plan_query(args.question)
    print(f"Question: {plan.question}")
    print(f"X query: {plan.query}")
    print(f"Days: {plan.days}")
    print(f"Limit: {plan.limit}")
    print("")
    print(plan.command())
    return 0


def _ask(args: argparse.Namespace, runs_dir: Path) -> int:
    provider = _select_search_provider(args.provider)
    if provider == "grok":
        grok_args = argparse.Namespace(
            env_file=args.env_file,
            question=args.question,
            max_search_results=args.max_search_results,
        )
        return _grok_search(grok_args, runs_dir)
    if provider == "surf":
        surf_args = argparse.Namespace(
            query=args.question,
            limit=args.limit or args.max_tweets,
            surf_binary=args.surf_binary,
        )
        return _surf_search(surf_args, runs_dir)
    if provider == "socialdata":
        socialdata_args = argparse.Namespace(
            env_file=args.env_file,
            query=args.question,
            type=args.type,
            limit=args.limit or args.max_tweets,
        )
        return _socialdata_search(socialdata_args, runs_dir)

    raise ValueError(f"Unknown search provider: {provider}")


def _show(args: argparse.Namespace, runs_dir: Path) -> int:
    path = latest_run_path(runs_dir)
    if path is None:
        print(f"No saved runs found in {runs_dir}", file=sys.stderr)
        return 1

    run = load_run(path)
    _print_run_summary(run, path, max_tweets=args.max_tweets)
    return 0


def _content_filter(args: argparse.Namespace) -> int:
    entries = load_content_index(args.index_file)
    match = find_similar_summary(args.summary, entries, threshold=args.threshold)
    if match is None:
        print("Status: relevant_new")
        print(f"Checked summaries: {len(entries)}")
        print(f"Threshold: {args.threshold:.2f}")
        return 0

    print("Status: irrelevant_duplicate")
    print(f"Similarity: {match.score:.2f}")
    print(f"Threshold: {args.threshold:.2f}")
    print(f"Matched topic: {match.entry.topic}")
    print(f"Matched summary: {match.entry.summary}")
    print(f"Matched source: {match.entry.source_url}")
    print(f"Matched file: {match.entry.file_path}")
    return 0


def _print_run_summary(run: dict, path: Path, max_tweets: int) -> None:
    if run.get("mode") in {"nansen-agent", "nansen-ask"}:
        print(f"Run: {path}")
        print(f"Query: {run.get('query')}")
        print(f"Mode: {run.get('mode')} | Nansen mode: {run.get('nansen_mode')}")
        if run.get("conversation_id"):
            print(f"Conversation ID: {run.get('conversation_id')}")
        tool_calls = run.get("tool_calls", [])
        if tool_calls:
            print(f"Tools: {', '.join(str(tool) for tool in tool_calls)}")
        print("")
        print(run.get("answer", ""))
        return
    if run.get("mode") in {"nansen-token-screener", "nansen-call"}:
        rows = run.get("nansen_data", {}).get("data", [])
        print(f"Run: {path}")
        print(f"Query: {run.get('query')}")
        print(f"Mode: {run.get('mode')} | Endpoint: {run.get('endpoint')} | Fetched: {run.get('fetched')}")
        print("")
        if isinstance(rows, list) and rows:
            _print_nansen_rows(rows, max_rows=max_tweets)
        else:
            print(json.dumps(run.get("nansen_data", {}), ensure_ascii=False, indent=2))
        return
    if run.get("mode") == "surf-search":
        posts = run.get("surf_data", {}).get("data", [])
        print(f"Run: {path}")
        print(f"Query: {run.get('query')}")
        print(f"Mode: {run.get('mode')} | Fetched: {run.get('fetched')}")
        print("")
        _print_surf_posts(posts, max_posts=max_tweets)
        return
    if run.get("mode") in {"surf-call", "surf-api-call"}:
        result = run.get("surf_data", {})
        print(f"Run: {path}")
        print(f"Query: {run.get('query')}")
        if run.get("mode") == "surf-call":
            print(f"Mode: {run.get('mode')} | Operation: {run.get('operation')} | Fetched: {run.get('fetched')}")
        else:
            print(f"Mode: {run.get('mode')} | Endpoint: {run.get('endpoint')} | Fetched: {run.get('fetched')}")
        print("")
        _print_generic_surf_result(result, max_rows=max_tweets)
        return
    if run.get("mode") == "surf-ask":
        print(f"Run: {path}")
        print(f"Query: {run.get('query')}")
        print(f"Mode: {run.get('mode')} | Model: {run.get('model')} | Effort: {run.get('effort')}")
        print("")
        print(run.get("answer", ""))
        return
    if run.get("mode") == "socialdata-search":
        tweets = run.get("socialdata_data", {}).get("tweets", [])
        print(f"Run: {path}")
        print(f"Query: {run.get('query')}")
        print(f"Mode: {run.get('mode')} | Fetched: {run.get('fetched')}")
        print("")
        _print_socialdata_posts(tweets, max_posts=max_tweets)
        return

    print(f"Run: {path}")
    print(f"Query: {run.get('query')}")
    print(f"Mode: {run.get('mode')}")
    print("")
    print(json.dumps(run, ensure_ascii=False, indent=2))


def _print_surf_posts(posts: list[dict], max_posts: int) -> None:
    for index, post in enumerate(posts[:max_posts], start=1):
        author = post.get("author", {})
        handle = author.get("handle")
        username = f"@{handle}" if handle else "author:unknown"
        created_at = _format_surf_created_at(post.get("created_at"))
        text = " ".join(post.get("text", "").split())
        url = post.get("url")
        stats = post.get("stats", {})
        likes = stats.get("likes", 0)
        reposts = stats.get("reposts", 0)
        replies = stats.get("replies", 0)
        views = stats.get("views", 0)

        print(f"{index}. {username} | {created_at} | likes:{likes} reposts:{reposts} replies:{replies} views:{views}")
        print(f"   {text}")
        if url:
            print(f"   {url}")


def _parse_csv(value: str) -> list[str]:
    items = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not items:
        raise ValueError("Expected at least one comma-separated value.")
    return items


def _parse_json_object(value: str, argument_name: str) -> dict[str, object]:
    parsed = _parse_json_value(value, argument_name)
    if not isinstance(parsed, dict):
        raise ValueError(f"{argument_name} must be a JSON object.")
    return parsed


def _parse_json_value(value: str, argument_name: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{argument_name} must be valid JSON: {exc.msg}") from exc


def _parse_key_value_pairs(values: list[str]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for raw_value in values:
        if "=" not in raw_value:
            raise ValueError(f"--param must use key=value format: {raw_value}")
        key, value = raw_value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"--param key cannot be empty: {raw_value}")
        parsed[key.replace("-", "_")] = _parse_param_value(value.strip())
    return parsed


def _parse_param_value(value: str) -> object:
    if value == "":
        return ""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _print_generic_surf_result(result: dict, max_rows: int) -> None:
    rows = result.get("data")
    if isinstance(rows, list):
        for index, row in enumerate(rows[:max_rows], start=1):
            print(f"{index}. {json.dumps(row, ensure_ascii=False)}")
        if not rows:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


def _extract_surf_answer(result: dict) -> str:
    output_text = result.get("output_text")
    if isinstance(output_text, str):
        return output_text

    text = result.get("text")
    if isinstance(text, str):
        return text

    output = result.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for content_item in content:
                    if isinstance(content_item, dict):
                        content_text = content_item.get("text")
                        if isinstance(content_text, str):
                            chunks.append(content_text)
            item_text = item.get("text")
            if isinstance(item_text, str):
                chunks.append(item_text)
        if chunks:
            return "\n".join(chunks)

    return ""


def _print_nansen_rows(rows: list[dict], max_rows: int) -> None:
    for index, row in enumerate(rows[:max_rows], start=1):
        if not isinstance(row, dict):
            print(f"{index}. {row}")
            continue

        chain = row.get("chain", "unknown-chain")
        symbol = row.get("token_symbol") or row.get("symbol") or row.get("token_address") or row.get("address") or "unknown-token"
        headline_fields = [
            ("price", row.get("price_usd")),
            ("change", row.get("price_change")),
            ("volume", row.get("volume")),
            ("netflow", row.get("netflow") or row.get("net_flow_24h_usd")),
            ("mcap", row.get("market_cap_usd")),
        ]
        metrics = " ".join(f"{name}:{value}" for name, value in headline_fields if value is not None)
        print(f"{index}. {symbol} | {chain}" + (f" | {metrics}" if metrics else ""))

        address = row.get("token_address") or row.get("address")
        if address:
            print(f"   address: {address}")


def _format_surf_created_at(value: object) -> str:
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        return value
    return "unknown-time"


def _print_socialdata_posts(tweets: list[dict], max_posts: int) -> None:
    for index, tweet in enumerate(tweets[:max_posts], start=1):
        user = tweet.get("user", {})
        handle = user.get("screen_name")
        username = f"@{handle}" if handle else "author:unknown"
        created_at = tweet.get("tweet_created_at", "unknown-time")
        text = " ".join((tweet.get("full_text") or tweet.get("text") or "").split())
        tweet_id = tweet.get("id_str")
        url = f"https://x.com/{handle}/status/{tweet_id}" if handle and tweet_id else None
        likes = tweet.get("favorite_count", 0)
        reposts = tweet.get("retweet_count", 0)
        replies = tweet.get("reply_count", 0)
        views = tweet.get("views_count", 0)

        print(f"{index}. {username} | {created_at} | likes:{likes} reposts:{reposts} replies:{replies} views:{views}")
        print(f"   {text}")
        if url:
            print(f"   {url}")
