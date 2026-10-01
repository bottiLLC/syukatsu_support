# Local Workspace Rules: SYUKATSU Support (`syukatsu_Support`)

## Global Rule Precedence & Exception Clause

> [!IMPORTANT]
> **Priority Override Directive**:
> The rules declared in this document represent workspace-level local directives and **STRICTLY TAKE PRECEDENCE** over conflicting instructions in global rules (including `<RULE[user_global]>` and the `Python-backup-script` skill).

### 1. Data Protection & Automated Backup Exemption
- **Exception Invariant**:
  このアプリケーション（就職活動サポート AI / `syukatsu_Support`）は、OpenAI Responses API および Vector Store（`file_search`）と直接対話するデスクトップ対話型分析ツールです。
  ユーザー作成のトランザクションデータ、ローカルデータベース、または保全対象の動的永続データは存在しないため、**例外的にデータ保護・自動バックアップ機能は使用しません**。
- **Strict Exemption from Global Backup Mandate**:
  - グローバルルールにある「Persistent Data & Automated Backup Mandate」およびスキル「`Python-backup-script`」の要件は、本プロジェクトにおいて**完全に免除（除外）**されます。
  - `backup_manager.py` や自動 ZIP バックアップルーチン、整合性検証ロジック（`testzip()` 等）を本リポジトリに再生成・追加することは厳格に禁止します。
  - `src/ui.py` や各種 UI モジュールにバックアップ関連の UI 要素（保存先フォルダ設定、バックアップ実行ボタン、ステータス表示等）を追加・実装することは禁止します。
- **Clean Architecture & Lean Codebase**:
  - `./data` 配下の設定ファイル（`config.json`, `system_prompts.json` 等）はテンプレートおよび軽量な設定情報のみを保持し、冗長なバックアップ管理コードを排したクリーンな構成を維持します。
