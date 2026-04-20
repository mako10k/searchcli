from __future__ import annotations

import json
from typing import Annotated

import typer

from searchcli import __version__
from searchcli.config import AppConfig, CONFIG_PATH, load_config, save_config
from searchcli.errors import SearchCliError
from searchcli.models import SearchRequest
from searchcli.providers import contextual_tradeoff, execute_search, get_provider, list_providers, provider_help_summary
from searchcli.secrets import delete_api_key, env_var_name, get_api_key, keyring_backend_name, require_api_key, set_api_key

PROVIDER_HELP = (
    "プロバイダを選択します。"
    f" {provider_help_summary()}。"
    " 迷ったら serper。詳しくは searchcli providers"
)

app = typer.Typer(
    help="構造化された web 検索を返す軽量 CLI。標準出力は自動化向け、エラーは復旧案付きで標準エラーへ出力します。",
    no_args_is_help=True,
    add_completion=False,
)
auth_app = typer.Typer(help="API キーを OS キーチェーンへ保存します。", no_args_is_help=True)
config_app = typer.Typer(help="既定値を管理します。", no_args_is_help=True)
app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")


def _emit_json(payload: dict, *, err: bool = False) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=err)


def _raise_cli_error(exc: SearchCliError) -> None:
    _emit_json(exc.to_payload(), err=True)
    raise typer.Exit(code=exc.exit_code)


def _resolve_provider(value: str | None, config: AppConfig) -> str:
    return (value or config.default_provider).strip().lower()


def _active_provider_ids() -> list[str]:
    active_ids: list[str] = []
    for provider in list_providers():
        try:
            lookup = get_api_key(provider.id)
        except SearchCliError:
            continue
        if lookup.api_key:
            active_ids.append(provider.id)
    return active_ids


def _validate_default_provider_choice(provider: str, allowed_provider_ids: list[str]) -> str:
    selected = provider.strip().lower()
    if selected not in allowed_provider_ids:
        raise SearchCliError(
            code="default_provider_invalid",
            message=f"default provider に選べません: {provider}",
            recovery=[
                f"次から選択してください: {', '.join(allowed_provider_ids)}",
                "詳しくは searchcli providers を見ろ",
            ],
        )
    return selected


def _persist_default_provider(provider_id: str) -> str:
    config = load_config()
    config.default_provider = provider_id
    path = save_config(config)
    return str(path)


def _provider_view(prefer_active: bool) -> tuple[list[dict[str, object]], str, bool]:
    available = list_providers()
    active_ids = _active_provider_ids()

    scope = "active" if prefer_active and active_ids else "available"
    fallback = prefer_active and not active_ids
    selected = [provider for provider in available if scope == "available" or provider.id in active_ids]
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


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", help="バージョンを表示して終了します。"),
    ] = None,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command("search")
def search_command(
    query: Annotated[str, typer.Argument(help="検索クエリ")],
    provider: Annotated[str | None, typer.Option("--provider", "-p", help=PROVIDER_HELP)]=None,
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, max=20, help="取得件数")]=5,
    region: Annotated[str | None, typer.Option("--region", help="地域コード。例: jp, us")]=None,
    language: Annotated[str | None, typer.Option("--lang", help="言語コード。例: ja, en")]=None,
    answer: Annotated[bool, typer.Option("--answer/--no-answer", help="要約回答を含める")]=True,
    topic: Annotated[str, typer.Option("--topic", help="Tavily 用 topic。general または news")]="general",
    search_depth: Annotated[str, typer.Option("--search-depth", help="Tavily 用 depth。basic または advanced")]="basic",
    timeout: Annotated[float | None, typer.Option("--timeout", min=1, help="タイムアウト秒")]=None,
    model: Annotated[str, typer.Option("--model", help="Perplexity 用モデル。既定: sonar")]="sonar",
    output_format: Annotated[str | None, typer.Option("--format", help="json, jsonl, table")]=None,
    include_raw: Annotated[bool, typer.Option("--raw", help="プロバイダの生レスポンスを含める")]=False,
) -> None:
    try:
        config = load_config()
        selected_provider = _resolve_provider(provider, config)
        selected_format = (output_format or config.default_format).lower()
        request = SearchRequest(
            query=query,
            provider=selected_provider,
            limit=limit,
            region=region,
            language=language,
            answer=answer,
            topic=topic,
            search_depth=search_depth,
            timeout=timeout or config.timeout_seconds,
            model=model,
        )
        response = execute_search(request, include_raw=include_raw)
        payload = response.to_dict(include_raw=include_raw)
        if selected_format == "json":
            _emit_json(payload)
            return
        if selected_format == "jsonl":
            typer.echo(json.dumps({k: v for k, v in payload.items() if k != "results"}, ensure_ascii=False))
            for item in payload["results"]:
                typer.echo(json.dumps(item, ensure_ascii=False))
            return
        if selected_format == "table":
            typer.echo(f"provider: {payload['provider']}")
            typer.echo(f"query: {payload['query']}")
            if payload.get("answer"):
                typer.echo(f"answer: {payload['answer']}")
            for index, item in enumerate(payload["results"], start=1):
                typer.echo(f"{index}. {item['title']}")
                typer.echo(f"   {item['url']}")
                if item.get("snippet"):
                    typer.echo(f"   {item['snippet']}")
            if payload.get("warnings"):
                typer.echo("warnings:")
                for warning in payload["warnings"]:
                    typer.echo(f"- {warning}")
            return
        raise SearchCliError(
            code="format_invalid",
            message=f"未対応の出力形式です: {selected_format}",
            recovery=["--format json, --format jsonl, --format table のいずれかを使う"],
        )
    except SearchCliError as exc:
        _raise_cli_error(exc)


@app.command("providers")
def providers_command(
    output_format: Annotated[str, typer.Option("--format", help="json または table")]="table",
    active: Annotated[
        bool,
        typer.Option(
            "--active/--available",
            help="表示対象。既定は active。active が 0 件なら available に自動フォールバックします。",
        ),
    ] = True,
) -> None:
    providers, scope, fallback = _provider_view(prefer_active=active)
    if output_format == "json":
        _emit_json(
            {
                "ok": True,
                "requested_scope": "active" if active else "available",
                "scope": scope,
                "fallback": fallback,
                "providers": providers,
            }
        )
        return
    typer.echo(f"view: {scope}")
    if fallback:
        typer.echo("active provider が 0 件のため available を表示しています。")
    typer.echo("")
    if scope == "available":
        typer.echo("選び方:")
        typer.echo("- 迷ったら serper: URL 一覧を軽く安定して取りたい")
        typer.echo("- 検索と要約を両方ほしいなら tavily")
        typer.echo("- 回答中心で使うなら perplexity")
        typer.echo("")
    elif len(providers) >= 2:
        typer.echo("現在 active な provider の選び方:")
        typer.echo("- URL 一覧寄りなら serper")
        typer.echo("- 検索+要約なら tavily")
        typer.echo("- 回答中心なら perplexity")
        typer.echo("")
    for provider in providers:
        typer.echo(f"{provider['id']}: {provider['summary']}")
        typer.echo(f"  best for: {provider['best_for']}")
        if provider.get("tradeoffs"):
            typer.echo(f"  tradeoffs: {provider['tradeoffs']}")
        typer.echo(f"  signup: {provider['signup_url']}")
        typer.echo(f"  env: {provider['env_var']}")
        if provider["notes"]:
            typer.echo(f"  notes: {', '.join(provider['notes'])}")
        typer.echo("")


@app.command("doctor")
def doctor_command() -> None:
    try:
        config = load_config()
        checks = []
        for provider in list_providers():
            try:
                secret = require_api_key(provider.id)
                status = {"provider": provider.id, "configured": True, "source": secret.source}
            except SearchCliError:
                status = {"provider": provider.id, "configured": False, "source": None}
            checks.append(status)
        _emit_json(
            {
                "ok": True,
                "config_path": str(CONFIG_PATH),
                "default_provider": config.default_provider,
                "default_format": config.default_format,
                "timeout_seconds": config.timeout_seconds,
                "keyring_backend": keyring_backend_name(),
                "providers": checks,
            }
        )
    except SearchCliError as exc:
        _raise_cli_error(exc)


@app.command("default")
def default_command(
    provider: Annotated[str | None, typer.Argument(help="省略時は現在の default を表示します")]=None,
) -> None:
    try:
        config = load_config()
        active_ids = _active_provider_ids()
        if provider is None:
            _emit_json(
                {
                    "ok": True,
                    "default_provider": config.default_provider,
                    "active_providers": active_ids,
                    "default_is_active": config.default_provider in active_ids,
                    "hint": "変更するには searchcli default <provider> を使います",
                }
            )
            return

        if not active_ids:
            raise SearchCliError(
                code="default_provider_no_active",
                message="default provider を変更するには active provider が必要です。",
                recovery=[
                    "先に searchcli auth set <provider> で API キーを追加する",
                    "詳しくは searchcli providers を見ろ",
                ],
            )

        selected = _validate_default_provider_choice(provider, active_ids)
        path = _persist_default_provider(selected)
        _emit_json(
            {
                "ok": True,
                "config_path": path,
                "default_provider": selected,
                "active_providers": active_ids,
            }
        )
    except SearchCliError as exc:
        _raise_cli_error(exc)


@auth_app.command("set")
def auth_set_command(
    provider: Annotated[str, typer.Argument(help=PROVIDER_HELP)],
    api_key: Annotated[str | None, typer.Option("--api-key", help="指定しない場合は対話入力")]=None,
    default_provider: Annotated[
        str | None,
        typer.Option("--default-provider", help="2 つめ以降の新規追加時に default にする provider を指定します"),
    ] = None,
) -> None:
    try:
        meta = get_provider(provider)
        active_before = _active_provider_ids()
        is_new_provider = meta.id not in active_before
        config_path: str | None = None
        chosen_default: str | None = None

        if not active_before:
            chosen_default = meta.id
        elif is_new_provider:
            default_candidates = [provider.id for provider in list_providers() if provider.id in set(active_before + [meta.id])]
            selected_default = default_provider
            if selected_default is None:
                selected_default = typer.prompt(
                    f"default provider を選択してください ({', '.join(default_candidates)})"
                )
            chosen_default = _validate_default_provider_choice(selected_default, default_candidates)

        secret_value = api_key or typer.prompt(f"{meta.display_name} API key", hide_input=True)
        set_api_key(meta.id, secret_value)

        if not active_before:
            config_path = _persist_default_provider(meta.id)
        elif is_new_provider:
            config_path = _persist_default_provider(chosen_default)

        _emit_json(
            {
                "ok": True,
                "provider": meta.id,
                "stored_in": "keyring",
                "provider_hint": meta.best_for,
                "default_provider": chosen_default,
                "next": [
                    "詳しくは searchcli providers を見ろ",
                    f"searchcli search 'latest {meta.id} api news' --provider {meta.id}",
                    f"環境変数 {env_var_name(meta.id)} があればそちらが優先されます",
                ],
                **({"config_path": config_path} if config_path else {}),
            }
        )
    except SearchCliError as exc:
        _raise_cli_error(exc)


@auth_app.command("clear")
def auth_clear_command(
    provider: Annotated[str, typer.Argument(help=PROVIDER_HELP)],
) -> None:
    try:
        meta = get_provider(provider)
        removed = delete_api_key(meta.id)
        _emit_json({"ok": True, "provider": meta.id, "deleted": removed})
    except SearchCliError as exc:
        _raise_cli_error(exc)


@auth_app.command("where")
def auth_where_command(
    provider: Annotated[str, typer.Argument(help=PROVIDER_HELP)],
) -> None:
    try:
        meta = get_provider(provider)
        secret = require_api_key(meta.id)
        _emit_json({"ok": True, "provider": meta.id, "source": secret.source})
    except SearchCliError as exc:
        _raise_cli_error(exc)


@config_app.command("show")
def config_show_command() -> None:
    try:
        config = load_config()
        _emit_json({"ok": True, "config_path": str(CONFIG_PATH), **config.to_dict()})
    except SearchCliError as exc:
        _raise_cli_error(exc)


@config_app.command("set-default-provider")
def config_set_default_provider_command(
    provider: Annotated[str, typer.Argument(help=PROVIDER_HELP)],
) -> None:
    try:
        meta = get_provider(provider)
        config = load_config()
        config.default_provider = meta.id
        path = save_config(config)
        _emit_json({"ok": True, "config_path": str(path), "default_provider": meta.id})
    except SearchCliError as exc:
        _raise_cli_error(exc)


@config_app.command("set-default-format")
def config_set_default_format_command(
    output_format: Annotated[str, typer.Argument(help="json, jsonl, table")],
) -> None:
    try:
        selected = output_format.lower()
        if selected not in {"json", "jsonl", "table"}:
            raise SearchCliError(
                code="format_invalid",
                message=f"未対応の出力形式です: {output_format}",
                recovery=["json, jsonl, table のいずれかを指定する"],
            )
        config = load_config()
        config.default_format = selected
        path = save_config(config)
        _emit_json({"ok": True, "config_path": str(path), "default_format": selected})
    except SearchCliError as exc:
        _raise_cli_error(exc)


@config_app.command("set-timeout")
def config_set_timeout_command(
    seconds: Annotated[float, typer.Argument(help="既定タイムアウト秒")],
) -> None:
    try:
        if seconds < 1:
            raise SearchCliError(
                code="timeout_invalid",
                message="タイムアウトは 1 秒以上で指定してください。",
                recovery=["例: searchcli config set-timeout 30"],
            )
        config = load_config()
        config.timeout_seconds = seconds
        path = save_config(config)
        _emit_json({"ok": True, "config_path": str(path), "timeout_seconds": seconds})
    except SearchCliError as exc:
        _raise_cli_error(exc)


if __name__ == "__main__":
    app()
