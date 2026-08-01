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

import openai

def translate_api_error(e: Exception) -> str:
    """
    OpenAI APIエラーおよびシステム例外を初心者に分かりやすい丁寧な日本語メッセージに変換します。
    """
    # Tenacity の RetryError の場合は内部で発生した元の例外を取り出す
    if hasattr(e, "last_attempt") and getattr(e, "last_attempt", None):
        try:
            exc = e.last_attempt.exception()
            if exc:
                e = exc
        except Exception:
            pass

    err_str = str(e)

    # 1. アプリの多重起動によるロック / ファイル権限エラー
    if isinstance(e, PermissionError) or "WinError 32" in err_str or "Permission denied" in err_str or "locked" in err_str.lower():
        return (
            "【アプリの多重起動エラー】 (App Lock Error)\n"
            "SYUKATSU Supportがすでに別のウィンドウまたはバックグラウンドで起動しているため、設定ファイルやデータがロックされています。\n"
            "他のSYUKATSU Supportの画面を閉じてから、再度起動・操作をお試しください。"
        )

    # 2. タイムアウト
    if isinstance(e, (openai.APITimeoutError, TimeoutError)) or "APITimeoutError" in err_str or "timed out" in err_str.lower():
        return (
            "【通信タイムアウト】 (APITimeoutError)\n"
            "OpenAIサーバーからの応答が制限時間を超えました。\n"
            "サーバーが一時的に混雑している可能性があります。数十秒ほど待ってから再度お試しください。"
        )

    # 3. APIキー形式エラー (UnicodeEncodeError / 全角文字混入など)
    if isinstance(e, (UnicodeEncodeError, UnicodeError)) or "ascii" in err_str.lower() or "ordinal not in range" in err_str.lower() or "codec" in err_str.lower():
        return (
            "【APIキー文字エラー】 (Invalid Key Format)\n"
            "入力されたOpenAI APIキーに全角文字や全角スペースなど、使用できない文字が含まれています。\n"
            "APIキーはすべて半角英数字・半角記号（sk-proj-...等）である必要があります。\n"
            "入力欄に半角の正しいAPIキーを貼り付け直し、「登録」ボタンを押してください。"
        )

    # 4. APIキーが誤っている (AuthenticationError)
    if isinstance(e, openai.AuthenticationError) or "AuthenticationError" in err_str or "invalid_api_key" in err_str.lower() or "401" in err_str:
        return (
            "【APIキーエラー】 (AuthenticationError)\n"
            "入力されたOpenAI APIキーが正しくないか、無効化されています。\n"
            "正しいAPIキー（sk-proj-...など）を入力欄に貼り付け直し、「登録」ボタンを押してください。"
        )

    # 4. API利用上限 / 残高不足 (RateLimitError)
    if isinstance(e, openai.RateLimitError) or "RateLimitError" in err_str:
        # クレジットの残高が不足している場合
        if "insufficient_quota" in err_str or "quota" in err_str.lower() or "billing" in err_str.lower() or "credit" in err_str.lower():
            return (
                "【クレジット残高不足】 (Insufficient Quota)\n"
                "OpenAIアカウントの無料利用分が終了したか、チャージ残高が不足しています。\n"
                "OpenAIの管理画面（https://platform.openai.com/settings/organization/billing）でクレジット残高や支払い情報をご確認ください。"
            )
        # 短期的なAPI利用上限（レート制限）に達している場合
        return (
            "【一時的な利用制限】 (RateLimitError)\n"
            "短時間での利用回数または利用量の上限（レートリミット）に達しました。\n"
            "数十秒〜数分ほど時間を置いてから再度お試しください。"
        )

    # 5. リクエストエラー (BadRequestError) - 入力トークン上限オーバー / 推論レベルミスマッチ等
    if isinstance(e, openai.BadRequestError) or "BadRequestError" in err_str:
        # 入力トークン上限オーバー
        if any(k in err_str.lower() for k in ["context_length_exceeded", "maximum context length", "exceeds the context window", "string_above_max_length", "too long", "token limit"]):
            return (
                "【入力文字数制限オーバー】 (Context Window Exceeded)\n"
                "送信した文章または過去の会話履歴が、AIが一度に処理できる制限（トークン上限）を超えています。\n"
                "「🧹 コンテキスト消去」ボタンを押して会話履歴をリセットするか、質問文を短くして再度お試しください。"
            )
        # 推論レベルミスマッチ
        if "reasoning_effort" in err_str or "reasoning.effort" in err_str:
            return (
                "【モデル設定エラー】 (Reasoning Effort Error)\n"
                "選択した推論強度が、現在のモデルでサポートされていません。\n"
                "推論強度を変更するか、対応するモデル（gpt-5.6-terra等）を選択してください。"
            )
        return (
            f"【リクエストエラー】 (BadRequestError)\n"
            f"送信したデータ形式または設定内容に問題があります。\n"
            f"詳細: {err_str}"
        )

    # 6. その他の標準的なOpenAI例外
    if isinstance(e, openai.APIConnectionError) or "APIConnectionError" in err_str:
        return (
            "【ネットワーク接続エラー】 (APIConnectionError)\n"
            "OpenAIのサーバーに接続できませんでした。\n"
            "インターネットの接続状態を確認し、再度お試しください。"
        )

    if isinstance(e, openai.NotFoundError) or "NotFoundError" in err_str:
        return (
            "【リソースが見つかりません】 (NotFoundError)\n"
            "指定されたモデルやVector Store（ナレッジベース）が存在しないか、アクセス権がありません。\n"
            "設定画面でモデルやVector Storeが正しいか確認してください。"
        )

    if isinstance(e, openai.InternalServerError):
        return (
            "【OpenAIサーバーエラー】 (InternalServerError)\n"
            "OpenAIのサーバー側で一時的な障害が発生しています。\n"
            "しばらく待ってから再度お試しください。"
        )

    if isinstance(e, openai.ConflictError):
        return (
            "【データ競合エラー】 (ConflictError)\n"
            "リソースが別の処理で更新中であるため、競合が発生しました。\n"
            "しばらく待ってから再度お試しください。"
        )

    if isinstance(e, openai.OpenAIError):
        return (
            f"【OpenAI APIエラー】 ({type(e).__name__})\n"
            f"AI通信中にエラーが発生しました。\n"
            f"詳細: {err_str}"
        )

    # 7. その他の予期せぬエラー
    return f"【システムエラー】 予期せぬエラーが発生しました:\n{err_str}"

