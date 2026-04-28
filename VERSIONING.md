# Versioning Policy

searchcli は Semantic Versioning を使います。

## Tag Rule

- Git tag format: `vX.Y.Z`
- package version format: `X.Y.Z`
- 初期公開版: `0.1.2`

## Meaning

- `MAJOR`: 互換性を壊す CLI / MCP / 出力仕様の変更
- `MINOR`: 後方互換な機能追加
- `PATCH`: 後方互換な不具合修正、ドキュメント修正、軽微な改善

## Pre-1.0 Rule

`0.y.z` の間は API と tool surface がまだ固まっていない前提です。ただし、tag を打った version に対しては変更内容を `CHANGELOG.md` に明記します。

## Release Rule

1. version を `pyproject.toml` と `src/searchcli/__init__.py` に反映する
2. `CHANGELOG.md` を更新する
3. `vX.Y.Z` タグを push する
4. GitHub Actions が PyPI publish を行う
5. 同じ tag version を使って MCP Registry publish を行う