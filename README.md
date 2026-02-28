# 就職活動サポートアプリ (SYUKATSU Support)

合同会社ぼっち向けに構築された、就職活動・企業分析用のデスクトップアプリケーションです。
OpenAIの最新API (`/responses` エンドポイント) と連携し、履歴書作成支援、面接対策、技術面接シミュレーション、および企業レポート(PDF等)の解析（RAG）を行います。

## 主な機能

1. **企業分析アシスタント**
    - OpenAIの最新アーキテクチャモデル（`gpt-5.2` 等）による高度な推論（Reasoning Effort対応）。
    - 履歴書作成支援、面接対策、有報比較など、用途に応じた複数のシステムプロンプトをワンタッチで切り替え。
2. **ナレッジベース管理 (RAG)**
    - 企業のAnnual Reportsや有価証券報告書（PDF/TXT等）をVector Storeへアップロード。
    - `file_search` ツールを通じたセキュアかつ精度の高いドキュメント参照による回答生成。
    - Vector Storeとそれに紐づくファイル群をGUIから直接管理（作成、名前変更、削除、アップロード）。
3. **コスト計算と可視化**
    - APIリクエストのトークン使用量を元に、リアルタイムで概算コスト（USD）を計算してステータスバーに表示。

## アーキテクチャ (The Phoenix Protocol)

本アプリケーションは、**State-Driven Architecture (状態駆動型アーキテクチャ)** を採用し、UI層とビジネスロジック・インフラストラクチャ層を完全に分離しています。これにより、高い保守性と耐障害性（Resilience）を実現しています。

```text
src/
├── app.py              # アプリケーションのエントリーポイント
├── state.py            # (AppState) アプリケーションの状態管理、ビジネスロジック、非同期スレッド管理
├── ui.py               # メインウィンドウ (Tkinter) の純粋なUIレイアウト宣言
├── rag_ui.py           # RAG管理画面 (Tkinter) の純粋なUIレイアウト宣言
├── models.py           # Pydantic V2 スキーマ (ユーザー設定、API入出力の厳密な型定義)
├── styles.py           # UIフォントやカラー設定
├── infrastructure/     # インフラ層 (外部依存関係)
│   ├── openai_client.py # AsyncOpenAI を用いたAPI通信、ストリーミング、RAG管理
│   └── security.py      # Fernet を用いた API Key の暗号化・復号、設定の永続化
├── core/               # コアロジック (UI/インフラに依存しない)
│   ├── errors.py       # APIエラーハンドリング・ユーザー向けメッセージ変換
│   ├── pricing.py      # トークン単価算定のロジック
│   ├── prompts.py      # システムプロンプト定義
│   ├── resilience.py   # Tenacityを用いた非同期リトライデコレータ
│   └── logger.py       # Structlogを用いたログ可視化・構造化設定
└── tests/              # pytest / pytest-asyncio による各コンポーネントのテスト
```

### 重要な設計原則
- **Trinitarian Integrity**: ビジネスロジックと外部通信はすべて `pydantic` モデルを用いた強固な検証を経由します。
- **Resilience**: 一過性のネットワークエラーやレートリミットに対しては `@resilient_api_call` により自動指数バックオフが行われます。
- **No Blocking**: API通信はすべて `asyncio` を用いた別スレッドから実行され、TkinterのメインUIループを決してブロックしません。

## 必要要件

- **OS**: Windows (開発環境)
- **Python**: 3.13 推奨
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (高速なPythonパッケージ/仮想環境管理ツール)
- **API Key**: `OPENAI_API_KEY` (アプリ内から設定して暗号化保存)

## インストールと起動

本プロジェクトでは、依存関係と環境の管理に **uv** を使用します。これにより、環境の構築と実行が完全に自動化・高速化されます。

```powershell
# 初回セットアップ & アプリケーションの起動
uv run src/app.py
```
> ※ `uv run` は自動的に仮想環境を構築し、`pyproject.toml` や `uv.lock` に基づいて依存関係を解決してからアプリを起動します。手動で `pip install` などを実行する必要はありません。

## テストの実行

非同期処理を用いたビジネスロジックおよびモデル定義に対するテストを実行します。

```powershell
uv run pytest tests/ -v
```

## ロギングとデータ保存

- **設定ファイル**:
    APIキーや最後に選択したモデル情報などは暗号化処理され、プロジェクトルートの `config.json` (公開非推奨) および `.secret.key` (鍵ファイル) に安全に保存されます。
- **ログのテキスト保存**:
    アプリ画面の「保存 💾」ボタンから、タイムスタンプ付きのテキストファイルとして応答結果（分析レポート）をローカルに書き出すことができます。
- **構造化ロギング**:
    コンソール出力は `structlog` を経由し、障害調査が容易なタイムスタンプ付きの詳細なコンテキスト（変数状態）を含んで記録されます。
