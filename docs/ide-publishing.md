# IDE Publishing Guide

searchcli を主要 IDE に公開または配布するための最小セットです。

## 対象

- VS Code
- Claude Code
- Windsurf
- Cursor
- Official MCP Registry

## 公開前チェック

1. `pyproject.toml`, `src/searchcli/__init__.py`, `CHANGELOG.md` の version を揃える
2. `uvx searchcli mcp` がローカルで起動することを確認する
3. 少なくとも 1 つの provider API key で `search` tool が通ることを確認する
4. `vX.Y.Z` タグを push する

## VS Code

workspace 共有設定は `.vscode/mcp.json` を使います。

ローカル開発中はリポジトリの `.venv` と `src` を使う設定で問題ありません。PyPI 公開後に配布用サンプルへ寄せるなら次のようにできます。

```json
{
  "servers": {
    "searchcli": {
      "type": "stdio",
      "command": "uvx",
      "args": ["searchcli", "mcp"],
      "env": {
        "SEARCHCLI_SERPER_API_KEY": "${input:searchcli-serper-api-key}",
        "SEARCHCLI_TAVILY_API_KEY": "${input:searchcli-tavily-api-key}",
        "SEARCHCLI_PERPLEXITY_API_KEY": "${input:searchcli-perplexity-api-key}"
      }
    }
  }
}
```

secret は `inputs` の `promptString` と `password: true` を使います。

## Claude Code

Claude Code は project scope ならリポジトリ直下の `.mcp.json` を共有できます。公開済みパッケージを使う場合の追加コマンドは次です。

```bash
claude mcp add --transport stdio --scope project \
  --env SEARCHCLI_SERPER_API_KEY=$SEARCHCLI_SERPER_API_KEY \
  --env SEARCHCLI_TAVILY_API_KEY=$SEARCHCLI_TAVILY_API_KEY \
  --env SEARCHCLI_PERPLEXITY_API_KEY=$SEARCHCLI_PERPLEXITY_API_KEY \
  searchcli -- uvx searchcli mcp
```

または `.mcp.json` に次を置けます。

```json
{
  "mcpServers": {
    "searchcli": {
      "command": "uvx",
      "args": ["searchcli", "mcp"],
      "env": {
        "SEARCHCLI_SERPER_API_KEY": "${SEARCHCLI_SERPER_API_KEY:-}",
        "SEARCHCLI_TAVILY_API_KEY": "${SEARCHCLI_TAVILY_API_KEY:-}",
        "SEARCHCLI_PERPLEXITY_API_KEY": "${SEARCHCLI_PERPLEXITY_API_KEY:-}"
      }
    }
  }
}
```

## Windsurf

Windsurf は `~/.codeium/windsurf/mcp_config.json` を使います。

```json
{
  "mcpServers": {
    "searchcli": {
      "command": "uvx",
      "args": ["searchcli", "mcp"],
      "env": {
        "SEARCHCLI_SERPER_API_KEY": "${env:SEARCHCLI_SERPER_API_KEY}",
        "SEARCHCLI_TAVILY_API_KEY": "${env:SEARCHCLI_TAVILY_API_KEY}",
        "SEARCHCLI_PERPLEXITY_API_KEY": "${env:SEARCHCLI_PERPLEXITY_API_KEY}"
      }
    }
  }
}
```

Windsurf の team 配布では custom registry または whitelist で `uvx searchcli mcp` を許可対象に入れる運用が現実的です。

## Cursor

Cursor では MCP 設定自体は stdio command と args を渡す形で共通です。バージョン差分が大きいため、配布資料では次の最小サンプルを出すのが安全です。

```json
{
  "mcpServers": {
    "searchcli": {
      "command": "uvx",
      "args": ["searchcli", "mcp"],
      "env": {
        "SEARCHCLI_SERPER_API_KEY": "${env:SEARCHCLI_SERPER_API_KEY}",
        "SEARCHCLI_TAVILY_API_KEY": "${env:SEARCHCLI_TAVILY_API_KEY}",
        "SEARCHCLI_PERPLEXITY_API_KEY": "${env:SEARCHCLI_PERPLEXITY_API_KEY}"
      }
    }
  }
}
```

Cursor 側で env interpolation が弱い環境では、wrapper script で環境を読み込んでから `uvx searchcli mcp` を実行させる運用に寄せます。

## Official MCP Registry

このリポジトリには `server.json` を同梱しています。release workflow が tag version を使って一時的に `server.json` の version を合わせ、そのまま official registry publish まで流す前提です。

`server.json` の現状の前提は次です。

- package registry: PyPI
- package identifier: `searchcli`
- runtime hint: `uvx`
- transport: stdio
- package argument: `mcp`

つまりクライアントから見た起動形は `uvx searchcli mcp` です。

## 配布メッセージの最小形

各 IDE へ公開するときは次を短く案内すると伝わりやすいです。

1. searchcli は web search 用の stdio MCP server
2. install command は `uvx searchcli mcp`
3. secrets は `SEARCHCLI_SERPER_API_KEY` などの環境変数で渡す
4. tools は `search`, `providers`, `doctor`