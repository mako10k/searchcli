from searchcli import cli as cli_module
from searchcli.config import AppConfig
from typer.testing import CliRunner

from searchcli.cli import app
from searchcli.secrets import SecretLookup


runner = CliRunner()


def test_help_works() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "構造化された web 検索" in result.stdout

    search_help = runner.invoke(app, ["search", "--help"])
    assert search_help.exit_code == 0
    assert "URL 一覧重視" in search_help.stdout
    assert "searchcli providers" in search_help.stdout


def test_providers_json() -> None:
    result = runner.invoke(app, ["providers", "--available", "--format", "json"])
    assert result.exit_code == 0
    assert '"scope": "available"' in result.stdout
    assert '"serper"' in result.stdout
    assert '"tavily"' in result.stdout
    assert '"perplexity"' in result.stdout
    assert '"best_for"' in result.stdout


def test_providers_table_guides_selection_when_available() -> None:
    result = runner.invoke(app, ["providers", "--available"])
    assert result.exit_code == 0
    assert "view: available" in result.stdout
    assert "迷ったら serper" in result.stdout
    assert "検索と要約を両方ほしいなら tavily" in result.stdout
    assert "回答中心で使うなら perplexity" in result.stdout


def test_providers_default_shows_only_active_without_tradeoffs_when_single(monkeypatch) -> None:
    def fake_get_api_key(provider: str) -> SecretLookup:
        if provider == "tavily":
            return SecretLookup(api_key="dummy", source="keyring")
        return SecretLookup(api_key=None, source=None)

    monkeypatch.setattr(cli_module, "get_api_key", fake_get_api_key)
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "view: active" in result.stdout
    assert "tavily:" in result.stdout
    assert "serper:" not in result.stdout
    assert "perplexity:" not in result.stdout
    assert "tradeoffs:" not in result.stdout


def test_providers_default_falls_back_to_available_when_no_active(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "get_api_key", lambda provider: SecretLookup(api_key=None, source=None))
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "view: available" in result.stdout
    assert "active provider が 0 件のため available を表示しています。" in result.stdout


def test_active_pair_tradeoffs_are_contextual(monkeypatch) -> None:
    def fake_get_api_key(provider: str) -> SecretLookup:
        if provider in {"serper", "tavily"}:
            return SecretLookup(api_key="dummy", source="keyring")
        return SecretLookup(api_key=None, source=None)

    monkeypatch.setattr(cli_module, "get_api_key", fake_get_api_key)
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "serper:" in result.stdout
    assert "tavily:" in result.stdout
    assert "perplexity:" not in result.stdout
    assert "tavily と比べて、URL 一覧を軽く素早く集めたいとき向き。" in result.stdout
    assert "serper と比べて、検索結果に加えて answer や深めの要約も欲しいとき向き。" in result.stdout


def test_auth_set_outputs_provider_guidance(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "_active_provider_ids", lambda: ["tavily"])
    monkeypatch.setattr(cli_module, "set_api_key", lambda provider, api_key: None)
    result = runner.invoke(app, ["auth", "set", "tavily", "--api-key", "dummy-key"])
    assert result.exit_code == 0
    assert '"provider_hint": "検索結果と要約を両方ほしいとき。RAG やエージェント用途向き。"' in result.stdout
    assert '"詳しくは searchcli providers を見ろ"' in result.stdout


def test_default_command_shows_current_default(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "load_config", lambda: AppConfig(default_provider="tavily"))
    monkeypatch.setattr(cli_module, "_active_provider_ids", lambda: ["tavily", "serper"])
    result = runner.invoke(app, ["default"])
    assert result.exit_code == 0
    assert '"default_provider": "tavily"' in result.stdout
    assert '"default_is_active": true' in result.stdout


def test_default_command_sets_active_provider(monkeypatch) -> None:
    saved: dict[str, str] = {}

    monkeypatch.setattr(cli_module, "_active_provider_ids", lambda: ["serper", "tavily"])
    monkeypatch.setattr(
        cli_module,
        "_persist_default_provider",
        lambda provider_id: saved.update({"provider": provider_id}) or "/tmp/config.json",
    )
    result = runner.invoke(app, ["default", "tavily"])
    assert result.exit_code == 0
    assert saved["provider"] == "tavily"
    assert '"default_provider": "tavily"' in result.stdout


def test_auth_set_first_provider_initializes_default(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "_active_provider_ids", lambda: [])
    monkeypatch.setattr(cli_module, "set_api_key", lambda provider, api_key: None)
    monkeypatch.setattr(cli_module, "_persist_default_provider", lambda provider_id: "/tmp/config.json")
    result = runner.invoke(app, ["auth", "set", "tavily", "--api-key", "dummy-key"])
    assert result.exit_code == 0
    assert '"default_provider": "tavily"' in result.stdout


def test_auth_set_second_provider_requires_default_selection(monkeypatch) -> None:
    saved: dict[str, str] = {}

    monkeypatch.setattr(cli_module, "_active_provider_ids", lambda: ["serper"])
    monkeypatch.setattr(cli_module, "set_api_key", lambda provider, api_key: None)
    monkeypatch.setattr(
        cli_module,
        "_persist_default_provider",
        lambda provider_id: saved.update({"provider": provider_id}) or "/tmp/config.json",
    )
    result = runner.invoke(app, ["auth", "set", "tavily", "--api-key", "dummy-key"], input="serper\n")
    assert result.exit_code == 0
    assert saved["provider"] == "serper"
    assert '"default_provider": "serper"' in result.stdout


def test_auth_set_second_provider_accepts_explicit_default_provider(monkeypatch) -> None:
    saved: dict[str, str] = {}

    monkeypatch.setattr(cli_module, "_active_provider_ids", lambda: ["serper"])
    monkeypatch.setattr(cli_module, "set_api_key", lambda provider, api_key: None)
    monkeypatch.setattr(
        cli_module,
        "_persist_default_provider",
        lambda provider_id: saved.update({"provider": provider_id}) or "/tmp/config.json",
    )
    result = runner.invoke(
        app,
        ["auth", "set", "tavily", "--api-key", "dummy-key", "--default-provider", "tavily"],
    )
    assert result.exit_code == 0
    assert saved["provider"] == "tavily"
    assert '"default_provider": "tavily"' in result.stdout
