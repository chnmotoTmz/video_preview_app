#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QLabel, QComboBox, 
                            QScrollArea, QPushButton, QSplitter, QFrame,
                            QTextEdit)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QUrl
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

class DatabaseManager:
    """SQLiteデータベースとの接続と操作を管理するクラス"""
    
    def __init__(self, db_path):
        """
        初期化関数
        
        Args:
            db_path (str): SQLiteデータベースファイルのパス
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """データベースに接続"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            return True
        except sqlite3.Error as e:
            print(f"データベース接続エラー: {e}")
            return False
            
    def close(self):
        """データベース接続を閉じる"""
        if self.conn:
            self.conn.close()
            
    def get_videos(self):
        """
        すべての動画情報を取得
        
        Returns:
            list: 動画情報の辞書のリスト
        """
        if not self.conn:
            return []
            
        try:
            self.cursor.execute("""
            SELECT video_id, source_filepath, duration_seconds, creation_time
            FROM videos
            ORDER BY video_id
            """)
            
            videos = []
            for row in self.cursor.fetchall():
                videos.append({
                    'video_id': row['video_id'],
                    'source_filepath': row['source_filepath'],
                    'duration_seconds': row['duration_seconds'],
                    'creation_time': row['creation_time']
                })
            return videos
        except sqlite3.Error as e:
            print(f"動画情報取得エラー: {e}")
            return []
            
    def get_scenes(self, video_id):
        """
        特定の動画のシーン情報を取得
        
        Args:
            video_id (str): 動画ID
            
        Returns:
            list: シーン情報の辞書のリスト
        """
        if not self.conn:
            return []
            
        try:
            self.cursor.execute("""
            SELECT scene_id, time_in, time_out, transcript, description, 
                   keyframe_path, preview_path, duration
            FROM scenes
            WHERE video_id = ?
            ORDER BY scene_id
            """, (video_id,))
            
            scenes = []
            for row in self.cursor.fetchall():
                scenes.append({
                    'scene_id': row['scene_id'],
                    'time_in': row['time_in'],
                    'time_out': row['time_out'],
                    'transcript': row['transcript'],
                    'description': row['description'],
                    'keyframe_path': row['keyframe_path'],
                    'preview_path': row['preview_path'],
                    'duration': row['duration']
                })
            return scenes
        except sqlite3.Error as e:
            print(f"シーン情報取得エラー: {e}")
            return []

class ThumbnailItem(QWidget):
    """サムネイル表示アイテム"""
    
    # ダブルクリック時のシグナル
    doubleClicked = pyqtSignal(dict)
    
    def __init__(self, scene_data, base_dir, parent=None):
        """
        初期化関数
        
        Args:
            scene_data (dict): シーン情報
            base_dir (str): 画像ファイルの基本ディレクトリ
            parent: 親ウィジェット
        """
        super().__init__(parent)
        self.scene_data = scene_data
        self.base_dir = base_dir
        
        # レイアウト設定
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # サムネイル画像
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(160, 90)  # 16:9 アスペクト比
        
        # シーン情報ラベル
        self.info_label = QLabel(f"シーン #{scene_data['scene_id']}")
        self.info_label.setAlignment(Qt.AlignCenter)
        
        # 時間情報ラベル
        time_in = self.format_time(scene_data['time_in'])
        time_out = self.format_time(scene_data['time_out'])
        self.time_label = QLabel(f"{time_in} - {time_out}")
        self.time_label.setAlignment(Qt.AlignCenter)
        
        # レイアウトに追加
        layout.addWidget(self.image_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.time_label)
        
        # サムネイル画像を読み込み
        self.load_thumbnail()
        
    def load_thumbnail(self):
        """サムネイル画像を読み込む"""
        keyframe_path = self.scene_data['keyframe_path']
        if keyframe_path:
            # Windowsスタイルのパスをシステムに合わせて変換
            keyframe_path = keyframe_path.replace('\\', os.path.sep)
            full_path = os.path.join(self.base_dir, keyframe_path)
            
            if os.path.exists(full_path):
                pixmap = QPixmap(full_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(160, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_label.setPixmap(pixmap)
                    return
                    
        # 画像が読み込めない場合はプレースホルダーを表示
        self.image_label.setText("画像なし")
        
    def format_time(self, seconds):
        """秒数を時間形式に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
    def mouseDoubleClickEvent(self, event):
        """ダブルクリックイベントハンドラ"""
        self.doubleClicked.emit(self.scene_data)
        super().mouseDoubleClickEvent(event)

class ThumbnailGrid(QScrollArea):
    """サムネイルグリッド表示コンポーネント"""
    
    # シーン選択時のシグナル
    sceneSelected = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        """
        初期化関数
        
        Args:
            parent: 親ウィジェット
        """
        super().__init__(parent)
        
        # スクロールエリアの設定
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # コンテンツウィジェット
        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        
        # グリッドレイアウト
        self.grid_layout = QGridLayout(self.content_widget)
        self.grid_layout.setSpacing(10)
        
        # サムネイルアイテムのリスト
        self.thumbnail_items = []
        
    def clear(self):
        """グリッドをクリア"""
        # 既存のアイテムを削除
        for item in self.thumbnail_items:
            self.grid_layout.removeWidget(item)
            item.deleteLater()
        self.thumbnail_items = []
        
    def load_scenes(self, scenes, base_dir):
        """
        シーン情報からサムネイルを読み込む
        
        Args:
            scenes (list): シーン情報の辞書のリスト
            base_dir (str): 画像ファイルの基本ディレクトリ
        """
        # 既存のアイテムをクリア
        self.clear()
        
        # グリッドの列数
        columns = 3
        
        # サムネイルアイテムを作成してグリッドに配置
        for i, scene in enumerate(scenes):
            row = i // columns
            col = i % columns
            
            thumbnail = ThumbnailItem(scene, base_dir)
            thumbnail.doubleClicked.connect(self.on_thumbnail_double_clicked)
            
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnail_items.append(thumbnail)
            
    def on_thumbnail_double_clicked(self, scene_data):
        """
        サムネイルダブルクリック時のハンドラ
        
        Args:
            scene_data (dict): クリックされたシーンの情報
        """
        self.sceneSelected.emit(scene_data)

# サムネイルビューアコンポーネントのテスト用コード
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # テスト用のウィンドウ
    window = QMainWindow()
    window.setWindowTitle("サムネイルビューアテスト")
    window.setGeometry(100, 100, 800, 600)
    
    # サムネイルグリッドを作成
    thumbnail_grid = ThumbnailGrid()
    
    # テスト用のシーンデータ
    test_scenes = [
        {
            'scene_id': 1,
            'time_in': 0.0,
            'time_out': 10.0,
            'transcript': 'テストトランスクリプト1',
            'description': 'テスト説明1',
            'keyframe_path': 'test/path/to/keyframe1.jpg',
            'preview_path': 'test/path/to/preview1.mp4',
            'duration': 10.0
        },
        {
            'scene_id': 2,
            'time_in': 10.0,
            'time_out': 20.0,
            'transcript': 'テストトランスクリプト2',
            'description': 'テスト説明2',
            'keyframe_path': 'test/path/to/keyframe2.jpg',
            'preview_path': 'test/path/to/preview2.mp4',
            'duration': 10.0
        },
        # 必要に応じてテストデータを追加
    ]
    
    # テスト用のベースディレクトリ
    base_dir = "."
    
    # シーンデータを読み込む
    thumbnail_grid.load_scenes(test_scenes, base_dir)
    
    # ウィンドウにサムネイルグリッドを設定
    window.setCentralWidget(thumbnail_grid)
    
    # シグナルのテスト用ハンドラ
    def on_scene_selected(scene_data):
        print(f"シーン選択: {scene_data['scene_id']}")
        print(f"説明: {scene_data['description']}")
    
    # シグナルを接続
    thumbnail_grid.sceneSelected.connect(on_scene_selected)
    
    # ウィンドウを表示
    window.show()
    
    sys.exit(app.exec_())
