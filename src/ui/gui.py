"""
Job Hunting Support GUI Application (MVP Factory).

This module connects the components of the Main Window MVP pattern:
- MainModel
- MainView
- MainPresenter
"""

import logging

from src.ui.main_model import MainModel
from src.ui.main_view import MainView
from src.ui.main_presenter import MainPresenter

logger = logging.getLogger(__name__)

class SyukatsuSupportApp:
    """
    Main application wrapper connecting MVP components.
    Provides the same interface as the old tk.Tk subclass
    for backwards compatibility in main.py.
    """

    def __init__(self) -> None:
        logger.info("Initializing MVP Architecture... Creating Model -> View -> Presenter")
        self.model = MainModel()
        self.view = MainView(self.model.user_config)
        self.presenter = MainPresenter(self.view, self.model)

    def mainloop(self) -> None:
        """Starts the Tkinter main loop."""
        self.view.mainloop()