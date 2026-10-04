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

    # AppBar タイトルの検証
    assert page.appbar.title.value == "就職活動サポートAI（Powerd by gpt-6.1-sol）"

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


@pytest.mark.asyncio
async def test_ui_step1_card_layout_two_rows() -> None:
    """STEP 1 カードが2行構成（1行目: ラベル/アイコン, 2行目: 設定変更ボタン）であることを検証します。"""
    page = MagicMock(spec=ft.Page)
    page.window = MagicMock()
    page.overlay = []

    state = AppState()
    app = SyukatsuSupportApp(page, state)

    # simple_panel の第1要素が step1_card
    step1_card = app.simple_panel.controls[0]
    assert isinstance(step1_card, ft.Card)
    container = step1_card.content
    assert isinstance(container, ft.Container)
    column = container.content
    assert isinstance(column, ft.Column)
    assert len(column.controls) == 2

    # 1行目: Row (STEP 1, Icon, Label)
    row1 = column.controls[0]
    assert isinstance(row1, ft.Row)
    assert app.simple_api_icon in row1.controls
    assert app.simple_api_label in row1.controls

    # 2行目: Row (設定 / 変更 ボタン)
    row2 = column.controls[1]
    assert isinstance(row2, ft.Row)
    assert app.simple_api_btn in row2.controls
    assert row2.alignment == ft.MainAxisAlignment.END


@pytest.mark.asyncio
async def test_ui_api_key_dialog_horizontal_and_compact() -> None:
    """APIキー設定ダイアログが横長（width指定あり）かつ縦方向展開（expand）無しのコンパクト構成であることを検証します。"""
    page = MagicMock(spec=ft.Page)
    page.window = MagicMock()
    page.overlay = []

    state = AppState()
    app = SyukatsuSupportApp(page, state)

    await app._on_open_api_key_dialog(MagicMock())
    assert len(page.overlay) == 1
    dlg = page.overlay[0]
    assert isinstance(dlg, ft.AlertDialog)

    # content は横幅指定された Container であること
    assert isinstance(dlg.content, ft.Container)
    assert dlg.content.width is not None
    assert dlg.content.width >= 600

    # 中身の Column が tight であること
    col = dlg.content.content
    assert isinstance(col, ft.Column)
    assert col.tight is True

    # key_input (TextField) が縦展開 (expand=True) されておらず、横長 (width >= 600) であること
    key_input = next(c for c in col.controls if isinstance(c, ft.TextField))
    assert not key_input.expand
    assert key_input.width is not None and key_input.width >= 600


@pytest.mark.asyncio
async def test_ui_api_key_sync_status() -> None:
    """APIキー設定状態の反映と『登録完了』緑色表示への同期を検証します。"""
    page = MagicMock(spec=ft.Page)
    page.window = MagicMock()
    page.overlay = []

    state = AppState()
    state.config.api_key = None

    app = SyukatsuSupportApp(page, state)
    await app._sync_from_state()

    # 未設定時
    assert app.simple_api_label.value == "APIキー: 未設定 (要登録)"
    assert app.simple_api_label.color == ft.Colors.RED_800
    assert app.simple_api_icon.icon == ft.Icons.WARNING

    # APIキー登録時
    await state.update_api_key("sk-test1234567890abcdef", silent=True)
    assert app.simple_api_label.value == "登録完了"
    assert app.simple_api_label.color == ft.Colors.GREEN_700
    assert app.simple_api_icon.icon == ft.Icons.CHECK_CIRCLE
    assert app.simple_api_icon.color == ft.Colors.GREEN_600


@pytest.mark.asyncio
async def test_preset_submit_resets_context_and_suppresses_user_prompt(tmp_path: object) -> None:
    """かんたんモードのプリセット実行時にコンテキストがリセットされユーザープロンプト表示が抑制されることを検証します。"""
    page = MagicMock(spec=ft.Page)
    page.window = MagicMock()
    page.overlay = []

    # テスト用ダミーPDF作成
    pdf_file = tmp_path / "dummy.pdf"  # type: ignore[operator]
    pdf_file.write_bytes(b"%PDF-1.4 dummy content")

    state = AppState()
    state.config.api_key = "sk-test123456789"
    state.config.active_pdf_path = str(pdf_file)
    state.config.last_response_id = "resp_previous_chain_999"

    app = SyukatsuSupportApp(page, state)

    # 既存のチャット表示を追加
    app.chat_list.controls.append(ft.Text("過去のチャット結果"))

    received_tags: list[str] = []

    async def mock_text_delta(text: str, tag: str) -> None:
        received_tags.append(tag)

    state.on_text_delta = mock_text_delta

    # handle_submit をモックして呼び出し引数を検証
    recorded_calls: list[dict[str, object]] = []

    async def mock_handle_submit(user_input: str, system_prompt: str, show_user_prompt: bool = True) -> None:
        recorded_calls.append(
            {
                "user_input": user_input,
                "system_prompt": system_prompt,
                "show_user_prompt": show_user_prompt,
            }
        )

    state.handle_submit = mock_handle_submit  # type: ignore[assignment]

    from src.core.prompts import MODE_FINANCIAL

    await state.handle_preset_submit(MODE_FINANCIAL)

    # 1. 過去のレスポンスIDがクリア（新規チャット化）されていること
    assert state.config.last_response_id is None
    # 2. チャットログがクリアされていること
    assert len(app.chat_list.controls) == 0
    # 3. show_user_prompt=False で実行されたこと
    assert len(recorded_calls) == 1
    assert recorded_calls[0]["show_user_prompt"] is False
