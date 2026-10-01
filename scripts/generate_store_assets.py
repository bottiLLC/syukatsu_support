# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# Windows Store アセット自動生成スクリプト (generate_store_assets.py)
# 外部依存なし（Python標準ライブラリ zlib, struct のみ）で Windows Store 準拠の PNG を生成します。

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def create_png_image(
    width: int,
    height: int,
    bg_color: tuple[int, int, int, int] = (44, 62, 80, 255),  # #2c3e50
    accent_color: tuple[int, int, int, int] = (22, 160, 133, 255),  # #16a085
) -> bytes:
    """指定解像度のブランドロゴ PNG バイナリを生成します。"""
    raw_scanlines = bytearray()
    center_x = width // 2
    center_y = height // 2
    emblem_radius = min(width, height) // 3

    for y in range(height):
        raw_scanlines.append(0)  # Filter type 0 (None)
        for x in range(width):
            dx = abs(x - center_x)
            dy = abs(y - center_y)
            # 中央にアクセントカラーの菱形エンブレムを描画
            if (dx + dy) <= emblem_radius:
                raw_scanlines.extend(accent_color)
            elif (dx + dy) <= emblem_radius + 2 and min(width, height) > 50:
                raw_scanlines.extend((255, 255, 255, 220))
            else:
                raw_scanlines.extend(bg_color)

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    # PNG ヘッダー
    png_header = b"\x89PNG\r\n\x1a\n"
    # IHDR チャンク: width, height, bit_depth=8, color_type=6 (RGBA), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_chunk = make_chunk(b"IHDR", ihdr_data)
    # IDAT チャンク
    idat_chunk = make_chunk(b"IDAT", zlib.compress(bytes(raw_scanlines), level=9))
    # IEND チャンク
    iend_chunk = make_chunk(b"IEND", b"")

    return png_header + ihdr_chunk + idat_chunk + iend_chunk


def generate_all_assets(target_dir: Path | None = None) -> None:
    """Windows Store 申請に必要な全解像度のアセットを出力します。"""
    if target_dir is None:
        target_dir = Path(__file__).resolve().parent.parent / "assets"

    target_dir.mkdir(parents=True, exist_ok=True)

    assets_specs = [
        ("StoreLogo.png", 50, 50),
        ("Square44x44Logo.png", 44, 44),
        ("Square150x150Logo.png", 150, 150),
        ("Wide310x150Logo.png", 310, 150),
        ("SplashScreen.png", 620, 300),
    ]

    for filename, w, h in assets_specs:
        file_path = target_dir / filename
        data = create_png_image(w, h)
        file_path.write_bytes(data)
        print(f"[GENERATED] {file_path.name} ({w}x{h}, {len(data)} bytes)")


if __name__ == "__main__":
    generate_all_assets()
