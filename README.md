# 就職活動サポートアプリ (SYUKATSU Support)

合同会社ぼっち向けに構築された、就職活動・企業分析用のデスクトップアプリケーションです。
OpenAIの最新API (`/responses` エンドポイント) と連携し、履歴書作成支援、面接対策、技術面接シミュレーション、および企業レポート(PDF等)の解析（RAG）を行います。

## 主な機能

1. **企業分析アシスタント**
   - OpenAIモデル（GPT-5.2等）による高度な推論（Reasoning Effort対応）。
   - 用途に応じた複数のシステムプロンプト（履歴書作成、面接対策、技術面接シミュレーション）をワンタッチで切り替え。
2. **ナレッジベース管理 (RAG)**
   - 企業のAnnual Reportsや有価証券報告書（PDF）をVector Storeへアップロード。
   - `file_search` ツールを通じたセキュアかつ精度の高いドキュメント参照による回答生成。
   - Vector Storeとそれに紐づくファイル群をGUIから直接管理（作成、名前変更、削除、アップロード）。
3. **コスト計算と可視化**
   - APIリクエストのトークン使用量を元に、リアルタイムで概算コスト（USD）を計算してステータスバーに表示。

## アーキテクチャ

本アプリケーションは、クリーンアーキテクチャの思想を取り入れ、さらにUI層においては**MVP (Model-View-Presenter)** パターンを採用しています。これにより、Tkinter（GUI）とビジネスロジックが完全に分離され、UIなしでの単体テストが可能となっています。

```text
src/
├── config/             # 環境変数、ユーザー設定 (app_config.py, dependencies.py 等)
├── core/               # ビジネスロジック、データモデル
│   ├── base.py         # AsyncOpenAI通信の基盤クラス
│   ├── errors.py       # API例外処理とエラーメッセージの日本語化定義（UI例外検知）
│   ├── models.py       # Pydantic V2 スキーマ (ユーザー入力/APIストリームレスポンスの厳密な型定義)
│   ├── pricing.py      # トークン単価テーブル
│   ├── prompts.py      # システムプロンプト定義
│   ├── services.py     # OpenAI API 通信 (`/responses`エンドポイント API), コスト計算
│   └── rag_services.py # Vector Store と File API の操作
├── ui/                 # コアUIコンポーネント (MVPパターン)
│   ├── main_model.py   # アプリ全体のステータス・設定の保持
│   ├── main_view.py    # Tkinter メインウィンドウ構築 (純粋なView)
│   ├── main_presenter.py # ViewとModelを繋ぎ、バックグラウンド処理を管理
│   ├── gui.py          # 上記3つを結合するメインファクトリ (エントリーポイント)
│   ├── rag_model.py    # RAG管理画面のステータス保持
│   ├── rag_view.py     # RAG管理画面 (tk.Toplevel) の構築
│   ├── rag_presenter.py  # RAG UIの非同期処理とAPI呼び出しを仲介
│   └── styles.py       # アプリケーション全体のUIスタイリング
└── tests/              # pytest / pytest-asyncio による非同期ユニットテスト/統合テスト
```

## 必要要件

- **OS**: Windows
- **Python**: 3.13推奨
- **API Key**: `OPENAI_API_KEY` (アプリ内から設定、または環境変数)

## インストールと起動

```bash
# 仮装環境の作成と有効化
python -m venv .venv
.venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt

# アプリケーションの起動
python main.py
```

## テストの実行

Mvpパターンの導入により、`tests/test_mvp_presenters.py` にて、Tkinterの画面に依存しない純粋な状態管理とバックグラウンド通信のテストが可能です。

```bash
pytest tests/ -v
```

## ロギングとデータ保存

- **設定ファイル**: アプリを実行するとプロジェクトルートに `config.json` が生成されます。APIキーや最後に選択したモデル情報などが安全に保存されます。
- **ログのテキスト保存**: アプリ画面の「保存 💾」ボタンから、タイムスタンプ付きのテキストファイルとして応答結果（分析レポート）をローカルに書き出すことができます。
