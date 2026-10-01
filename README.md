# 就職活動サポートアプリ (SYUKATSU Support)

[![CI](https://github.com/bottiLLC/syukatsu_support/actions/workflows/ci.yml/badge.svg)](https://github.com/bottiLLC/syukatsu_support/actions/workflows/ci.yml)
[![Python 3.14 | 3.13](https://img.shields.io/badge/python-3.14%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checker: mypy strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy-lang.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

合同会社ぼっちが開発した、就職活動・企業分析用のデスクトップアプリケーションです。
最新の **OpenAI API (`/responses` エンドポイント)** とネイティブ連携し、履歴書作成支援、面接対策、技術面接シミュレーション、および企業レポート(PDF等)の解析（RAG）を直感的なGUIから行えます。

## 主な機能

1. **企業分析アシスタント (GPT-5.6 シリーズ完全対応)**
    - `gpt-5.6-terra` (標準・推論バランスモデル), `gpt-5.6-sol` (高度推論モデル), `gpt-5.6-luna` (高速・低コストモデル) および `gpt-5.4-pro`, `gpt-5.4` に完全対応。
    - **Reasoning Effort (推論強度: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`)** の選択により、難解な業界・企業分析に対しても高度な推論を実行可能。
    - 履歴書作成支援、面接対策、有報比較など、用途に応じた複数の専用メタプロンプトをプルダウンからワンタッチで切り替え。
2. **ナレッジベース管理 (RAG)**
    - 企業のAnnual Reportsや有価証券報告書（PDF/TXT等）をローカルから直接 OpenAI の Vector Store へアップロード。
    - `file_search` ツールを通じたセキュアかつ精度の高いドキュメント参照による回答生成。
    - Vector Storeとそれに紐づくファイル群を専用の管理画面(GUI)から直接管理（作成、ファイルアップロード、削除）。
3. **データ保護・整合性検証付き自動バックアップ**
    - ユーザー設定、暗号化キー、システムプロンプト等の永続データを `./data/` 配下に完全隔離。
    - `testzip()` による整合性検証付きアトミックZIPアーカイブ生成機能 (`backup_manager.py`) を標準搭載。
    - GUI設定サイドバーから保存先ディレクトリの確認・更新および即時バックアップ実行が可能。
4. **コスト計算と可視化**
    - APIリクエストの入力・出力・キャッシュ済みトークン使用量を元に、リアルタイムで概算コスト（USD）を計算してステータスバーに表示。
5. **初心者向けエラーハンドリング & 直感的なダイアログ UX**
    - **親切なエラーメッセージ**: APIキー未登録・誤り、クレジット残高不足、利用制限(Rate Limit)、タイムアウト、トークン数制限オーバー、アプリ多重起動ロック等が発生した際、初心者が即座に対処できるよう原因と解決策を分かりやすく日本語で表示。
    - **「OK」ボタン付きダイアログ**: APIキー保存時や通知・エラー発生時のすべてのダイアログに「OK」ボタンを配置し、ワンクリックで確実に閉じられる快適な操作性を実現。

---

## アーキテクチャ (The Phoenix Protocol)

本アプリケーションは、モダンなGUIフレームワークである **Flet** を採用し、**State-Driven Architecture (状態駆動型アーキテクチャ)** と **Clean Architecture** の設計思想に基づいて構築されています。UI層とビジネスロジックは完全に切り離されています。

```text
syukatsu_Support/
├── app.py                  # ルート起動エントリーポイント (sys.path確定的解決)
├── backup_manager.py       # データ保護・整合性検証バックアップマネージャー
├── run.bat                 # Windows用ワンクリック自動セットアップ起動スクリプト
├── run.command             # macOS/Linux用ワンクリック自動起動スクリプト
├── data/                   # 永続データ隔離ディレクトリ (Git管理外)
│   ├── config.json         # ユーザー設定
│   ├── .secret.key         # APIキー暗号化用鍵
│   └── system_prompts.json # システムプロンプト定義
├── src/
│   ├── app.py              # アプリケーション初期化・メインループ
│   ├── state.py            # (AppState) ViewModel: 状態管理・リアクティブ通知
│   ├── ui.py               # (View) メインウィンドウUIレイアウト・バックアップ操作
│   ├── rag_ui.py           # (View) RAG管理画面UIコンポーネント
│   ├── models.py           # Pydantic V2 スキーマ (厳密な型定義・シリアライゼーション)
│   ├── styles.py           # UIカラー・スタイリング定数
│   ├── application/        # アプリケーション層 (Use Cases)
│   │   └── usecases/
│   │       ├── llm_usecase.py # LLM分析実行とストリーミング管理
│   │       └── rag_usecase.py # ナレッジベース(Vector Store/File)操作
│   ├── infrastructure/     # インフラ層 (外部依存関係)
│   │   ├── openai_client.py   # AsyncOpenAI を用いたAPI通信実装
│   │   └── security.py        # Fernet暗号化・./data への設定永続化管理
│   └── core/               # コアロジック・ドメイン層
│       ├── errors.py       # APIエラーメッセージ変換
│       ├── pricing.py      # トークン単価算定ロジック
│       ├── prompts.py      # プロンプトローダー
│       ├── resilience.py   # Tenacity指数バックオフリトライ
│       ├── logger.py       # Structlog構造化ロギング
│       └── utils.py        # パス解決・引用マーカー除去
└── tests/                  # pytest / pytest-asyncio による包括的単体テスト群
```

---

## 必要要件

- **OS**: Windows / macOS / Linux (Windows推奨)
- **Python**: 3.13 または 3.14 以上
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (高速なPythonパッケージ/仮想環境管理ツール)
- **API Key**: `OPENAI_API_KEY` (初回起動時にGUIから登録、暗号化されて安全にローカル保存されます)

---

## 開発・実行手順

本プロジェクトでは、依存関係と環境の管理に **uv** を使用します（`pip` や手動の `venv` 有効化は不要です）。

### 1. アプリケーションの起動

**ワンクリック起動 (推奨)**:
- **Windows**: `run.bat` をダブルクリックします。
- **Mac/Linux**: ターミナルで `chmod +x run.command` を実行した後、`run.command` をダブルクリックします。

**コマンドラインでの起動**:
```powershell
uv run app.py
```

### 2. 品質検証・静的解析・テストの実行

本プロジェクトは CI/CD パイプラインと完全に同期したローカル検証環境を提供します。

```powershell
# 1. Ruff による静的解析と自動修正
uv run ruff check .

# 2. Ruff によるコードフォーマット検証
uv run ruff format --check .

# 3. Mypy による厳格な静的型検査 (Strict Type Checking)
uv run mypy src app.py backup_manager.py

# 4. Pytest による単体テストおよびブランチカバレッジ計測
uv run pytest
```

### 3. アプリケーションのビルド (単一ファイル .exe 化)

PyInstaller を用いて、Python環境が不要な単一の実行可能ファイル（`dist/syukatsu-support.exe`）を作成します。

```powershell
uv run python build.py
```

※ ビルド完了後、`dist/` フォルダ内に単一の実行ファイル `syukatsu-support.exe` が生成されます。

---

## ロギング・データ保存・バックアップ

- **セキュアなデータ隔離 (`./data`)**:
    APIキーなどの機密設定は内蔵されたFernet方式で暗号化処理され、プロジェクト内の `./data/` 配下 (`config.json`, `.secret.key`, `system_prompts.json`) に厳格に隔離保持されます。
- **整合性検証付き自動バックアップ (`backup_manager.py`)**:
    バックアップ実行時は一時ファイル経由のアトミックなZIP生成を行い、ZIP内のCRC32を検証する `testzip()` を通過したアーカイブのみを確定保存します。
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
