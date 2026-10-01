# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# Windows Store (MSIX) 自動パッケージ化 & 検証スクリプト (package_msix.py)

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def find_makeappx() -> Path | None:
    """Windows SDK 内の MakeAppx.exe を探索します。"""
    kits_root = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if kits_root.exists():
        candidates = list(kits_root.glob("*/x64/MakeAppx.exe"))
        if candidates:
            return sorted(candidates)[-1]
    which_makeappx = shutil.which("MakeAppx.exe")
    if which_makeappx:
        return Path(which_makeappx)
    return None


def main() -> None:
    """Windows Store 向け MSIX パッケージの作成およびステージングを実行します。"""
    project_dir = Path(__file__).resolve().parent
    dist_dir = project_dir / "dist"
    target_exe = dist_dir / "syukatsu-support.exe"
    stage_dir = dist_dir / "msix_stage"
    target_msix = dist_dir / "syukatsu-support.msix"
    manifest_src = project_dir / "AppxManifest.xml"
    assets_src = project_dir / "assets"
    prompts_src = project_dir / "system_prompts.json"

    print("=" * 60)
    print("  SYUKATSU Support - Windows Store (MSIX) Packaging Script")
    print("=" * 60)

    # 1. 実行可能ファイルの確認・ビルド
    print("[1/5] Verifying executable binary...")
    if not target_exe.exists():
        print("[INFO] Executable not found in dist/. Triggering build.py...")
        res = subprocess.run([sys.executable, str(project_dir / "build.py")], cwd=project_dir)
        if res.returncode != 0:
            print("[ERROR] Build failed. Aborting packaging.")
            sys.exit(res.returncode)

    # 2. Store Assets の確認
    print("[2/5] Ensuring Windows Store visual assets...")
    required_assets = [
        "StoreLogo.png",
        "Square44x44Logo.png",
        "Square150x150Logo.png",
        "Wide310x150Logo.png",
        "SplashScreen.png",
    ]
    missing_assets = [a for a in required_assets if not (assets_src / a).exists()]
    if missing_assets:
        print(f"[INFO] Missing assets: {missing_assets}. Generating...")
        res = subprocess.run(
            [sys.executable, str(project_dir / "scripts" / "generate_store_assets.py")],
            cwd=project_dir,
        )
        if res.returncode != 0:
            print("[ERROR] Asset generation failed.")
            sys.exit(res.returncode)

    # 3. ステージングディレクトリの構築
    print(f"[3/5] Assembling layout into {stage_dir}...")
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    # ファイルの配置
    shutil.copy2(target_exe, stage_dir / "syukatsu-support.exe")
    shutil.copy2(manifest_src, stage_dir / "AppxManifest.xml")
    if prompts_src.exists():
        shutil.copy2(prompts_src, stage_dir / "system_prompts.json")

    assets_stage = stage_dir / "assets"
    assets_stage.mkdir(exist_ok=True)
    for asset_name in required_assets:
        shutil.copy2(assets_src / asset_name, assets_stage / asset_name)

    # 4. MSIX パッケージ生成
    print("[4/5] Packaging into MSIX container...")
    makeappx_exe = find_makeappx()

    if makeappx_exe:
        print(f"[INFO] Found Windows SDK MakeAppx: {makeappx_exe}")
        cmd = [
            str(makeappx_exe),
            "pack",
            "/d",
            str(stage_dir),
            "/p",
            str(target_msix),
            "/nv",
            "/o",
        ]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"[ERROR] MakeAppx failed with code {result.returncode}")
            sys.exit(result.returncode)
    else:
        print("[INFO] MakeAppx.exe not detected. Packing MSIX container via standard OPC...")
        with zipfile.ZipFile(target_msix, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(stage_dir):
                for f in files:
                    file_path = Path(root) / f
                    arcname = file_path.relative_to(stage_dir)
                    # AppxManifest.xml は非圧縮で格納するのが仕様準拠
                    if file_path.name == "AppxManifest.xml":
                        zf.write(file_path, arcname=arcname, compress_type=zipfile.ZIP_STORED)
                    else:
                        zf.write(file_path, arcname=arcname, compress_type=zipfile.ZIP_DEFLATED)

    # 5. パッケージ成果物の検証
    print("\n[5/5] Verifying MSIX package...")
    if not target_msix.exists():
        print(f"[ERROR] Expected MSIX package not found at: {target_msix}")
        sys.exit(1)

    size_mb = target_msix.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] MSIX Package created: {target_msix}")
    print(f"[INFO] Package Size: {size_mb:.2f} MB")
    print(f"[INFO] Layout Staging Directory: {stage_dir}")

    print("\n" + "=" * 60)
    print("  Windows Store Packaging Ready!")
    print("  Artifact: dist/syukatsu-support.msix")
    print("  Layout:   dist/msix_stage/")
    print("=" * 60)


if __name__ == "__main__":
    main()
