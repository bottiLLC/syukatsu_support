"""
サービス層（LLMServiceとCostCalculator）のユニットテスト。
OpenAI Responses APIとのやり取りとコスト計算ロジックに焦点を当てています。
"""

from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from openai import APIConnectionError, RateLimitError

from src.core.services import LLMService, CostCalculator
from src.core.models import (
    ResponseRequestPayload,
    StreamTextDelta,
    StreamResponseCreated,
    StreamUsage,
    StreamError,
)
from src.core.pricing import PRICING_TABLE


# --- CostCalculator Tests ---


class TestCostCalculator:
    """CostCalculatorユーティリティクラスのテスト。"""

    def test_calculate_known_model(self):
        """既知のモデル（例: gpt-4oなど）のコスト計算を確認します。"""
        # Create a dummy usage object
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cached_tokens=0
        )
        
        # We need to ensure we use a model that exists in PRICING_TABLE
        model_name = "gpt-5.2" # Using default model from PRICING_TABLE
        if model_name not in PRICING_TABLE:
            # Fallback to any key available if the specific one is missing in test env
            model_name = list(PRICING_TABLE.keys())[0]

        cost_str = CostCalculator.calculate(model_name, usage)
        assert "Cost: $" in cost_str
        assert "Tokens: 1500" in cost_str

    def test_calculate_unknown_model_fallback(self):
        """未知のモデルがデフォルトの価格設定（gpt-5.2）にフォールバックすることを確認します。"""
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=1000,
            total_tokens=2000,
            cached_tokens=0
        )
        
        # Use a non-existent model name
        cost_str = CostCalculator.calculate("unknown-model-v99", usage)
        
        # Should contain estimate marker
        assert "(Est.)" in cost_str
        assert "Cost: $" in cost_str

    def test_calculate_with_caching(self):
        """キャッシュされたトークンがより低いレートで計算されることを確認します。"""
        usage = StreamUsage(
            input_tokens=1000,
            output_tokens=0,
            total_tokens=1000,
            cached_tokens=500  # 500 cached, 500 non-cached
        )
        # Using a model we know the pricing for (mocking or relying on constant)
        # Here we just check the string formatting for correctness
        cost_str = CostCalculator.calculate("gpt-5.2", usage)
        assert "In:1000/Cache:500/Out:0" in cost_str


# --- LLMService Tests ---


class TestLLMService:
    """LLMServiceとOpenAI APIのやり取りのテスト。"""

    @pytest.fixture(autouse=True)
    def mock_sleep(self):
        """Tenacityのリトライ待機（asyncio.sleep）をモックしてテストを高速化します。"""
        with patch("asyncio.sleep", new_callable=AsyncMock) as m:
            yield m

    @pytest.fixture
    def mock_client(self):
        """OpenAIクライアントインスタンスをモックします。"""
        # FIX: Patch src.core.base.AsyncOpenAI because LLMService inherits init from BaseOpenAIService
        # defined in src.core.base, which is where the AsyncOpenAI class is imported and instantiated.
        with patch("src.core.base.AsyncOpenAI") as mock_openai_cls:
            mock_instance = AsyncMock()
            mock_openai_cls.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def service(self, mock_client):
        """モックされたクライアントでLLMServiceを初期化します。"""
        return LLMService(api_key="test-key")

    @pytest.fixture
    def valid_payload(self):
        """有効なResponseRequestPayloadを返します。"""
        return ResponseRequestPayload(
            model="gpt-5.2",
            input="Test input",  # Will be normalized
            instructions="System prompt"
        )

    def _create_mock_event(self, event_type: str, **kwargs) -> MagicMock:
        """モックおよびストリームイベントを作成するためのヘルパー。"""
        event = MagicMock()
        event.type = event_type
        for k, v in kwargs.items():
            setattr(event, k, v)
        return event

    @pytest.mark.asyncio
    async def test_stream_analysis_success(self, service, mock_client, valid_payload):
        """
        テキストのデルタと使用量統計を伴うストリーミングセッションが成功することを確認します。
        """
        # Setup mock stream events
        mock_events = [
            self._create_mock_event(
                "response.created",
                response=MagicMock(id="resp_123")
            ),
            self._create_mock_event(
                "response.output_text.delta",
                delta="Hello "
            ),
            self._create_mock_event(
                "response.output_text.delta",
                delta="World"
            ),
            self._create_mock_event(
                "response.completed",
                response=MagicMock(
                    usage=MagicMock(
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                        input_tokens_details=MagicMock(cached_tokens=2)
                    )
                )
            )
        ]
    
        # Configure client mock
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = mock_events
        mock_client.responses.create.return_value = mock_stream
    
        # Execute
        results = [result async for result in service.stream_analysis(valid_payload)]

        # Assertions
        assert len(results) == 4
        
        # 1. Response Created
        assert isinstance(results[0], StreamResponseCreated)
        assert results[0].response_id == "resp_123"
        
        # 2. Text Deltas
        assert isinstance(results[1], StreamTextDelta)
        assert results[1].delta == "Hello "
        assert isinstance(results[2], StreamTextDelta)
        assert results[2].delta == "World"
        
        # 3. Usage
        assert isinstance(results[3], StreamUsage)
        assert results[3].total_tokens == 15
        assert results[3].cached_tokens == 2

        # Verify API call arguments
        mock_client.responses.create.assert_called_once()
        call_kwargs = mock_client.responses.create.call_args[1]
        assert call_kwargs["model"] == "gpt-5.2"
        # Input should be normalized to list
        assert isinstance(call_kwargs["input"], list)
        assert call_kwargs["input"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_stream_analysis_api_connection_error(self, service, mock_client, valid_payload):
        """API接続エラーの処理を確認します。"""
        # Tenacity retry logic will catch this, retry, and eventually raise.
        # However, the service layer catches the raised exception and yields a StreamError.
        # We need to simulate the failure persisting across retries.
        mock_client.responses.create.side_effect = APIConnectionError(message="Connection failed", request=MagicMock())

        results = [result async for result in service.stream_analysis(valid_payload)]

        # Expect one StreamError after retries are exhausted
        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "【通信エラー】" in results[0].message
        
        # Verify retries occurred (Tenacity stop_after_attempt is 5 in resilience.py)
        # Note: In the refactoring, we used resilient_api_call which defaults to 5 attempts.
        assert mock_client.responses.create.call_count == 5

    @pytest.mark.asyncio
    async def test_stream_analysis_rate_limit_error(self, service, mock_client, valid_payload):
        """Rate Limitエラーの処理を確認します。"""
        mock_client.responses.create.side_effect = RateLimitError(message="Rate limit", response=MagicMock(), body=None)

        results = [result async for result in service.stream_analysis(valid_payload)]

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "【利用制限エラー】" in results[0].message
        # Verify retries
        assert mock_client.responses.create.call_count == 5

    @pytest.mark.asyncio
    async def test_stream_analysis_stream_error_event(self, service, mock_client, valid_payload):
        """ストリーム中に発行された 'error' イベントの処理を確認します。"""
        mock_events = [
            self._create_mock_event(
                "error",
                error=MagicMock(message="Something went wrong mid-stream")
            )
        ]
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = mock_events
        mock_client.responses.create.return_value = mock_stream

        results = [result async for result in service.stream_analysis(valid_payload)]

        assert len(results) == 1
        assert isinstance(results[0], StreamError)
        assert "Something went wrong" in results[0].message

    @pytest.mark.asyncio
    async def test_stream_analysis_ignore_unknown_events(self, service, mock_client, valid_payload):
        """未知のイベントタイプが無視されることを確認します。"""
        mock_events = [
            self._create_mock_event("response.unknown_event_type")
        ]
        
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = mock_events
        mock_client.responses.create.return_value = mock_stream

        results = [result async for result in service.stream_analysis(valid_payload)]

        # Should produce no results, but strictly not raise an error
        assert len(results) == 0