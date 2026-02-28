"""
就活サポートGUIアプリケーション（MVPファクトリー）。

このモジュールはメインウィンドウのMVPパターンのコンポーネントを接続します：
- MainModel
- MainView
- MainPresenter
"""

import structlog

from src.ui.main_model import MainModel
from src.ui.main_view import MainView
from src.ui.main_presenter import MainPresenter

log = structlog.get_logger()

class SyukatsuSupportApp:
    """
    MVPコンポーネントを接続するメインアプリケーションのラッパー。
    main.pyでの後方互換性のために、古いtk.Tkサブクラスと同じインターフェースを提供します。
    """

    def __init__(self) -> None:
        log.info("MVPアーキテクチャの初期化中... Model -> View -> Presenter を作成")
        self.model = MainModel()
        self.view = MainView(self.model.user_config)
        self.presenter = MainPresenter(self.view, self.model)

    def mainloop(self) -> None:
        """Tkinterのメインループを開始します。"""
        self.view.mainloop()