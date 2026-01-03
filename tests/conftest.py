import sys
import os

# プロジェクトのルートディレクトリを sys.path に追加
# これにより、tests ディレクトリから 'src' モジュールをインポートできるようになります
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))