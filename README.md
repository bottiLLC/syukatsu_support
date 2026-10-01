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
- **GPT-6 次世代推論モデル対応**: フラッグシップ推論モデル `gpt-6-astra`、高精度・低コストの `gpt-6.1-sol`、および超高速・大量処理の `gpt-6-luna` の3モデルに完全対応。
- **推論強度（Reasoning Effort）の動的制御**: 課題の難易度に応じて `max`, `xhigh`, `high`, `medium`, `low` を指定可能。非推論モード `none` は `gpt-6-luna` のみ選択可能とするモデル整合性インターロックを内蔵。
- **OpenAI Responses API & RAG 連携**: OpenAI `/responses` エンドポイントをネイティブ採用し、企業の有価証券報告書（PDF）を対象とする Vector Store ファイル検索（`file_search`）とストリーミング分析を実行。
- **整合性検証付き自動バックアップ**: `./data` 配下の暗号化設定および永続データを `testzip()` による破損検知付きアトミックZIPとして保護（`backup_manager.py`）。
- **Windows Store 申請準備完了**: UWP / Desktop Bridge 仕様の `AppxManifest.xml`、5種類のストアアイコンアセット、および自動 MSIX パッケージ生成スクリプト（`package_msix.py` / [WINDOWS_STORE_GUIDE.md](file:///e:/Python/syukatsu_Support/WINDOWS_STORE_GUIDE.md)）を完備。

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
