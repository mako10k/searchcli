from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from searchcli.config import load_config
from searchcli.errors import SearchCliError
from searchcli.models import SearchRequest
from searchcli.providers import contextual_tradeoff, execute_search, list_providers
from searchcli.secrets import get_api_key, keyring_backend_name, require_api_key


class SearchCliMcpServer:
    def search(
        self,
        query: str,
        provider: str | None = None,
        limit: int = 5,
        region: str | None = None,
        language: str | None = None,
        answer: bool = True,
        topic: str = "general",
        search_depth: str = "basic",
        timeout: float | None = None,
        model: str = "sonar",
        include_raw: bool = False,
    ) -> dict[str, Any]:
        config = load_config()
        selected_provider = (provider or config.default_provider).strip().lower()
        request = SearchRequest(
            query=query,
            provider=selected_provider,
            limit=limit,
            region=self._optional_string(region),
            language=self._optional_string(language),
            answer=answer,
            topic=self._optional_string(topic) or "general",
            search_depth=self._optional_string(search_depth) or "basic",
            timeout=timeout or config.timeout_seconds,
            model=self._optional_string(model) or "sonar",
        )
        response = execute_search(request, include_raw=include_raw)
        return response.to_dict(include_raw=include_raw)

    def providers(self, active_only: bool = True) -> dict[str, Any]:
        providers, scope, fallback = self._provider_view(prefer_active=active_only)
        return {
            "ok": True,
            "requested_scope": "active" if active_only else "available",
            "scope": scope,
            "fallback": fallback,
            "providers": providers,
        }

    def doctor(self) -> dict[str, Any]:
        config = load_config()
        checks = []
        for provider in list_providers():
            try:
                secret = require_api_key(provider.id)
                status = {
                    "provider": provider.id,
                    "configured": True,
                    "source": secret.source,
                }
            except SearchCliError:
                status = {
                    "provider": provider.id,
                    "configured": False,
                    "source": None,
                }
            checks.append(status)
        return {
            "ok": True,
            "default_provider": config.default_provider,
            "default_format": config.default_format,
            "timeout_seconds": config.timeout_seconds,
            "keyring_backend": keyring_backend_name(),
            "providers": checks,
        }

    def to_result(
        self,
        payload: dict[str, Any],
        *,
        is_error: bool = False,
    ) -> CallToolResult:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(payload, ensure_ascii=False, indent=2),
                )
            ],
            structuredContent=payload,
            isError=is_error,
        )

    def _provider_view(
        self,
        prefer_active: bool,
    ) -> tuple[list[dict[str, object]], str, bool]:
        available = list_providers()
        active_ids = self._active_provider_ids()

        scope = "active" if prefer_active and active_ids else "available"
        fallback = prefer_active and not active_ids
        selected = [
            provider
            for provider in available
            if scope == "available" or provider.id in active_ids
        ]
        selected_ids = [provider.id for provider in selected]

        rows: list[dict[str, object]] = []
        for provider in selected:
            row = provider.to_dict()
            row["is_active"] = provider.id in active_ids
            tradeoff = contextual_tradeoff(provider, selected_ids, scope)
            if tradeoff is None:
                row.pop("tradeoffs", None)
            else:
                row["tradeoffs"] = tradeoff
            rows.append(row)
        return rows, scope, fallback

    def _active_provider_ids(self) -> list[str]:
        active_ids: list[str] = []
        for provider in list_providers():
            try:
                lookup = get_api_key(provider.id)
            except SearchCliError:
                continue
            if lookup.api_key:
                active_ids.append(provider.id)
        return active_ids

    def _optional_string(self, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


def create_mcp_app(server: SearchCliMcpServer | None = None) -> FastMCP:
    implementation = server or SearchCliMcpServer()
    app = FastMCP(
        "searchcli",
        instructions="Structured multi-provider web search tools for searchcli.",
    )

    @app.tool()
    def search(
        query: str,
        provider: str | None = None,
        limit: int = 5,
        region: str | None = None,
        language: str | None = None,
        answer: bool = True,
        topic: str = "general",
        search_depth: str = "basic",
        timeout: float | None = None,
        model: str = "sonar",
        include_raw: bool = False,
    ) -> CallToolResult:
        """Run a web search and return structured results."""
        try:
            payload = implementation.search(
                query=query,
                provider=provider,
                limit=limit,
                region=region,
                language=language,
                answer=answer,
                topic=topic,
                search_depth=search_depth,
                timeout=timeout,
                model=model,
                include_raw=include_raw,
            )
        except SearchCliError as exc:
            return implementation.to_result(exc.to_payload(), is_error=True)
        return implementation.to_result(payload)

    @app.tool()
    def providers(active_only: bool = True) -> CallToolResult:
        """List configured or available search providers with guidance."""
        payload = implementation.providers(active_only=active_only)
        return implementation.to_result(payload)

    @app.tool()
    def doctor() -> CallToolResult:
        """Inspect current config and provider authentication status."""
        payload = implementation.doctor()
        return implementation.to_result(payload)

    return app


def run_stdio_server() -> None:
    create_mcp_app().run(transport="stdio")


def main() -> None:
    run_stdio_server()


if __name__ == "__main__":
    main()