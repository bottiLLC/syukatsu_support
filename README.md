# 就職活動サポートアプリ (SYUKATSU Support)

合同会社ぼっちが開発した、就職活動・企業分析用のデスクトップアプリケーションです。
最新の **OpenAI API (`/responses` エンドポイント)** とネイティブ連携し、履歴書作成支援、面接対策、技術面接シミュレーション、および企業レポート(PDF等)の解析（RAG）を直感的なGUIから行えます。

## 主な機能

1. **企業分析アシスタント**
    - `gpt-5.4-pro`, `gpt-5.4`, `gpt-5.4-mini` などの最新モデルに完全対応。
    - **Reasoning Effort (推論強度)** の選択により、難解な技術質問や深い分析に対しても高度な推論を実行可能。
    - 履歴書作成支援、面接対策、有報比較など、用途に応じた複数の専用メタプロンプトをプルダウンからワンタッチで切り替え。
2. **ナレッジベース管理 (RAG)**
    - 企業のAnnual Reportsや有価証券報告書（PDF/TXT等）をローカルから直接 OpenAI の Vector Store へアップロード。
    - `file_search` ツールを通じたセキュアかつ精度の高いドキュメント参照による回答生成。
    - Vector Storeとそれに紐づくファイル群を専用の管理画面(GUI)から直接管理（作成、ファイルアップロード、削除）。
3. **コスト計算と可視化**
    - APIリクエストの入力・出力トークン使用量を元に、リアルタイムで概算コスト（USD）を計算してステータスバーに表示。

---

## アーキテクチャ (The Phoenix Protocol)

本アプリケーションは、モダンなGUIフレームワークである **Flet** を採用し、**State-Driven Architecture (状態駆動型アーキテクチャ)** と **Clean Architecture** の設計思想に基づいて構築されています。UI層とビジネスロジックは完全に切り離されています。

```text
src/
├── app.py              # アプリケーションのエントリーポイント (Flet初期化処理)
├── state.py            # (AppState) ViewModel: 状態管理、UseCaseレイヤーへの処理移譲
├── ui.py               # (View) メインウィンドウの純粋なUIレイアウト宣言
├── rag_ui.py           # (View) RAG管理画面のUIコンポーネント
├── models.py           # Pydantic V2 スキーマ (ユーザー設定、API入出力の厳密な型定義)
├── styles.py           # UIフォントやカラーの一元管理
├── application/        # アプリケーション層 (Use Cases)
│   └── usecases/       # UIやインフラに依存しないビジネスロジック群
│       ├── llm_usecase.py # LLM分析の独立実行とストリーミングの一元管理
│       └── rag_usecase.py # ナレッジベース(Vector Store/File)の操作カプセル化
├── infrastructure/     # インフラ層 (外部依存関係)
│   ├── openai_client.py # AsyncOpenAI を用いたAPI通信実装 (v2.3 Responses対応)
│   └── security.py      # Fernet を用いた API Key の暗号化・復号、設定の永続化
├── core/               # コアロジック・ドメイン層 (UI/インフラに依存しない)
│   ├── errors.py       # APIエラーハンドリング・ユーザー向けメッセージ変換
│   ├── pricing.py      # トークン単価算定のロジック
│   ├── prompts.py      # システムプロンプト定義
│   ├── resilience.py   # Tenacityを用いた非同期リトライデコレータ
│   └── logger.py       # Structlogを用いたログ可視化・構造化設定
└── tests/              # pytest / pytest-asyncio による各コンポーネントの非同期テスト
```

### 【設計のポイント】
- **Fletによる非同期UI描画**: PythonネイティブなUI構築とモダンなフラットデザイン。非同期タスク (`page.run_task`) による完全なノンブロッキングUIを実現。
- **Trinitarian Integrity**: データベース定義、Pydantic V2スキーマ、ビジネスロジックが強固に統合されたシリアライズ検証（Schema-Logic Alignment）。
- **Resilient API Calls**: Structlog を用いた構造化ロギングと Tenacity の指数バックオフリトライにより、一過性のネットワーク障害を自動リカバリー。

---

## 必要要件

- **OS**: Windows / macOS / Linux (Windows推奨)
- **Python**: 3.13 以上
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (高速なPythonパッケージ/仮想環境管理ツール)
- **API Key**: `OPENAI_API_KEY` (初回起動時にGUIから登録、暗号化されて安全にローカル保存されます)

---

## 開発・実行手順

本プロジェクトでは、依存関係と環境の管理に **uv** を使用します（`pip` や手動の `venv` 有効化は不要です）。

### 1. アプリケーションの起動
ディレクトリ直下で以下のコマンドを実行するだけで、自動的に依存関係が解決されUIが起動します。

```powershell
uv run src/app.py
```

### 2. 単体テストの実行 (Pytest)
非同期処理およびモデルのシリアライゼーションに対する自動テストを実行します（常にPass率100%を維持）。

```powershell
uv run pytest tests/ -v
```

### 3. 単一実行ファイル (exe) のビルド
PyInstaller を用いて、Python環境が不要な単一の実行可能アプリを作成します。

```powershell
uv run pyinstaller --noconsole --onefile --name syukatsu-support --collect-all src src/app.py -y
```
※ ビルド完了後、`dist` フォルダに `syukatsu-support.exe` が生成されます。ローカルに依存する鍵ファイル(`.secret.key`)等と共に利用してください。

---

## ロギングとデータ保存

- **セキュアな設定管理**:
    APIキーなどの機密情報は内蔵されたFernet方式で暗号化処理され、ローカルの `config.json` と `.secret.key` に安全に保持されます。
- **レポートのエクスポート**:
    画面上の「保存 💾」ボタンから、AIの推論・回答履歴のすべてをタイムスタンプ付きのテキストファイルとしてローカルへ書き出すことができます。
- **構造化ロギング (Structlog)**:
    コンソールには、障害調査が容易なStructlogによるコンテキスト付きログ（変数状態・タイムスタンプ）が出力されます。
