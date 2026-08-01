# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# 
# PyInstaller 自動ビルド & 検証スクリプト (build.py)

import os
import sys
import subprocess
from pathlib import Path

def main():
    project_dir = Path(__file__).resolve().parent
    spec_file = project_dir / "build_exe.spec"
    dist_dir = project_dir / "dist"
    target_exe = dist_dir / "syukatsu-support.exe"

    print("=" * 60)
    print("  SYUKATSU Support - Executable Build & Verification Script")
    print("=" * 60)
    print(f"[INFO] Project Root: {project_dir}")
    print(f"[INFO] Spec File:    {spec_file}")
    print()

    # 1. 実行中の同一プロセスの終了確認
    print("[1/4] Checking and terminating running instances...")
    if os.name == "nt":
        for proc_name in ["syukatsu-support.exe", "flet.exe", "flet_desktop.exe"]:
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True)

    # 2. PyInstaller ビルド実行
    print("[2/4] Executing PyInstaller build via 'uv run pyinstaller build_exe.spec -y'...")
    cmd = ["uv", "run", "pyinstaller", "build_exe.spec", "-y"]
    result = subprocess.run(cmd, cwd=project_dir)

    if result.returncode != 0:
        print("\n[ERROR] PyInstaller build failed with exit code:", result.returncode)
        sys.exit(result.returncode)

    # 3. 成果物の検証
    print("\n[3/4] Verifying generated build artifacts...")
    if not target_exe.exists():
        print(f"[ERROR] Expected executable not found at: {target_exe}")
        sys.exit(1)

    size_mb = target_exe.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Executable created: {target_exe}")
    print(f"[INFO] File Size: {size_mb:.2f} MB")

    # 4. 外部リソース検証
    json_path = project_dir / "system_prompts.json"
    if not json_path.exists():
        print("[WARNING] system_prompts.json does not exist in root!")
    else:
        print(f"[INFO] Source system_prompts.json confirmed ({json_path.stat().st_size} bytes)")

    print("\n" + "=" * 60)
    print("  Build completed successfully! Product ready in dist/syukatsu-support.exe")
    print("=" * 60)

if __name__ == "__main__":
    main()
