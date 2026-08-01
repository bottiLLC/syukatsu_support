# 就職活動サポートアプリ (SYUKATSU Support)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

合同会社ぼっちが開発した、就職活動・企業分析用のデスクトップアプリケーションです。
最新の **OpenAI API (`/responses` エンドポイント)** とネイティブ連携し、履歴書作成支援、面接対策、技術面接シミュレーション、および企業レポート(PDF等)の解析（RAG）を直感的なGUIから行えます。

## 主な機能

1. **企業分析アシスタント (GPT-5.6 シリーズ完全対応)**
    - `gpt-5.6-terra` (標準・推論バランスモデル), `gpt-5.6-sol` (高度推論モデル), `gpt-5.6-luna` (高速・低コストモデル) および `gpt-5.4-pro`, `gpt-5.4` に完全対応。
    - **Reasoning Effort (推論強度: `high`, `medium`, `low`, `xhigh`)** の選択により、難解な業界・企業分析に対しても高度な推論を実行可能。
    - 履歴書作成支援、面接対策、有報比較など、用途に応じた複数の専用メタプロンプトをプルダウンからワンタッチで切り替え。
2. **ナレッジベース管理 (RAG)**
    - 企業のAnnual Reportsや有価証券報告書（PDF/TXT等）をローカルから直接 OpenAI の Vector Store へアップロード。
    - `file_search` ツールを通じたセキュアかつ精度の高いドキュメント参照による回答生成。
    - Vector Storeとそれに紐づくファイル群を専用の管理画面(GUI)から直接管理（作成、ファイルアップロード、削除）。
3. **コスト計算と可視化**
    - APIリクエストの入力・出力・キャッシュ済みトークン使用量を元に、リアルタイムで概算コスト（USD）を計算してステータスバーに表示。
4. **初心者向けエラーハンドリング & 直感的なダイアログ UX**
    - **親切なエラーメッセージ**: APIキー未登録・誤り、クレジット残高不足、利用制限(Rate Limit)、タイムアウト、トークン数制限オーバー、アプリ多重起動ロック等が発生した際、初心者が即座に対処できるよう原因と解決策を分かりやすく日本語で表示。
    - **「OK」ボタン付きダイアログ**: APIキー保存時（「設定完了 APIキーを保存しました。」）や通知・エラー発生時のすべてのダイアログに「OK」ボタンを配置し、ワンクリックで確実に閉じられる快適な操作性を実現。

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
- **Python**: 3.14 以上
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (高速なPythonパッケージ/仮想環境管理ツール)
- **API Key**: `OPENAI_API_KEY` (初回起動時にGUIから登録、暗号化されて安全にローカル保存されます)

---

## 開発・実行手順

本プロジェクトでは、依存関係と環境の管理に **uv** を使用します（`pip` や手動の `venv` 有効化は不要です）。

### 1. アプリケーションの起動

**ワンクリック起動 (推奨)**:
- **Windows**: `run.bat` をダブルクリックします。
- **Mac/Linux**: ターミナルで `chmod +x run.command` を実行した後、`run.command` をダブルクリック（またはスクリプト実行）します。

**コマンドラインでの起動**:
```powershell
uv run src/app.py
```

### 2. 単体テストの実行 (Pytest)
非同期処理およびモデルのシリアライゼーションに対する自動テストを実行します（常にPass率100%を維持）。

```powershell
uv run pytest tests/ -v
```

### 3. アプリケーションのビルド (単一ファイル .exe 化)
PyInstaller を用いて、Python環境が不要な単一の実行可能ファイル（`dist/syukatsu-support.exe`）を作成します。
Flet および Flet-Desktop の全バイナリリソースが1つの `.exe` 内に完全にバンドルされるため、配布や実行が容易です。

**ビルド自動化スクリプトでの実行 (推奨)**:
```powershell
uv run python build.py
```

**コマンドラインで直接実行する場合**:
```powershell
uv run pyinstaller --noconsole --onefile --name syukatsu-support --collect-all flet --collect-all flet_desktop --collect-all src --add-data "system_prompts.json;." src/app.py -y
```
※ ビルド完了後、`dist/` フォルダ内に単一の実行ファイル `syukatsu-support.exe` が生成されます。この `.exe` ファイル単体で他のPC環境でもダブルクリックで直接起動できます。

---

## ロギング・データ保存・サポート

- **セキュアな設定管理 (LocalAppdata連携)**:
    APIキーなどの機密設定は内蔵されたFernet方式で暗号化処理され、クラウドドキュメント等の同期エラーを防ぐため、OS標準の `%LOCALAPPDATA%\SYUKATSU_Support` 配下 (`config.json`, `.secret.key`) に安全に保持されます。
- **レポートのエクスポート**:
    画面上の「保存 💾」ボタンから、AIの推論・回答履歴のすべてをタイムスタンプ付きのテキストファイルとして書き出すことができます。
- **初心者向けエラーガイドと開発者サポート**:
    各種OpenAI APIエラーやアプリ多重起動ロックが発生した際、ダイアログ上に原因と具体的対処法を初心者向け日本語で表示します。また、ダイアログからエラーログをテキスト保存したり、メールで開発者へ報告するためのサポート機能も備えています。
- **構造化ロギング (Structlog)**:
    コンソールやバックグラウンド処理では、障害調査が容易なStructlogによるコンテキスト付きログ（変数状態・タイムスタンプ）が出力されます。

---

## 免責事項・コストに関する強い警告 (Disclaimer & API Costs)

> **【⚠️ 警告：完全自己責任での利用について ⚠️】**
> 
> 本アプリは OpenAI の API を使用するため、ユーザー自身での **APIキー取得とクレジットカード登録が必須** です。
> 
> 本アプリは**従量課金制**です。特に上位モデル（例: `gpt-5.6-sol`, `gpt-5.4-pro`等）を選択して**巨大なPDF（有価証券報告書など）** を分析した場合、膨大なトークンが消費され、**高額なAPI費用が発生するリスク**があります。
> 
> アプリの使用によって生じたAPIの課金額や、実行時のいかなる損害・エラーに対しても、**開発者（合同会社ぼっち / bottiLLC）は一切の責任を負いません。完全に「自己責任」でのご利用**となりますので、トークンの使用量やモデル選択には十分ご注意ください。

---

## プライバシーポリシー (Privacy Policy)

本アプリ内でのデータは全て利用者のデバイス上で暗号化して管理され、OpenAIとの直接通信のみに用いられます。送信されるデータはモデルの学習に利用されません。詳細についてはリポジトリ内の [PRIVACY_POLICY.md](./PRIVACY_POLICY.md) をご確認ください。

---

## ライセンス (License)

本ソフトウェアは **GNU General Public License v3.0 (GPL-3.0)** の下で公開されています。

著作権者: **合同会社ぼっち (bottiLLC)**

ソースコードの改変・再配布を行う場合は、同一のGPL-3.0ライセンスを適用する義務があります。詳細はリポジトリ内の `LICENSE` ファイル、または[GNU公式ライセンス](https://www.gnu.org/licenses/gpl-3.0.html)をご確認ください。
