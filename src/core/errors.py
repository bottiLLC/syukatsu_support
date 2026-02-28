import openai

def translate_api_error(e: Exception) -> str:
    """
    OpenAIの例外をユーザーに分かりやすい日本語のエラーメッセージに変換します。
    すべての標準的な例外タイプに対して、詳細な説明と対処可能なアドバイスを提供します。
    """
    match type(e):
        case openai.AuthenticationError:
            return (
                "【API認証エラー】 (AuthenticationError)\n"
                "APIキーが無効、またはアクセス権限がありません。\n"
                "対策: 設定画面または環境変数 (OPENAI_API_KEY) で正しいAPIキーが設定されているか確認してください。"
            )
        case openai.RateLimitError:
            return (
                "【利用制限エラー】 (RateLimitError)\n"
                "APIの利用上限に達したか、アカウントの残高が不足しています。\n"
                "対策: しばらく待ってから再試行するか、OpenAIの管理画面で利用枠や支払い情報を確認してください。"
            )
        case openai.APITimeoutError:
            return (
                "【タイムアウト】 (APITimeoutError)\n"
                "サーバーからの応答が制限時間を超えました。一時的な混雑が原因の可能性があります。\n"
                "対策: しばらく待ってから再度お試しください。"
            )
        case openai.APIConnectionError:
            return (
                "【通信エラー】 (APIConnectionError)\n"
                "OpenAIのサーバーへ接続できませんでした。ネットワーク環境が不安定な可能性があります。\n"
                "対策: インターネットへの接続状況を確認し、再度お試しください。"
            )
        case openai.NotFoundError:
            return (
                "【リソース未発見】 (NotFoundError)\n"
                "要求されたリソース（指定したモデルやファイルなど）が見つかりません。\n"
                "対策: 設定されているモデル名(gpt-5.2等)や、読み込み対象のファイルが存在しているか確認してください。"
            )
        case openai.ConflictError:
            return (
                "【競合エラー】 (ConflictError)\n"
                "リソースが別のプロセスで更新中である等、競合が発生しました。\n"
                "対策: しばらく待ってから再試行してください。"
            )
        case openai.UnprocessableEntityError:
            return (
                "【処理不能エラー】 (UnprocessableEntityError)\n"
                "リクエストの形式は正しいですが、内容の処理ができませんでした。\n"
                "対策: 送信データ（ファイルやテキスト内容）に異常がないか確認してください。"
            )
        case openai.InternalServerError:
            return (
                "【サーバー内部エラー】 (InternalServerError)\n"
                "OpenAI側で一時的なシステム障害が発生している可能性があります。\n"
                "対策: しばらく待ってから再度お試しください。問題が続く場合はOpenAIのステータスぺージをご確認ください。"
            )
        case openai.BadRequestError:
            err_str = str(e)
            # Catch errors related to invalid reasoning efforts or tool combinations
            if "reasoning_effort" in err_str or "reasoning.effort" in err_str:
                return (
                    "【リクエストエラー】 (BadRequestError/ReasoningEffort)\n"
                    "選択した推論レベル（Reasoning Effort）が、現在のモデルでサポートされていません。\n"
                    "対策: 設定で推論レベルを変更するか、対応するモデルを選択してください。"
                )
            # Catch context window exceeded error
            if "maximum context length" in err_str or "exceeds the context window" in err_str or "context_length_exceeded" in err_str:
                return (
                    "【データ超過エラー】 (ContextWindowExceeded)\n"
                    "読み込んだ文章量・会話履歴がモデルの処理限界を超えました。\n"
                    "対策: 「🧹コンテキスト消去」を押して履歴をリセットするか、質問内容をより具体的に絞って再度お試しください。"
                )
            return (
                f"【リクエストエラー】 (BadRequestError)\n"
                f"送信したデータに誤りがあります。\n詳細: {err_str}"
            )
        case openai.OpenAIError:
            return (
                f"【OpenAI APIエラー】 (OpenAIError)\n"
                f"APIとの通信中にエラーが発生しました。\n詳細: {str(e)}"
            )
        case _:
            return f"【システムエラー】 予期せぬエラーが発生しました: {str(e)}"

