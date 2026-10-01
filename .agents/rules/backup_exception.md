# Data Protection & Automated Backup Exemption

> [!IMPORTANT]
> This local rule takes precedence over `<RULE[user_global]>` and `Python-backup-script`.

- **Exemption Rule**:
  このアプリケーションはデータ保護・バックアップをする動的永続データが存在しないため、例外的にデータ保護・バックアップ機能（`Python-backup-script` / `backup_manager.py`）を使用しません。
- **Directives**:
  - `backup_manager.py` および自動バックアップロジックを実装・生成しないこと。
  - UI にバックアップ関連の設定および操作ウィジェットを配置しないこと。
