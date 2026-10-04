# Windows Store (Microsoft Store) 申請・公開ガイド

本ドキュメントは、「就職活動サポート AI」を Microsoft Partner Center 経由で Windows Store（Microsoft Store）に申請・公開するための標準手順書です。

---

## 1. 事前準備 (Microsoft Partner Center)

1. **Microsoft デベロッパーアカウントの作成**:
   - [Microsoft Partner Center](https://partner.microsoft.com/dashboard) にアクセスし、開発者登録（個人または組織）を完了します。
2. **アプリ名の予約**:
   - ダッシュボードの「アプリとゲーム」から「新しいアプリを作成」をクリックし、アプリ名（例: `就職活動サポート AI` または `Syukatsu Support AI`）を予約します。
3. **パッケージ ID 情報の取得**:
   - 予約後、「製品の管理」→「パッケージ ID」ページに表示される以下の3つの情報を確認します:
     - **パッケージ名 (Package/Identity/Name)**
     - **パブリッシャー (Package/Identity/Publisher)**（例: `CN=XXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`）
     - **パブリッシャー表示名 (PublisherDisplayName)**

---

## 2. マニフェスト設定の同期

[AppxManifest.xml](file:///e:/Python/syukatsu_Support/AppxManifest.xml) を開き、Partner Center で取得した情報に更新します。

```xml
  <Identity
    Name="<Partner Centerで割り当てられたパッケージ名>"
    Publisher="<Partner Centerで割り当てられたパブリッシャーCN>"
    Version="1.0.0.0"
    ProcessorArchitecture="x64" />

  <Properties>
    <DisplayName>就職活動サポート AI</DisplayName>
    <PublisherDisplayName><Partner Centerに登録されたパブリッシャー名></PublisherDisplayName>
    <Logo>assets\StoreLogo.png</Logo>
    <Description>有価証券報告書等の分析・志望動機作成を支援するAI就活アシスタントデスクトップアプリ</Description>
  </Properties>
```

---

## 3. パッケージの自動ビルド

本リポジトリには、Windows Store 向け成果物を一括生成するスクリプトが用意されています。

```bash
# 1. 依存関係のセットアップ
uv sync

# 2. Windows Store パッケージ (MSIX) の生成
uv run python package_msix.py
```

実行が完了すると、`dist/` ディレクトリ配下に以下の成果物が生成されます:
- `dist/syukatsu-support.msix`: Windows Store 提出用 MSIX パッケージ
- `dist/msix_stage/`: MSIX Packaging Tool や Windows SDK 手動ビルド用の完全なステージング構造
- `dist/syukatsu-support.exe`: スタンドアロン実行可能バイナリ

> [!WARNING]
> **ローカルで `.msix` をダブルクリックした際に「アプリ パッケージの解析中にエラーが発生しました」と表示される原因**:
> 1. **MakeAppx.exe（Windows SDK）の未検出**: Windows の App Installer は、内部に `AppxBlockMap.xml`（ブロック単位の SHA-256 ハッシュリスト）および正規の OPC メタデータが含まれていることを厳格に検査します。Windows SDK がインストールされていない環境では ZIP フォールバックで固められるため、App Installer が構造不適合として解析エラーを返します。
> 2. **デジタル署名の未付与**: Windows のセキュリティ仕様により、未署名の MSIX パッケージはローカルで直接インストール（サイドローディング）できません。
> 
> **対処方法**:
> - **今すぐローカルで動作確認する場合**: `dist/syukatsu-support.exe` を直接ダブルクリックして起動してください。
> - **Microsoft Store への提出**: Partner Center に `dist/syukatsu-support.msix` を提出、または「Win32 アプリケーション」枠として `dist/syukatsu-support.exe` を提出してください（Store 審査通過時に Microsoft の公式証明書で自動署名されます）。
> - **ローカルで MSIX インストールを検証したい場合**: Microsoft Store より無償の「**MSIX Packaging Tool**」を入手して `dist/msix_stage` をパッケージ化するか、Windows SDK を導入してテスト証明書で `SignTool.exe` による署名を行ってください。

---

## 4. ストア申請手順 (Partner Center)

Microsoft Store では **MSIX パッケージ方式** および **Win32 EXE 方式** の両方が利用可能です。

### 方式 A: MSIX パッケージによる申請（推奨）

1. Partner Center の「申請」→「パッケージ」セクションを開きます。
2. `dist/syukatsu-support.msix` をドラッグ＆ドロップしてアップロードします。
3. パッケージの整合性・マニフェスト検証が自動的に実行されます。

### 方式 B: Win32 EXE 直接申請

1. アプリの種類として「デスクトップ アプリケーション (Win32)」を選択します。
2. 実行ファイル `dist/syukatsu-support.exe` をアップロード、またはホスティング先 URL を指定します。

---

## 5. ストア掲載情報の入力項目

審査をスムーズに通過させるための推奨設定値です。

- **カテゴリ**: `ビジネス & 生産性 (Business & Productivity)` / `教育 (Education)`
- **価格と提供状況**: 無料（Free）
- **年齢区分**: アンケートに回答（外部AIとの通信を行うため、適切なレーティングを選択）
- **プライバシーポリシー URL**:
  - 本アプリに付属する [PRIVACY_POLICY.md](file:///e:/Python/syukatsu_Support/PRIVACY_POLICY.md) を GitHub または自社サイトの Web URL として指定します。
- **機能宣言 (Capabilities)**:
  - `runFullTrust`（デスクトップ ネイティブ実行に必要な権限）
- **ストアアセット画像**:
  - `assets/StoreLogo.png` (50x50)
  - `assets/Square150x150Logo.png` (150x150)
  - `assets/Square44x44Logo.png` (44x44)
  - `assets/Wide310x150Logo.png` (310x150)
  - `assets/SplashScreen.png` (620x300)
  - ※ 実際のアプリ画面スクリーンショット（1920x1080 等）を最低1枚以上添付してください。

---

## 6. 審査提出とリリース

1. 全セクションの入力が完了したら、「ストアに提出」をクリックします。
2. 通常 24〜72 時間以内に Microsoft による自動・手動審査が完了し、Store 上に公開されます。
