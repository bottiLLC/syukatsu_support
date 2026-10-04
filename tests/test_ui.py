# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""UIコンポーネントおよびFletシリアライゼーションの単体テスト。"""

from unittest.mock import MagicMock

import flet as ft
import msgpack  # type: ignore[import-untyped]
import pytest
from flet.controls.base_control import BaseControl
from flet.messaging.flet_socket_server import configure_encode_object_for_msgpack  # type: ignore[attr-defined]

from src.models import ViewMode
from src.state import AppState
from src.ui import SyukatsuSupportApp


@pytest.mark.asyncio
async def test_ui_segmented_button_serialization_integrity() -> None:
    """SegmentedButtonのselectedプロパティがmsgpackで正常にシリアライズ可能であることを検証します。"""
    page = MagicMock(spec=ft.Page)
    page.window = MagicMock()
    page.overlay = []

    state = AppState()
    app = SyukatsuSupportApp(page, state)

    # 1. 初期構築時の selected が list[str] であることの検証
    assert isinstance(app.mode_segment.selected, list)
    assert app.mode_segment.selected == [ViewMode.SIMPLE.value]

    # 2. msgpack パッキングが例外なく完了することの検証
    packed_initial = msgpack.packb(
        ["patchControl", app.mode_segment],
        default=configure_encode_object_for_msgpack(BaseControl),  # type: ignore[no-untyped-call]
    )
    assert isinstance(packed_initial, bytes)
    assert len(packed_initial) > 0

    # 3. state との同期後も list[str] が保持されシリアライズ可能であることの検証
    await state.set_view_mode(ViewMode.ADVANCED)
    assert isinstance(app.mode_segment.selected, list)
    assert app.mode_segment.selected == [ViewMode.ADVANCED.value]

    packed_updated = msgpack.packb(
        ["patchControl", app.mode_segment],
        default=configure_encode_object_for_msgpack(BaseControl),  # type: ignore[no-untyped-call]
    )
    assert isinstance(packed_updated, bytes)
    assert len(packed_updated) > 0
