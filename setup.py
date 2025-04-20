#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import shutil
import subprocess
from PyQt5.QtWidgets import QApplication
from cx_Freeze import setup, Executable

# アプリケーションのバージョン
VERSION = "1.0.0"

# ビルド設定
build_exe_options = {
    "packages": ["os", "sys", "sqlite3", "PyQt5", "PyQt5.QtCore", "PyQt5.QtGui", 
                "PyQt5.QtWidgets", "PyQt5.QtMultimedia", "PyQt5.QtMultimediaWidgets"],
    "excludes": ["tkinter", "matplotlib", "numpy", "scipy"],
    "include_files": [
        # 必要なファイルをここに追加
        "database_manager.py",
        "thumbnail_viewer.py",
        "video_player.py",
        "video_preview_app.py",
        "README.md"
    ],
    "include_msvcr": True,
}

# 実行ファイル設定
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # Windows GUIアプリケーション

executables = [
    Executable(
        "video_preview_app.py",  # メインスクリプト
        base=base,
        target_name="VideoPreviewApp",  # 出力ファイル名
        icon=None,  # アイコンファイル（必要に応じて追加）
        shortcut_name="ビデオプレビューアプリ",
        shortcut_dir="DesktopFolder",
        copyright="Copyright (c) 2025",
    )
]

# セットアップ
setup(
    name="VideoPreviewApp",
    version=VERSION,
    description="ビデオプレビューアプリケーション",
    options={"build_exe": build_exe_options},
    executables=executables,
)

# ビルドとパッケージング用のメイン関数
def main():
    # READMEファイルの作成
    create_readme()
    
    # ビルドディレクトリのクリーンアップ
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    # cx_Freezeでビルド
    build_cmd = [sys.executable, "setup.py", "build"]
    subprocess.run(build_cmd, check=True)
    
    print("ビルド完了！")
    print(f"ビルドディレクトリ: {os.path.abspath('build')}")

def create_readme():
    """README.mdファイルを作成"""
    readme_content = """# ビデオプレビューアプリケーション

## 概要
このアプリケーションは、SQLiteデータベースに格納された動画シーン情報を表示し、サムネイル画像の閲覧と動画のプレビュー再生を行うためのツールです。

## 機能
- SQLiteデータベースからの動画・シーン情報の読み込み
- サムネイル画像のグリッド表示
- シーン情報（説明、文字起こし、時間情報）の表示
- サムネイルをダブルクリックして動画プレビュー再生
- シーン検索機能

## 使用方法
1. アプリケーションを起動
2. 「データベース選択...」ボタンをクリックしてSQLiteデータベースファイルを選択
3. 動画選択コンボボックスから表示したい動画を選択
4. サムネイルグリッドからシーンを選択（ダブルクリックで再生）
5. 検索ボックスを使用して特定のシーンを検索

## 必要環境
- Windows 10/11、macOS、Linux
- 画面解像度: 1280x720以上推奨

## 注意事項
- 動画ファイルはデータベースに記録されたパスに存在する必要があります
- キーフレーム画像はデータベースに記録されたパスに存在する必要があります

## トラブルシューティング
- データベースが読み込めない場合は、ファイルパスとアクセス権を確認してください
- 動画が再生されない場合は、ファイルパスと対応するコーデックがインストールされているか確認してください

## 連絡先
問題や質問がある場合は、開発者までご連絡ください。
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("README.mdファイルを作成しました")

if __name__ == "__main__":
    main()
