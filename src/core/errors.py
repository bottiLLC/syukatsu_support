# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""OpenAI API エラー翻訳モジュール。

OpenAI API例外およびシステムエラーを検知し、初心者に分かりやすい丁寧な日本語メッセージに変換します。
"""

from __future__ import annotations

import openai


def _extract_error_details(e: Exception) -> tuple[int | None, str | None, str]:
    """例外オブジェクトからHTTPステータスコード、エラーコード、文字列表現を安全に抽出します。"""
    status_code: int | None = getattr(e, "status_code", None)
    if status_code is None and hasattr(e, "response") and getattr(e, "response", None) is not None:
        status_code = getattr(e.response, "status_code", None)

    error_code: str | None = getattr(e, "code", None)
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        err_dict = body.get("error")
        if isinstance(err_dict, dict) and not error_code:
            error_code = err_dict.get("code")

    err_str = str(e)
    return status_code, error_code, err_str


def translate_api_error(e: Exception) -> str:
    """OpenAI APIエラーおよびシステム例外を初心者に分かりやすい丁寧な日本語メッセージと対応方法に変換します。"""
    # Tenacity の RetryError の場合は内部で発生した元の例外を取り出す
    if hasattr(e, "last_attempt") and getattr(e, "last_attempt", None):
        try:
            exc = e.last_attempt.exception()
            if exc:
                e = exc
        except Exception:
            pass

    status_code, error_code, err_str = _extract_error_details(e)
    lower_err = err_str.lower()
    code_str = (error_code or "").lower()

    # 1. アプリの多重起動によるロック / ファイル権限エラー
    if (
        isinstance(e, PermissionError)
        or "winerror 32" in lower_err
        or "permission denied" in lower_err
        or "locked" in lower_err
    ):
        return (
            "【アプリの多重起動エラー】 (App Lock Error)\n"
            "■ 原因: SYUKATSU Supportがすでに別のウィンドウまたはバックグラウンドで起動しているため、設定ファイルやデータがロックされています。\n"
            "■ 対応方法: 他のSYUKATSU Supportの画面をすべて閉じてから、再度起動・操作をお試しください。"
        )

    # 2. タイムアウト
    if (
        isinstance(e, (openai.APITimeoutError, TimeoutError))
        or "apitimeouterror" in lower_err
        or "timed out" in lower_err
    ):
        return (
            "【通信タイムアウト】 (APITimeoutError)\n"
            "■ 原因: OpenAIサーバーからの応答待機時間が制限を超過しました。大規模な文書解析時やサーバー混雑時に発生します。\n"
            "■ 対応方法: サーバー混雑が緩和するまで数十秒〜数分お待ちいただき、再度お試しください。"
        )

    # 3. APIキー形式エラー (UnicodeEncodeError / 全角文字混入など)
    if (
        isinstance(e, (UnicodeEncodeError, UnicodeError))
        or "ascii" in lower_err
        or "ordinal not in range" in lower_err
        or "codec" in lower_err
    ):
        return (
            "【APIキー文字エラー】 (Invalid Key Format)\n"
            "■ 原因: 入力されたOpenAI APIキーに全角文字や全角スペースなど、使用できない文字が含まれています。\n"
            "■ 対応方法: APIキーはすべて半角英数字・半角記号（sk-proj-...等）である必要があります。正しい半角文字を入力欄に貼り付け直し、「登録」ボタンを押してください。"
        )

    # 4. 認証エラー (AuthenticationError: 401)
    if (
        isinstance(e, openai.AuthenticationError)
        or status_code == 401
        or "authenticationerror" in lower_err
        or "invalid_api_key" in code_str
        or "invalid_api_key" in lower_err
    ):
        if "ip_not_authorized" in code_str or "ip_not_authorized" in lower_err:
            return (
                "【アクセス拒否（IP制限）】 (AuthenticationError: 401)\n"
                "■ 原因: 接続元のIPアドレスが、OpenAI組織アカウントで設定されたIPホワイトリスト（許可リスト）に含まれていません。\n"
                "■ 対応方法: OpenAI管理画面のセキュリティ設定（IP allowlist）を確認し、現在お使いのネットワークのIPアドレスを追加するか、制限を解除してください。"
            )
        if "account_deactivated" in code_str or "account_deactivated" in lower_err:
            return (
                "【アカウント無効化エラー】 (AuthenticationError: 401)\n"
                "■ 原因: ご利用のOpenAIアカウントが無効化または一時停止されています。\n"
                "■ 対応方法: OpenAIアカウントの状態をご確認いただくか、OpenAIサポート（https://help.openai.com）にお問い合わせください。"
            )
        return (
            "【APIキーエラー】 (AuthenticationError: 401)\n"
            "■ 原因: 入力されたOpenAI APIキーが正しくないか、無効化または削除されています。\n"
            "■ 対応方法: OpenAIの管理画面（https://platform.openai.com/api-keys）で新しいAPIキーを生成・コピーし、画面左上の「設定 / 変更」または詳細設定の入力欄に貼り直して「登録」ボタンを押してください。"
        )

    # 5. アクセス権限エラー (PermissionDeniedError: 403)
    if (
        isinstance(e, openai.PermissionDeniedError)
        or status_code == 403
        or "permissiondeniederror" in lower_err
        or "permission_denied" in code_str
    ):
        return (
            "【アクセス権限エラー】 (PermissionDeniedError: 403)\n"
            "■ 原因: リクエストされたモデルや機能へのアクセス権限がないか、国・地域制限（非対応国からのアクセス）にかかっています。\n"
            "■ 対応方法: ご利用のOpenAI組織（Organization）やプロジェクトに選択中のモデルへのアクセス権が付与されているか確認してください。また、VPNをご利用の場合は接続地域（Supported countries）をご確認ください。"
        )

    # 6. リソース未存在エラー (NotFoundError: 404)
    if (
        isinstance(e, openai.NotFoundError)
        or status_code == 404
        or "notfounderror" in lower_err
        or "model_not_found" in code_str
    ):
        return (
            "【リソースが見つかりません】 (NotFoundError: 404)\n"
            "■ 原因: 指定されたAIモデル、Vector Store（ナレッジベース）、ファイルID、または会話履歴（レスポンスID）が存在しません。\n"
            "■ 対応方法:\n"
            "  1. モデルの場合: 選択中のモデル名が正しいか設定画面でご確認ください。\n"
            "  2. ナレッジベースの場合: 「ナレッジベース管理」を開き、Vector Storeを再作成・同期してください。\n"
            "  3. 会話継続の場合: 「🧹 コンテキスト消去」ボタンを押して新規チャットを開始してください。"
        )

    # 7. リソース競合エラー (ConflictError: 409)
    if isinstance(e, openai.ConflictError) or status_code == 409 or "conflicterror" in lower_err:
        return (
            "【リソース競合エラー】 (ConflictError: 409)\n"
            "■ 原因: 操作対象のVector Storeやファイルが、OpenAIサーバー上で別の更新・解析処理を実行中のため競合が発生しました。\n"
            "■ 対応方法: サーバー側でのファイル処理やインデックス生成が完了するまで数十秒〜数分お待ちいただき、再度お試しください。"
        )

    # 8. 処理不能エンティティ (UnprocessableEntityError: 422)
    if isinstance(e, openai.UnprocessableEntityError) or status_code == 422 or "unprocessableentityerror" in lower_err:
        return (
            "【データ処理不可エラー】 (UnprocessableEntityError: 422)\n"
            "■ 原因: リクエスト構文は正しいものの、指定したPDFファイルやデータ内容がサーバー側で解析できない形式（破損、パスワード保護、非対応エンコーディング等）です。\n"
            "■ 対応方法: 添付した有報PDFファイルが破損していないか、パスワード保護されていないかを確認し、正常なPDFを再選択してください。"
        )

    # 9. 利用枠・利用上限・レートリミット (RateLimitError: 429)
    if isinstance(e, openai.RateLimitError) or status_code == 429 or "ratelimiterror" in lower_err:
        # クレジット残高不足
        if (
            "insufficient_quota" in code_str
            or "credit_balance_exhausted" in code_str
            or "insufficient_quota" in lower_err
            or "quota" in lower_err
            or "billing" in lower_err
            or "credit" in lower_err
        ):
            return (
                "【クレジット残高不足】 (Insufficient Quota: 429)\n"
                "■ 原因: OpenAIアカウントの利用枠（クレジット残高）が不足しているか、無料クレジットの有効期限が終了しています。\n"
                "■ 対応方法: OpenAIプラットフォームの請求管理画面（https://platform.openai.com/settings/organization/billing）にアクセスし、クレジット残高をチャージ（Add to credit balance）してください。"
            )
        # 月間利用上限到達
        if (
            "organization_usage_limit_exceeded" in code_str
            or "organization_spend_limit_exceeded" in code_str
            or "usage_limit_exceeded" in lower_err
        ):
            return (
                "【月間利用上限到達】 (Usage Limit Exceeded: 429)\n"
                "■ 原因: 組織アカウントに設定されている月間の利用上限額（Usage Limit / Spend Limit）に到達しました。\n"
                "■ 対応方法: OpenAI管理画面のLimits設定で月間上限額を引き上げるか、翌月1日の上限リセットをお待ちください。"
            )
        # 短期レート制限（TPMおよびRPM）
        return (
            "【一時的な利用制限】 (RateLimitError: 429)\n"
            "■ 原因: 短時間でのリクエスト回数（RPM）またはトークン消費量（TPM）の上限に達しました。\n"
            "■ 対応方法: 自動リトライが行われますが、解消しない場合は数十秒〜数分ほど時間を置いてから再度お試しください。"
        )

    # 10. リクエスト構文・パラメータエラー (BadRequestError: 400)
    if isinstance(e, openai.BadRequestError) or status_code == 400 or "badrequesterror" in lower_err:
        # 入力トークン上限オーバー
        if any(
            k in lower_err
            for k in [
                "context_length_exceeded",
                "maximum context length",
                "exceeds the context window",
                "string_above_max_length",
                "too long",
                "token limit",
            ]
        ):
            return (
                "【入力文字数制限オーバー】 (Context Window Exceeded: 400)\n"
                "■ 原因: 送信した有報PDF、質問文、および過去の会話履歴の総トークン数がモデルの許容上限（コンテキストウィンドウ）を超えています。\n"
                "■ 対応方法: 「🧹 コンテキスト消去」ボタンを押して会話履歴をリセットするか、質問内容を簡潔にして再度お試しください。"
            )
        # 推論レベルミスマッチ
        if "reasoning_effort" in lower_err or "reasoning.effort" in lower_err:
            return (
                "【モデル設定エラー】 (Reasoning Effort Error: 400)\n"
                "■ 原因: 選択中のモデルでは指定された推論強度（reasoning_effort）がサポートされていません。\n"
                "■ 対応方法: 詳細設定パネルで推論強度を変更するか、対応する最新モデルを選択してください。"
            )
        return (
            "【リクエストエラー】 (BadRequestError: 400)\n"
            "■ 原因: 送信データ形式または設定パラメータがOpenAI APIの仕様と一致していません。\n"
            f"■ 詳細: {err_str}\n"
            "■ 対応方法: 設定内容を見直し、不要なオプションを初期状態に戻してお試しください。"
        )

    # 11. サーバーエラー群 (500, 502, 503, 504)
    if status_code in (502, 504) or "bad gateway" in lower_err or "gateway timeout" in lower_err:
        return (
            f"【ゲートウェイ通信エラー】 (Gateway Error: {status_code or '502/504'})\n"
            "■ 原因: OpenAIの上位サーバーまたは通信プロキシ間で一時的な通信障害・タイムアウトが発生しました。\n"
            "■ 対応方法: 少し時間を置いてから再度送信してください。頻発する場合はネットワーク環境をご確認ください。"
        )

    if status_code == 503 or "service unavailable" in lower_err or "overloaded" in lower_err or "capacity" in lower_err:
        return (
            "【サーバー過負荷・一時停止】 (Service Unavailable: 503)\n"
            "■ 原因: OpenAIサーバーが現在アクセス集中により過負荷（Overloaded）状態にあるか、システムメンテナンス中です。\n"
            "■ 対応方法: アクセスが落ち着くまで数分ほど時間を置いてから再度お試しいただくか、ステータスページ（https://status.openai.com）をご確認ください。"
        )

    if isinstance(e, openai.InternalServerError) or status_code == 500 or "internalservererror" in lower_err:
        return (
            "【OpenAIサーバーエラー】 (InternalServerError: 500)\n"
            "■ 原因: OpenAIのサーバー内部で一時的な障害が発生しました。\n"
            "■ 対応方法: ユーザー側の設定に問題はありません。OpenAIステータスページ（https://status.openai.com）で稼働状況をご確認の上、数分置いて再度お試しください。"
        )

    # 12. ネットワーク接続エラー
    if isinstance(e, openai.APIConnectionError) or "apiconnectionerror" in lower_err:
        return (
            "【ネットワーク接続エラー】 (APIConnectionError)\n"
            "■ 原因: お使いのPCからOpenAIサーバーへの通信が確立できませんでした（DNS解決失敗、回線切断、プロキシ・ファイアウォールによる遮断等）。\n"
            "■ 対応方法:\n"
            "  1. インターネット接続が正常かブラウザでWebページが開けるか確認してください。\n"
            "  2. 社内ネットワークやVPN、セキュリティソフトをご利用の場合は、OpenAIサーバー（api.openai.com）への通信が遮断されていないか確認してください。"
        )

    # 13. その他のOpenAI基底例外
    if isinstance(e, openai.OpenAIError):
        type_name = type(e).__name__
        return (
            f"【OpenAI APIエラー】 ({type_name})\n"
            "■ 原因: OpenAI APIとの通信中にエラーが発生しました。\n"
            f"■ 詳細: {err_str}\n"
            "■ 対応方法: 設定内容を確認の上再度お試しください。解消しない場合はOpenAIの稼働状況（https://status.openai.com）をご確認ください。"
        )

    # 14. その他の予期せぬシステム例外
    return (
        "【システムエラー】 予期せぬエラーが発生しました:\n"
        f"■ 原因・詳細: {err_str}\n"
        "■ 対応方法: アプリケーションを再起動して再度お試しください。"
    )
