from google.genai import errors as genai_errors

def translate_api_error(e: Exception) -> str:
    """
    Translates Gemini exceptions to user-friendly Japanese error messages.
    """
    if isinstance(e, genai_errors.APIError):
        err_str = str(e)
        if "401" in err_str or "UNAUTHENTICATED" in err_str or "API_KEY_INVALID" in err_str:
            return "API認証エラー: APIキーが無効か、アクセス権限がありません。"
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            return "利用制限エラー: 会話の利用上限に達したか、残高が不足しています。"
        if "504" in err_str or "DEADLINE_EXCEEDED" in err_str:
            return "タイムアウト: サーバーからの応答が制限時間を超えました。"
        
        # Catch errors related to reasoning efforts just in case
        if "reasoning" in err_str.lower():
            return "_REASONING_EFFORT_ERROR_"
            
        # Catch context window exceeded error
        if "maximum context length" in err_str.lower() or "exceeds" in err_str.lower() or "too large" in err_str.lower():
            return (
                "データ超過エラー: 読み込んだ文章量・会話履歴がモデルの処理限界を超えました。\n"
                "【対策】「🧹コンテキスト消去」を押して履歴をリセットするか、"
                "質問内容をより具体的に絞って再度お試しください。"
            )
            
        return f"Gemini APIエラー: {err_str}"
    
    return f"予期せぬエラーが発生しました: {str(e)}"
