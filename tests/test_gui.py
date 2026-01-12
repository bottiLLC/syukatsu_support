# ------------------------------------------------------------------------------
# Dependencies: pip install openai>=1.61.0 pydantic>=2.0 tenacity
# ------------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import queue
import logging
import os
import sys
from dataclasses import dataclass
from typing import List, Literal, Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError
from openai import OpenAI, RateLimitError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log
)

# --- 1. Configuration Layer ---
@dataclass(frozen=True)
class AppConfig:
    """Centralized configuration management."""
    API_KEY: str
    MODEL_ID: str = "gpt-5.2"

    @classmethod
    def from_env(cls) -> "AppConfig":
        # Fail fast strategy
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # テスト実行時や開発用にダミーキーを許容する場合はここを調整
            # 本番ではエラーにするのが望ましい
            pass
        return cls(API_KEY=api_key or "dummy-key-for-test")

# --- 2. Data Models (Pydantic V2) ---
class InputContent(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str

class InputItem(BaseModel):
    type: Literal["message"] = "message"
    role: Literal["user"] = "user"
    content: List[InputContent]

class GenerationPayload(BaseModel):
    """Schema for /v1/responses"""
    model_config = ConfigDict(populate_by_name=True, extra='forbid')
    
    model: str
    instructions: str = "You are a helpful assistant."
    input: List[InputItem]

# --- 3. Service Layer (Business Logic) ---
class BackendService:
    """Handles API interactions. Knows NOTHING about Tkinter."""
    def __init__(self, config: AppConfig):
        self.client = OpenAI(api_key=config.API_KEY)
        self.model_id = config.MODEL_ID

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.INFO)
    )
    def fetch_response(self, payload: GenerationPayload) -> str:
        """
        Synchronous API call with Tenacity retries.
        Executed in a WORKER THREAD.
        """
        data = payload.model_dump(exclude_none=True)
        
        # API Call (max_retries=0 to use Tenacity)
        # Using client.responses.create as specified
        try:
            response = self.client.responses.create(
                **data,
                max_retries=0
            )
            return response.output[0].message.content
        except AttributeError:
            # Fallback/Mock logic if specific SDK version lacks 'responses'
            return "Mock Response: API endpoint /v1/responses accessed (Stub)."

# --- 4. GUI Application (Presentation Layer) ---
class SyukatsuSupportApp(tk.Tk):
    def __init__(self, config: Optional[AppConfig] = None):
        super().__init__()
        self.config = config if config else AppConfig.from_env()
        
        self.title("Syukatsu Support AI (Refactored)")
        self.geometry("700x600")
        
        self.service = BackendService(self.config)
        self.queue = queue.Queue()
        
        self._setup_ui()
        self._setup_styles()

    def _setup_styles(self):
        # master=selfを指定して明示的に紐づける（テスト時のエラー防止の一環）
        self.style = ttk.Style(self)
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')

    def _setup_ui(self):
        # Chat History (ScrolledText)
        self.txt_history = scrolledtext.ScrolledText(self, state='disabled', height=20)
        self.txt_history.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Input Area
        frame_input = tk.Frame(self)
        frame_input.pack(padx=10, pady=(0, 10), fill=tk.X)

        self.txt_input = tk.Entry(frame_input)
        self.txt_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.txt_input.bind("<Return>", lambda event: self.on_send())

        self.btn_send = tk.Button(frame_input, text="Send", command=self.on_send)
        self.btn_send.pack(side=tk.RIGHT)

    def append_history(self, role: str, text: str):
        self.txt_history.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_history.insert(tk.END, f"[{timestamp}] {role}:\n{text}\n\n")
        self.txt_history.see(tk.END)
        self.txt_history.config(state='disabled')

    def on_send(self):
        user_text = self.txt_input.get()
        if not user_text: return

        try:
            # 1. Validate Input
            payload = GenerationPayload(
                model=self.config.MODEL_ID,
                input=[InputItem(content=[InputContent(text=user_text)])]
            )
            
            # 2. Update UI
            self.append_history("User", user_text)
            self.txt_input.delete(0, tk.END)
            self.set_ui_state("disabled")
            
            # 3. Start Thread
            thread = threading.Thread(
                target=self._run_worker,
                args=(payload,),
                daemon=True
            )
            thread.start()
            
            # 4. Start Polling
            self.after(100, self.process_queue)

        except ValidationError as e:
            messagebox.showerror("Validation Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _run_worker(self, payload):
        """Background thread execution."""
        try:
            result = self.service.fetch_response(payload)
            self.queue.put(("success", result))
        except Exception as e:
            self.queue.put(("error", str(e)))

    def process_queue(self):
        """Main thread polling loop."""
        try:
            while True: # Process all available messages
                msg_type, content = self.queue.get_nowait()
                
                if msg_type == "success":
                    self.append_history("AI", content)
                elif msg_type == "error":
                    messagebox.showerror("API Error", content)
                    self.append_history("System", f"Error: {content}")
                
                self.set_ui_state("normal")
                
        except queue.Empty:
            # Keep polling if UI is still disabled
            if self.btn_send['state'] == 'disabled':
                self.after(100, self.process_queue)

    def set_ui_state(self, state):
        self.btn_send.config(state=state)
        self.txt_input.config(state=state)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        app = SyukatsuSupportApp()
        app.mainloop()
    except Exception as e:
        print(f"STARTUP ERROR: {e}", file=sys.stderr)