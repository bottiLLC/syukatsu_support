# 就職活動サポート AI (SYUKATSU Support)

![CI](https://img.shields.io/badge/CI-passed-green)
![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)
![Flet](https://img.shields.io/badge/Flet-0.82.2-blue.svg)
![License](https://img.shields.io/badge/License-Private-red.svg)

## Overview
有価証券報告書等の開示資料や企業ドキュメントを最新のOpenAI推論モデルで分析し、財務・人的資本・志望動機戦略レポートを生成するデスクトップAI就活支援ツールです。Windows Store（Microsoft Store）申請用のMSIXおよびネイティブWin32パッケージングに対応しています。

## Quick Start (TL;DR)
```bash
uv sync
uv run python app.py
uv run python package_msix.py
```

## Architecture & Features
- **かんたんモードと定型3大分析**: 初心者向けのワンクリック分析（財務分析・人的資本分析・志望動機検討）を搭載し、分析ごとにコンテキストを完全初期化して独立したレポートを生成。
- **GPT-6 次世代推論モデル & 動的インターロック**: フラッグシップ `gpt-6-astra`、標準モデル `gpt-6.1-sol`、超高速 `gpt-6-luna` に対応し、モデル特性に応じた推論強度（`none`〜`max`）の動的検証を実施。
- **OpenAI Responses API & RAG 連携**: `/responses` エンドポイントをネイティブ採用し、企業の有価証券報告書（PDF）に対する Vector Store（`file_search`）検索とストリーミング分析を実行。
- **全OpenAI APIエラーの日本語ガイダンス**: 401（認証）、429（クォータ超過・レート制限）、503（サーバー過負荷）等の全APIエラーを網羅し、原因と即時対処手順を日本語で明示。
- **レポート出力 & Windows Store 申請準備**: 分析結果の Word (`.docx`) / テキスト (`.txt`) 出力、および UWP / Desktop Bridge 仕様の `AppxManifest.xml` と自動 MSIX 生成スクリプトを完備。

## Environment Variables
| 環境変数名 | デフォルト / 設定例 | 説明 |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | `sk-proj-...` | OpenAI API接続用シークレットキー。未設定時はアプリGUIから暗号化登録可能。 |
| `APP_LOG_LEVEL` | `INFO` | アプリケーションのログ出力レベル（`DEBUG`, `INFO`, `WARNING`, `ERROR`）。 |

## Limits & Known Trade-offs
- **API従量課金とコスト管理**: `gpt-6-astra` による大規模PDFの深い推論（`max`/`xhigh`）は大量のトークンを消費します。アプリ下部にリアルタイム概算コスト（USD）が表示されますが、OpenAIダッシュボードでの利用上限設定を併用してください。
- **推論強度 'none' の制約**: OpenAI仕様に基づき、`gpt-6-astra` および `gpt-6.1-sol` では `none` 推論強度は利用できません（`gpt-6-luna` のみ利用可能）。
- **Microsoft Partner Center 申請時の署名**: 生成された `dist/syukatsu-support.msix` は、Partner Center 提出時に Microsoft により正規署名されます。ローカル端末での手動サイドローディング検証を行う場合は、テスト用自己署名証明書のインポートが必要です。

---

Copyright (c) LLC Bocchi. All rights reserved.
