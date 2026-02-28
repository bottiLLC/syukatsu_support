import asyncio
import os
import sys
import time
import tkinter as tk
from unittest.mock import patch

from src.config.app_config import ConfigManager
from src.ui.main_model import MainModel
from src.ui.main_view import MainView
from src.ui.main_presenter import MainPresenter

def run_e2e_test_with_mock():
    print("Starting E2E simulation test with MOCK API...")
    
    config = ConfigManager.load()
    config.api_key = "dummy_api_key"
            
    model = MainModel()
    view = MainView(config)
    
    # Hide the MainView window
    view.withdraw()
    
    presenter = MainPresenter(view, model)
    
    # Simulate user input
    test_msg = "これは自動E2Eテストです。"
    view._input_view.insert("1.0", test_msg)
    
    print(f"Sending prompt: {test_msg}")
    
    # Mock the AsyncOpenAI client's responses.create
    class AsyncMockStream:
        async def __aiter__(self):
            # Simulate typical StreamTextDelta event
            class MockEvent1:
                type = "response.output_text.delta"
                delta = "テスト成功"
                
            class MockEvent2:
                type = "response.completed"
                response = type('obj', (), {
                    'usage': type('usage_obj', (), {
                        'input_tokens': 10,
                        'output_tokens': 5,
                        'total_tokens': 15,
                        'input_tokens_details': type('details_obj', (), {'cached_tokens': 0})()
                    })()
                })()
                
            yield MockEvent1()
            # Small delay
            await asyncio.sleep(0.1)
            yield MockEvent2()

    with patch('src.core.services.AsyncOpenAI') as MockAsyncClient:
        # Client instance mock
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value
        
        # Async stream mock
        mock_client_instance.responses.create.return_value = AsyncMockStream()
        
        # Trigger generation
        presenter.handle_start_generation()
        
        # Wait for completion
        timeout = 10 # 10 seconds max for mock
        start_time = time.time()
        
        print("Waiting for response...")
        while model.is_generating and (time.time() - start_time) < timeout:
            view.update()
            time.sleep(0.1)
            
    if model.is_generating:
        print("Timeout! Generation did not complete in time.")
        presenter.handle_stop_generation()
        sys.exit(1)
        
    log_content = view.get_log_content()
    print("\n--- Interaction Log ---")
    print(log_content)
    print("-----------------------\n")
    
    if "[エラー]" in log_content or "Error" in log_content:
        print("Test FAILED: Error found in log.")
        sys.exit(1)
        
    if "テスト成功" in log_content:
        print("Test PASSED: Mock response successfully parsed and displayed!")
    else:
        print("Test FAILED: Mock response content not found in log.")
        sys.exit(1)
        
    # Cleanup
    view.destroy()

if __name__ == "__main__":
    run_e2e_test_with_mock()
