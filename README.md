# searchcli

構造化された Web 検索を返す、軽量でマルチプラットフォームな CLI です。Serper、Tavily、Perplexity を同じインターフェースで扱い、標準出力は LLM やスクリプトに取り込みやすい JSON を基本にします。

## 特徴

- Python 3.11 以上で動作し、Linux、macOS、Windows で利用可能
- 軽量な依存だけで構成
- 自然な引数構成: `searchcli search "query" --provider tavily --limit 5`
- エラー時は JSON と復旧案を標準エラーへ出力
- API キーは OS キーチェーンへ保存し、環境変数にも対応
- 登録先 URL を `searchcli providers` で確認可能

## どの provider を選ぶか

- serper: 迷ったらこれ。まず URL 一覧を軽く安定して集めたいとき向き
- tavily: URL 一覧に加えて answer も欲しいとき向き。RAG やエージェント用途に相性が良い
- perplexity: URL 一覧より自然文の回答を重視したいとき向き

CLI 上では `searchcli providers` がまず active provider を表示し、active が 0 件のときだけ available 全件へ自動フォールバックします。常に全件を見たいときは `searchcli providers --available` を使います。

## インストール

### pipx

```bash
pipx install .
```

### 仮想環境

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## 最短セットアップ

1. 利用したい API に登録する
2. API キーを保存する
3. 検索する

```bash
searchcli providers
searchcli providers --available
searchcli auth set serper
searchcli search "2026 AI regulation Japan" --provider serper
```

最初の provider を追加したときは、その provider が自動で default になります。2 つめ以降を追加するときは、どれを default にするかをその場で選ばせます。あとから変更したい場合は `searchcli default` と `searchcli default <provider>` を使います。

## アカウント登録先

- Serper: https://serper.dev
- Tavily: https://tavily.com
- Perplexity: https://www.perplexity.ai/settings/api

## 代表コマンド

### 検索

```bash
searchcli search "site:python.org typer cli" --provider serper --limit 5
searchcli search "latest chip export controls" --provider tavily --topic news --search-depth advanced
searchcli search "What changed in Python 3.13 packaging?" --provider perplexity --model sonar
```

`--provider` の目安:

- serper: URL 一覧を機械処理したい
- tavily: 検索結果と answer を両方取りたい
- perplexity: 調査回答をそのまま下流へ渡したい

### JSONL で逐次処理

```bash
searchcli search "vector database benchmarks" --provider tavily --format jsonl
```

### 人向け表示

```bash
searchcli search "edge ai inference trends" --provider serper --format table
```

### 既定値設定

```bash
searchcli default
searchcli default tavily
searchcli config set-default-provider tavily
searchcli config set-default-format json
searchcli config set-timeout 30
```

### 診断

```bash
searchcli doctor
searchcli auth where serper
```

## 出力形式

検索成功時の基本構造:

```json
{
  "ok": true,
  "provider": "serper",
  "query": "site:python.org typer cli",
  "answer": null,
  "results": [
    {
      "title": "Typer",
      "url": "https://typer.tiangolo.com/",
      "snippet": "Typer, build great CLIs...",
      "score": null,
      "source": "typer.tiangolo.com",
      "metadata": {
        "position": 1
      }
    }
  ],
  "warnings": [],
  "auth_source": "keyring"
}
```

失敗時の基本構造:

```json
{
  "ok": false,
  "error": {
    "code": "auth_missing",
    "message": "serper 用の API キーが未設定です。",
    "recovery": [
      "searchcli auth set serper を実行して保存する",
      "または環境変数 SEARCHCLI_SERPER_API_KEY を設定する",
      "searchcli providers で登録先 URL を確認する"
    ]
  }
}
```

## セキュリティ

- API キーは `keyring` 経由で OS キーチェーンへ保存します
- 環境変数 `SEARCHCLI_<PROVIDER>_API_KEY` が設定されている場合はそちらを優先します
- 設定ファイルには秘密情報を保存しません
- Linux でキーチェーン未設定の場合は、`searchcli doctor` でバックエンド名を確認し、必要なら環境変数運用へ切り替えてください

## プロバイダ別メモ

### Serper

- 軽量で結果一覧を取りやすい
- `--region` と `--lang` が使いやすい

### Tavily

- `--topic news` や `--search-depth advanced` に対応
- 回答付きの検索を作りやすい

### Perplexity

- URL 一覧より回答が主になる場合があります
- `--model sonar` などモデル指定が可能です

## LLM 自動化向けの使い方

- 標準出力は `--format json` を既定にできます
- 失敗は標準エラーへ JSON で返るため、再試行や代替プロバイダ選択を組み込みやすいです
- 生レスポンスが必要な場合は `--raw` を使います

## 今後の拡張候補

- Bing、Brave、Exa などの追加
- 期間フィルタやドメイン制約の統一オプション
- `auth test` やキャッシュ機能の追加
