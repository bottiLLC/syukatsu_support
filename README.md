# 就職活動サポートアプリ (SYUKATSU Support)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

合同会社ぼっち向けに構築された、就職活動・企業分析用のデスクトップアプリケーションです。
Google Gemini API (Native Async `client.aio`) と連携し、履歴書作成支援、面接対策、技術面接シミュレーション、および企業レポート(PDF等)の解析（RAG）を行います。

## 主な機能

1. **企業分析アシスタント**
   - Geminiモデル（gemini-3.1-pro-preview 等）による高度な推論（Thinking Level対応）。
   - 用途に応じた複数のシステムプロンプト（履歴書作成、面接対策、技術面接シミュレーション）をワンタッチで切り替え。
2. **ナレッジベース管理 (RAG)**
   - 企業のAnnual Reportsや有価証券報告書（PDF）をVector Storeへアップロード。
   - `file_search` ツールを通じたセキュアかつ精度の高いドキュメント参照による回答生成。
   - Vector Storeとそれに紐づくファイル群をGUIから直接管理（作成、名前変更、削除、アップロード）。
   - **[NEW] 日本語ファイル名のアップロードに完全対応**（内部で自動的にエンコード処理を補完）。
3. **コスト計算と可視化**
   - APIリクエストのトークン使用量を元に、リアルタイムで概算コスト（USD）を計算してステータスバーに表示。

## アーキテクチャ

本アプリケーションは、クリーンアーキテクチャの思想を取り入れ、さらにUI層においては**MVP (Model-View-Presenter)** パターンを採用しています。これにより、Tkinter（GUI）とビジネスロジックが完全に分離され、UIなしでの単体テストが可能となっています。

```text
src/
├── config/             # 環境変数、ユーザー設定 (app_config.py, dependencies.py 等)
├── core/               # ビジネスロジック、データモデル
│   ├── base.py         # Gemini API通信の基盤クラス
│   ├── errors.py       # API例外処理とエラーメッセージの日本語化定義（503 サーバー混雑エラー等に対応）
│   ├── models.py       # Pydantic V2 スキーマ (ユーザー入力/APIストリームレスポンスの厳密な型定義)
│   ├── pricing.py      # トークン単価テーブル
│   ├── prompts.py      # システムプロンプト定義
│   ├── services.py     # Gemini API 通信 (Native Async API), コスト計算
│   └── rag_services.py # Vector Store と File API の操作
├── ui/                 # コアUIコンポーネント (MVPパターン)
│   ├── main_model.py   # アプリ全体のステータス・設定の保持
│   ├── main_view.py    # Tkinter メインウィンドウ構築 (純粋なView)
│   ├── main_presenter.py # ViewとModelを繋ぎ、バックグラウンド処理を管理
│   ├── gui.py          # 上記3つを結合するメインファクトリ (エントリーポイント)
│   ├── rag_model.py    # RAG管理画面のステータス保持
│   ├── rag_view.py     # RAG管理画面 (tk.Toplevel / ttk.PanedWindow) の構築
│   ├── rag_presenter.py  # RAG UIの非同期処理と自動修復例外制御を仲介
│   └── rag_window.py   # RAG管理画面用ファクトリ
└── tests/              # pytest / pytest-asyncio による非同期ユニットテスト/統合テスト
```

## 必要要件

- **OS**: Windows
- **Python**: 3.13推奨
- **API Key**: `GEMINI_API_KEY` (アプリ内から設定、または環境変数)

## インストールと起動

ソースコードから実行する場合は、以下の手順に従ってください。

```bash
# 仮装環境の作成と有効化
python -m venv .venv
.venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt

# アプリケーションの起動
python main.py
```

### Windows用 実行ファイル (EXE) について

Python環境の構築が不要な、単一の実行ファイルによる起動も可能です。
`dist` フォルダ内に生成される `Syukatsu_Support.exe` をダブルクリックするだけでアプリが起動します。

※ 初回起動時はファイルの展開が行われるため、少し時間がかかる場合があります。
※ `.env` ファイルや `config.json` などの設定ファイルは、exeファイルと同じフォルダに配置してご使用ください。

## テストの実行

MVPパターンの完全導入により、Tkinterの画面描画に依存しない純粋な状態管理とバックグラウンド通信のテストが可能になりました。UI検証用の不要なスクリプト群はクリーンアップされています。

```bash
pytest tests/ -v
```

## ロギングとデータ保存

- **設定ファイル**: アプリを実行するとプロジェクトルートに `config.json` が生成されます。APIキーや最後に選択したモデル情報などが安全に保存されます。
- **ログのテキスト保存**: アプリ画面の「保存 💾」ボタンから、タイムスタンプ付きのテキストファイルとして応答結果（分析レポート）をローカルに書き出すことができます。

## ライセンス (License)

Copyright (c) 2026 Botti LLC (Contract LLC Botti)

本ソフトウェアは **GNU General Public License v3.0 (GPLv3)** の下で公開されています。

あなたは以下の権利を有します：

* **使用の自由**: 目的を問わず、本ソフトウェアを使用すること。
* **研究と改変の自由**: 本ソフトウェアのソースコードを研究し、自分のニーズに合わせて改変すること。
* **再配布の自由**: 本ソフトウェアのコピーを（改変の有無に関わらず）再配布すること。

> [!CAUTION]
> **【重要】制約事項（コピーレフト）**: 
> もしあなたが本ソフトウェア（またはその改変版）を再配布する場合、あるいはネットワーク経由でサービスとして提供する場合、そのソースコード全体をGPLv3の下で公開する義務が生じます。これにより、このソフトウェアの自由は下流のユーザーに対しても永久に保証されます。

詳細については、リポジトリに含まれる [LICENSE](LICENSE) ファイル、または [GNU General Public License](https://www.gnu.org/licenses/gpl-3.0.html) を参照してください。

## 免責事項 (Disclaimer)

本ソフトウェアは「現状のまま」提供され、明示または黙示を問わず、いかなる保証も行われません。本ソフトウェアの使用によって生じた、いかなる損害（データの損失、出力情報の誤り、AIのハルシネーション、就職活動への悪影響）についても、作者および著作権者は責任を負いません。ご利用は自己責任でお願いします。
