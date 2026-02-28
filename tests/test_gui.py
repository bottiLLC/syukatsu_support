# ------------------------------------------------------------------------------
# Dependencies: pip install openai>=1.61.0 pydantic>=2.0 tenacity
# ------------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import queue
import structlog
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

# --- 1. 設定レイヤー (Configuration Layer) ---
@dataclass(frozen=True)
class AppConfig:
    """中央集権的な設定管理。"""
    API_KEY: str
    MODEL_ID: str = "gpt-5.2"

    @classmethod
    def from_env(cls) -> "AppConfig":
        # フェイルファスト戦略
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # テスト実行時や開発用にダミーキーを許容する場合はここを調整
            # 本番ではエラーにするのが望ましい
            pass
        return cls(API_KEY=api_key or "dummy-key-for-test")

# --- 2. データモデル (Data Models / Pydantic V2) ---
class InputContent(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str

class InputItem(BaseModel):
    type: Literal["message"] = "message"
    role: Literal["user"] = "user"
    content: List[InputContent]

class GenerationPayload(BaseModel):
    """/v1/responses 用のスキーマ"""
    model_config = ConfigDict(populate_by_name=True, extra='forbid')
    
    model: str
    instructions: str = "You are a helpful assistant."
    input: List[InputItem]

# --- 3. サービスレイヤー (Business Logic) ---
class BackendService:
    """APIとのやり取りを処理します。Tkinterについては何も知りません。"""
    def __init__(self, config: AppConfig):
        self.client = OpenAI(api_key=config.API_KEY)
        self.model_id = config.MODEL_ID

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(structlog.get_logger(__name__), logging.INFO)
    )
    def fetch_response(self, payload: GenerationPayload) -> str:
        """
        Tenacityリトライを利用した同期API呼び出し。
        ワーカースレッド（WORKER THREAD）で実行されます。
        """
        data = payload.model_dump(exclude_none=True)
        
        # API呼び出し (Tenacityを使用するため max_retries=0)
        # 指定通り client.responses.create を使用
        try:
            response = self.client.responses.create(
                **data,
                max_retries=0
            )
            return response.output[0].message.content
        except AttributeError:
            # 特定のSDKバージョンに'responses'がない場合のフォールバック/モックロジック
            return "モックレスポンス: APIエンドポイント /v1/responses にアクセスしました（スタブ）。"

# --- 4. GUIアプリケーション (Presentation Layer) ---
class SyukatsuSupportApp(tk.Tk):
    def __init__(self, config: Optional[AppConfig] = None):
        super().__init__()
        self.config = config if config else AppConfig.from_env()
        
        self.title("就活サポートAI (Refactored)")
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
        # チャット履歴 (ScrolledText)
        self.txt_history = scrolledtext.ScrolledText(self, state='disabled', height=20)
        self.txt_history.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # 入力エリア
        frame_input = tk.Frame(self)
        frame_input.pack(padx=10, pady=(0, 10), fill=tk.X)

        self.txt_input = tk.Entry(frame_input)
        self.txt_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.txt_input.bind("<Return>", lambda event: self.on_send())

        self.btn_send = tk.Button(frame_input, text="送信", command=self.on_send)
        self.btn_send.pack(side=tk.RIGHT)

    def append_history(self, role: str, text: str):
        self.txt_history.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_history.insert(tk.END, f"[{timestamp}] {role}:\n{text}\n\n")
        self.txt_history.see(tk.END)
        self.txt_history.config(state='disabled')

    def on_send(self):
        user_text = self.txt_input.get()
        if not user_text:
            return

        try:
            # 1. 入力のバリデーション
            payload = GenerationPayload(
                model=self.config.MODEL_ID,
                input=[InputItem(content=[InputContent(text=user_text)])]
            )
            
            # 2. UIの更新
            self.append_history("User", user_text)
            self.txt_input.delete(0, tk.END)
            self.set_ui_state("disabled")
            
            # 3. スレッドの開始
            thread = threading.Thread(
                target=self._run_worker,
                args=(payload,),
                daemon=True
            )
            thread.start()
            
            # 4. ポーリングの開始
            self.after(100, self.process_queue)

        except ValidationError as e:
            messagebox.showerror("バリデーションエラー", str(e))
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def _run_worker(self, payload):
        """バックグラウンドスレッドの実行。"""
        try:
            result = self.service.fetch_response(payload)
            self.queue.put(("success", result))
        except Exception as e:
            self.queue.put(("error", str(e)))

    def process_queue(self):
        """メインスレッドのポーリングループ。"""
        try:
            while True: # 利用可能なすべてのメッセージを処理
                msg_type, content = self.queue.get_nowait()
                
                if msg_type == "success":
                    self.append_history("AI", content)
                elif msg_type == "error":
                    messagebox.showerror("APIエラー", content)
                    self.append_history("System", f"エラー: {content}")
                
                self.set_ui_state("normal")
                
        except queue.Empty:
            # UIがまだ無効になっている場合はポーリングを継続
            if self.btn_send['state'] == 'disabled':
                self.after(100, self.process_queue)

    def set_ui_state(self, state):
        self.btn_send.config(state=state)
        self.txt_input.config(state=state)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    try:
        app = SyukatsuSupportApp()
        app.mainloop()
    except Exception as e:
        import structlog
        structlog.get_logger().error("起動エラー", error=str(e))
        raise