"""
OpenAI APIとのやり取りおよびコスト計算のためのサービス層。

このモジュールは、OpenAI Responses APIと通信するための `LLMService` と、
使用コストを見積もるための `CostCalculator` を提供します。非同期ストリーミングレスポンス、
イベント処理、および就活サポートアプリのためのエラー管理を処理します。
"""

import logging
import structlog
from typing import Any, AsyncGenerator, Optional

from openai import (
    OpenAIError,
    AsyncOpenAI
)
from pydantic import ValidationError

from src.core.base import BaseOpenAIService
from src.core.models import (
    ResponseRequestPayload,
    StreamError,
    StreamResponseCreated,
    StreamResult,
    StreamTextDelta,
    StreamUsage,
)
from src.core.pricing import PRICING_TABLE, ModelPricing
from src.core.errors import translate_api_error
from src.core.resilience import resilient_api_call

log = structlog.get_logger()


class CostCalculator:
    """
    API使用量の見積りコストを計算するためのユーティリティを提供します。
    """

    _TOKEN_UNIT = 1_000_000

    @classmethod
    def calculate(cls, model_name: str, usage: StreamUsage) -> str:
        """
        指定されたモデルとトークン使用量に対する見積りコストを計算します。

        Args:
            model_name: 使用されたモデルの識別子 (例: "gpt-5.2")。
            usage: トークン使用量の統計 (input, output, cached)。

        Returns:
            トークン数とUSDでの見積りコストを示すフォーマットされた文字列。
        """
        pricing = cls._get_pricing(model_name)
        is_estimate = False

        # モデルが見つからない場合はデフォルトの価格設定にフォールバック
        if not pricing:
            pricing = PRICING_TABLE.get("gpt-5.2")
            is_estimate = True
            log.warning(
                "モデルの価格設定が見つかりません。デフォルトにフォールバックします。",
                model_name=model_name,
                default_model="gpt-5.2",
            )

        if not pricing:
            log.error("どのモデルに対しても価格情報が利用できません。")
            return "Cost info unavailable"

        # 入力コスト計算: (総入力 - キャッシュ分) * 入力単価
        non_cached_input = max(0, usage.input_tokens - usage.cached_tokens)
        input_cost = (non_cached_input / cls._TOKEN_UNIT) * pricing.input_price

        # キャッシュされた入力コスト計算
        cached_cost = (
            usage.cached_tokens / cls._TOKEN_UNIT
        ) * pricing.cached_input_price

        # 出力コスト計算
        output_cost = (usage.output_tokens / cls._TOKEN_UNIT) * pricing.output_price

        total_cost = input_cost + cached_cost + output_cost
        estimate_label = "(Est.)" if is_estimate else ""

        log.info(
            "コストが計算されました",
            model_name=model_name,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.cached_tokens,
            total_cost=total_cost,
            is_estimate=is_estimate,
        )

        return (
            f"Tokens: {usage.total_tokens} "
            f"(In:{usage.input_tokens}/Cache:{usage.cached_tokens}/Out:{usage.output_tokens}) | "
            f"Cost: ${total_cost:.5f} {estimate_label}"
        )

    @staticmethod
    def _get_pricing(model_name: str) -> Optional[ModelPricing]:
        """
        指定されたモデルの価格設定を取得します。

        モデル名を価格テーブルのキーと照合し、より長い(より具体的な)一致を優先します。

        Args:
            model_name: モデルの識別子。

        Returns:
            見つかった場合は ModelPricing オブジェクト、それ以外は None。
        """
        # より具体的なモデルを最初に一致させるため、キーを長さの降順にソート
        sorted_keys = sorted(PRICING_TABLE.keys(), key=len, reverse=True)

        for key in sorted_keys:
            if key in model_name:
                log.debug("モデルの価格設定キーに一致しました", model_name=model_name, matched_key=key)
                return PRICING_TABLE[key]
        log.warning("モデルの価格設定が見つかりません", model_name=model_name)
        return None


class LLMService(BaseOpenAIService):
    """
    OpenAI Responses API とやり取りするためのサービス。

    AsyncOpenAIコンテキストマネージャーを使用して分析レスポンスのストリーミングを処理し、
    APIイベントをアプリケーション固有のドメインオブジェクトに変換します。
    """

    async def stream_analysis(
        self, payload: ResponseRequestPayload
    ) -> AsyncGenerator[StreamResult, None]:
        """
        Responses API への非同期ストリーミングリクエストを実行します。

        Args:
            payload: モデル、入力、およびその他のパラメータを含むリクエストペイロード。

        Yields:
            テキストのデルタ、レスポンスメタデータ、使用量統計、またはエラーを表す
            StreamResult オブジェクト。
        """
        try:
            # Pydantic モデルを辞書に変換。APIのデフォルトを尊重するためNoneは除外
            request_params = payload.model_dump(exclude_none=True)

            log.info(
                "非同期ストリーム分析を開始します",
                model=payload.model,
                request_params_keys=list(request_params.keys()),
            )

            # 非同期ジェネレータからyield
            async for result in self._execute_api_call(request_params):
                yield result

        except Exception as e:
            # ジェネレータのセットアップ中の予期しない例外のキャッチオール
            log.exception("stream_analysis で予期しないエラーが発生しました", error=str(e))
            yield StreamError(
                message=f"\n[Unexpected Error] 予期せぬエラーが発生しました: {e}"
            )

    @resilient_api_call()
    async def _create_stream(self, client: AsyncOpenAI, request_params: dict) -> Any:
        """
        リトライロジックを使用して API ストリームを開始するヘルパーメソッド。
        これは *接続* の確立のみをリトライし、ストリームのイテレーションはリトライしません。
        """
        log.info(
            "APIストリームの作成を試みます",
            model=request_params.get("model"),
            attempt_params=request_params,
        )
        # 要件に従い厳密に client.responses.create を使用
        return await client.responses.create(**request_params)

    async def _execute_api_call(
        self, request_params: dict
    ) -> AsyncGenerator[StreamResult, None]:
        """
        非同期コンテキストマネージャー内で API コールを実行し、結果を yield します。
        特定の API 例外を処理し、それらを StreamError イベントに変換します。
        """
        model_name = request_params.get("model", "unknown_model")
        try:
            async with self.get_async_client() as client:
                stream = await self._create_stream(client, request_params)

                async for event in stream:
                    result = self._process_event(event)
                    if result:
                        yield result
            log.info("API ストリームが正常に完了しました。", model=model_name)

        except OpenAIError as e:
            msg = translate_api_error(e)
            log.error(
                "ストリームイテレーション中の OpenAI API エラー",
                model=model_name,
                error_type=type(e).__name__,
                error_message=str(e),
                translated_message=msg,
            )
            yield StreamError(message=f"\n[API Error] {msg}")
        except ValidationError as e:
            log.error(
                "ストリーム処理中のバリデーションエラー",
                model=model_name,
                error_message=str(e),
            )
            yield StreamError(
                message=f"\n[Validation Error] リクエストデータの形式が不正です: {e}"
            )
        except Exception as e:
            log.exception(
                "ストリームイテレーション中のエラー",
                model=model_name,
                error_message=str(e),
            )
            yield StreamError(
                message=f"\n[Stream Error] ストリーム処理中にエラーが発生しました: {e}"
            )

    def _process_event(self, event: Any) -> Optional[StreamResult]:
        """
        生の API イベントをドメインオブジェクトに解析します。

        Args:
            event: OpenAI SDK ストリームによって返されるイベントオブジェクト。

        Returns:
            イベントが関連する場合は StreamResult オブジェクト、それ以外は None。
        """
        # OpenAPI 'ResponseStreamEvent' スキーマに基づくイベント型のチェック
        event_type = getattr(event, "type", None)

        if not event_type:
            return None

        if event_type == "response.output_text.delta":
            return self._handle_text_delta(event)

        if event_type == "response.created":
            return self._handle_response_created(event)

        if event_type == "response.completed":
            return self._handle_response_completed(event)

        if event_type == "error":
            return self._handle_error_event(event)

        return None

    def _handle_text_delta(self, event: Any) -> Optional[StreamTextDelta]:
        """'response.output_text.delta' イベントを処理します。"""
        delta_content = getattr(event, "delta", None)
        if delta_content:
            return StreamTextDelta(delta=delta_content)
        return None

    def _handle_response_created(
        self, event: Any
    ) -> Optional[StreamResponseCreated]:
        """'response.created' イベントを処理します。"""
        response_obj = getattr(event, "response", None)
        if response_obj and hasattr(response_obj, "id"):
            return StreamResponseCreated(response_id=response_obj.id)
        return None

    def _handle_response_completed(self, event: Any) -> Optional[StreamUsage]:
        """
        'response.completed' イベントを処理して、使用量統計を抽出します。
        """
        response_obj = getattr(event, "response", None)
        if not response_obj:
            return None

        usage_obj = getattr(response_obj, "usage", None)
        if not usage_obj:
            return None

        # デフォルト値を使用して安全に使用量フィールドを抽出
        input_tokens = getattr(usage_obj, "input_tokens", 0)
        output_tokens = getattr(usage_obj, "output_tokens", 0)
        total_tokens = getattr(usage_obj, "total_tokens", 0)

        # input_tokens_details からキャッシュされたトークンを抽出
        cached_tokens = 0
        input_details = getattr(usage_obj, "input_tokens_details", None)
        if input_details:
            cached_tokens = getattr(input_details, "cached_tokens", 0)

        return StreamUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
        )

    def _handle_error_event(self, event: Any) -> StreamError:
        """
        ストリームからの 'error' イベントを処理します。
        """
        error_obj = getattr(event, "error", None)
        message = "Unknown stream error"

        if error_obj:
            if hasattr(error_obj, "message"):
                message = error_obj.message
            elif isinstance(error_obj, dict):
                message = error_obj.get("message", message)
            else:
                message = str(error_obj)

        return StreamError(message=f"\n[Stream Error] {message}")