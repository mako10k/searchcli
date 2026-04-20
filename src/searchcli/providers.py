from __future__ import annotations

from urllib.parse import urlparse

import httpx

from searchcli.errors import SearchCliError
from searchcli.models import ProviderMeta, SearchRequest, SearchResponse, SearchResult
from searchcli.secrets import require_api_key


PROVIDERS: dict[str, ProviderMeta] = {
    "serper": ProviderMeta(
        id="serper",
        display_name="Serper",
        env_var="SEARCHCLI_SERPER_API_KEY",
        signup_url="https://serper.dev",
        docs_url="https://serper.dev/api-key",
        summary="Google 検索ベースの軽量な検索 API。",
        best_for="まず結果 URL を安定して集めたいとき。最初の 1 つとして推奨。",
        tradeoffs="回答生成は補助的で、深い要約や調査向きではない。",
        notes=["結果一覧中心", "ニュースや画像などへの拡張余地あり"],
    ),
    "tavily": ProviderMeta(
        id="tavily",
        display_name="Tavily",
        env_var="SEARCHCLI_TAVILY_API_KEY",
        signup_url="https://tavily.com",
        docs_url="https://docs.tavily.com",
        summary="検索と要約を両立しやすい RAG 向け API。",
        best_for="検索結果と要約を両方ほしいとき。RAG やエージェント用途向き。",
        tradeoffs="URL 一覧だけ欲しい用途では Serper より重く感じる場合がある。",
        notes=["answer を返しやすい", "search_depth と topic を調整可能"],
    ),
    "perplexity": ProviderMeta(
        id="perplexity",
        display_name="Perplexity",
        env_var="SEARCHCLI_PERPLEXITY_API_KEY",
        signup_url="https://www.perplexity.ai/settings/api",
        docs_url="https://docs.perplexity.ai",
        summary="回答重視の web-connected API。",
        best_for="自然文の回答を主に欲しいとき。リサーチ補助や対話型用途向き。",
        tradeoffs="URL の網羅一覧や厳密な件数制御は他 2 つより弱い場合がある。",
        notes=["引用 URL を伴う回答向き", "モデル指定が可能"],
    ),
}


def provider_help_summary() -> str:
    return (
        "serper=URL 一覧重視, "
        "tavily=検索+要約重視, "
        "perplexity=回答重視"
    )


PAIRWISE_TRADEOFFS: dict[frozenset[str], dict[str, str]] = {
    frozenset({"serper", "tavily"}): {
        "serper": "tavily と比べて、URL 一覧を軽く素早く集めたいとき向き。",
        "tavily": "serper と比べて、検索結果に加えて answer や深めの要約も欲しいとき向き。",
    },
    frozenset({"serper", "perplexity"}): {
        "serper": "perplexity と比べて、自然文回答より URL 一覧の回収を優先したいとき向き。",
        "perplexity": "serper と比べて、URL 一覧より自然文の回答を重視したいとき向き。",
    },
    frozenset({"tavily", "perplexity"}): {
        "tavily": "perplexity と比べて、回答だけでなく URL 一覧や検索結果も扱いたいとき向き。",
        "perplexity": "tavily と比べて、検索結果一覧より回答中心で使いたいとき向き。",
    },
}


def contextual_tradeoff(provider: ProviderMeta, selected_provider_ids: list[str], scope: str) -> str | None:
    if scope != "active":
        return provider.tradeoffs
    if len(selected_provider_ids) <= 1:
        return None
    if len(selected_provider_ids) == 2:
        pair = PAIRWISE_TRADEOFFS.get(frozenset(selected_provider_ids), {})
        return pair.get(provider.id)
    return provider.tradeoffs


def list_providers() -> list[ProviderMeta]:
    return list(PROVIDERS.values())


def get_provider(provider: str) -> ProviderMeta:
    normalized = provider.strip().lower()
    if normalized not in PROVIDERS:
        supported = ", ".join(sorted(PROVIDERS))
        raise SearchCliError(
            code="provider_unknown",
            message=f"未対応プロバイダです: {provider}",
            recovery=[
                f"対応プロバイダから選択する: {supported}",
                "searchcli providers で登録先と特徴を確認する",
            ],
        )
    return PROVIDERS[normalized]


def execute_search(request: SearchRequest, include_raw: bool = False) -> SearchResponse:
    provider = get_provider(request.provider)
    secret = require_api_key(provider.id)

    try:
        with httpx.Client(timeout=request.timeout, headers={"User-Agent": "searchcli/0.1.0"}) as client:
            if provider.id == "serper":
                response = _search_serper(client, request, secret.api_key or "")
            elif provider.id == "tavily":
                response = _search_tavily(client, request, secret.api_key or "")
            else:
                response = _search_perplexity(client, request, secret.api_key or "")
    except httpx.TimeoutException as exc:
        raise SearchCliError(
            code="request_timeout",
            message=f"{provider.display_name} への問い合わせがタイムアウトしました。",
            recovery=[
                "--timeout を大きくする",
                "ネットワーク疎通を確認する",
                "件数を減らして再試行する: --limit 3",
            ],
            details={"provider": provider.id},
        ) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise SearchCliError(
            code="api_http_error",
            message=f"{provider.display_name} API が HTTP {status} を返しました。",
            recovery=[
                "API キーが正しいか確認する",
                "利用上限や課金状態を確認する",
                "searchcli auth where で認証元を確認する",
            ],
            details={"provider": provider.id, "status": status, "body": exc.response.text[:1000]},
        ) from exc
    except httpx.HTTPError as exc:
        raise SearchCliError(
            code="network_error",
            message=f"{provider.display_name} への接続に失敗しました。",
            recovery=[
                "プロキシや DNS 設定を確認する",
                "少し待って再試行する",
                "別プロバイダで代替する",
            ],
            details={"provider": provider.id, "reason": str(exc)},
        ) from exc

    response.auth_source = secret.source
    if not include_raw:
        response.raw = None
    return response


def _search_serper(client: httpx.Client, request: SearchRequest, api_key: str) -> SearchResponse:
    payload: dict[str, object] = {
        "q": request.query,
        "num": request.limit,
        "page": 1,
        "autocorrect": True,
    }
    if request.region:
        payload["gl"] = request.region
    if request.language:
        payload["hl"] = request.language

    response = client.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json=payload,
    )
    response.raise_for_status()
    raw = response.json()

    results = [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=item.get("snippet", ""),
            source=_domain(item.get("link", "")),
            metadata={"position": item.get("position")},
        )
        for item in raw.get("organic", [])[: request.limit]
    ]

    answer = None
    answer_box = raw.get("answerBox") or {}
    if request.answer:
        answer = answer_box.get("answer") or answer_box.get("snippet") or raw.get("knowledgeGraph", {}).get("description")

    warnings: list[str] = []
    if not results:
        warnings.append("検索結果が 0 件でした。語句やプロバイダを変えて再試行してください。")

    return SearchResponse(
        provider="serper",
        query=request.query,
        answer=answer,
        results=results,
        warnings=warnings,
        raw=raw,
    )


def _search_tavily(client: httpx.Client, request: SearchRequest, api_key: str) -> SearchResponse:
    payload: dict[str, object] = {
        "api_key": api_key,
        "query": request.query,
        "max_results": request.limit,
        "search_depth": request.search_depth,
        "topic": request.topic,
        "include_answer": request.answer,
        "include_raw_content": False,
        "include_images": False,
    }
    response = client.post("https://api.tavily.com/search", json=payload)
    response.raise_for_status()
    raw = response.json()

    results = [
        SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", ""),
            score=item.get("score"),
            source=_domain(item.get("url", "")),
            metadata={"published_date": item.get("published_date")},
        )
        for item in raw.get("results", [])[: request.limit]
    ]

    warnings: list[str] = []
    if raw.get("response_time"):
        warnings.append(f"provider_response_time={raw['response_time']}")

    return SearchResponse(
        provider="tavily",
        query=request.query,
        answer=raw.get("answer") if request.answer else None,
        results=results,
        warnings=warnings,
        raw=raw,
    )


def _search_perplexity(client: httpx.Client, request: SearchRequest, api_key: str) -> SearchResponse:
    payload = {
        "model": request.model,
        "messages": [
            {
                "role": "system",
                "content": "You are a web search assistant. Respond with grounded, concise findings and cite sources.",
            },
            {"role": "user", "content": request.query},
        ],
        "temperature": 0.1,
    }
    response = client.post(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
    )
    response.raise_for_status()
    raw = response.json()

    message = (
        raw.get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )
    citations = raw.get("citations") or raw.get("search_results") or raw.get("web_results") or []

    results: list[SearchResult] = []
    for item in citations[: request.limit]:
        if isinstance(item, str):
            url = item
            title = _domain(url)
            snippet = ""
        else:
            url = item.get("url") or item.get("link") or ""
            title = item.get("title") or _domain(url)
            snippet = item.get("snippet") or item.get("content") or ""
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source=_domain(url),
            )
        )

    warnings: list[str] = []
    if not results:
        warnings.append("Perplexity は回答中心のため URL 一覧が少ない場合があります。")

    return SearchResponse(
        provider="perplexity",
        query=request.query,
        answer=message if request.answer else None,
        results=results,
        warnings=warnings,
        raw=raw,
    )


def _domain(url: str) -> str | None:
    if not url:
        return None
    return urlparse(url).netloc or None
