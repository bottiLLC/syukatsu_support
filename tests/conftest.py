import sys
import os

# Set environment variable to prevent Pydantic building models eagerly which causes MemoryError in tests
os.environ["DEFER_PYDANTIC_BUILD"] = "true"

# プロジェクトのルートディレクトリを sys.path に追加
# これにより、tests ディレクトリから 'src' モジュールをインポートできるようになります
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))