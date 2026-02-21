import openai

def translate_api_error(e: Exception) -> str:
    """
    Translates OpenAI exceptions to user-friendly Japanese error messages.
    """
    if isinstance(e, openai.AuthenticationError):
        return "API認証エラー: APIキーが無効か、アクセス権限がありません。"
    elif isinstance(e, openai.RateLimitError):
        return "利用制限エラー: 会話の利用上限に達したか、残高が不足しています。"
    elif isinstance(e, openai.APITimeoutError):
        return "タイムアウト: サーバーからの応答が制限時間を超えました。"
    elif isinstance(e, openai.APIConnectionError):
        return "通信エラー: OpenAIサーバーへ接続できませんでした。"
    elif isinstance(e, openai.BadRequestError):
        err_str = str(e)
        # Catch errors related to invalid reasoning efforts or tool combinations
        if "reasoning_effort" in err_str or "reasoning.effort" in err_str:
            return "_REASONING_EFFORT_ERROR_"
        # Catch context window exceeded error
        if "maximum context length" in err_str or "exceeds the context window" in err_str or "context_length_exceeded" in err_str:
            return (
                "データ超過エラー: 読み込んだ文章量・会話履歴がモデルの処理限界を超えました。\n"
                "【対策】「🧹コンテキスト消去」を押して履歴をリセットするか、"
                "質問内容をより具体的に絞って再度お試しください。"
            )
        return f"リクエストエラー: 送信したデータに誤りがあります。\n詳細: {err_str}"
    elif isinstance(e, openai.OpenAIError):
        return f"OpenAI APIエラー: {str(e)}"
    
    return f"予期せぬエラーが発生しました: {str(e)}"
