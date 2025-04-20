#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import unittest
import tempfile
import shutil
import sqlite3
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

# テスト対象のモジュールをインポート
from database_manager import DatabaseManager
from thumbnail_viewer import ThumbnailGrid, ThumbnailItem
from video_player import VideoPlayer
from video_preview_app import VideoPreviewApp, SceneInfoPanel

class TestDatabaseManager(unittest.TestCase):
    """DatabaseManagerクラスのテスト"""
    
    def setUp(self):
        """テスト前の準備"""
        # テスト用の一時データベースを作成
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        # テスト用のデータベースを初期化
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # テスト用のテーブルを作成
        self.cursor.execute('''
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            source_filepath TEXT,
            duration_seconds REAL,
            creation_time TEXT,
            timecode_offset TEXT,
            completed BOOLEAN,
            last_update TEXT
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            scene_id INTEGER,
            time_in REAL,
            time_out REAL,
            transcript TEXT,
            description TEXT,
            keyframe_path TEXT,
            preview_path TEXT,
            duration REAL,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        )
        ''')
        
        # テスト用のデータを挿入
        self.cursor.execute('''
        INSERT INTO videos (
            video_id, source_filepath, duration_seconds, creation_time, 
            timecode_offset, completed, last_update
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("TEST001", "test/path/video.mp4", 60.0, "2025-04-19", "00:00:00", 1, "2025-04-19"))
        
        self.cursor.execute('''
        INSERT INTO scenes (
            video_id, scene_id, time_in, time_out, transcript, description,
            keyframe_path, preview_path, duration
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("TEST001", 1, 0.0, 10.0, "テストトランスクリプト", "テスト説明",
              "test/path/keyframe.jpg", "test/path/preview.mp4", 10.0))
        
        self.conn.commit()
        
        # テスト対象のインスタンスを作成
        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.connect()
        
    def tearDown(self):
        """テスト後のクリーンアップ"""
        # データベース接続を閉じる
        if self.db_manager:
            self.db_manager.close()
        
        if self.conn:
            self.conn.close()
        
        # 一時ディレクトリを削除
        shutil.rmtree(self.temp_dir)
        
    def test_get_videos(self):
        """get_videos()メソッドのテスト"""
        videos = self.db_manager.get_videos()
        
        # 結果の検証
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]['video_id'], "TEST001")
        self.assertEqual(videos[0]['source_filepath'], "test/path/video.mp4")
        self.assertEqual(videos[0]['duration_seconds'], 60.0)
        
    def test_get_scenes(self):
        """get_scenes()メソッドのテスト"""
        scenes = self.db_manager.get_scenes("TEST001")
        
        # 結果の検証
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]['scene_id'], 1)
        self.assertEqual(scenes[0]['time_in'], 0.0)
        self.assertEqual(scenes[0]['time_out'], 10.0)
        self.assertEqual(scenes[0]['transcript'], "テストトランスクリプト")
        self.assertEqual(scenes[0]['description'], "テスト説明")
        
    def test_get_scene(self):
        """get_scene()メソッドのテスト"""
        scene = self.db_manager.get_scene("TEST001", 1)
        
        # 結果の検証
        self.assertIsNotNone(scene)
        self.assertEqual(scene['scene_id'], 1)
        self.assertEqual(scene['time_in'], 0.0)
        self.assertEqual(scene['time_out'], 10.0)
        
    def test_get_keyframe_path(self):
        """get_keyframe_path()メソッドのテスト"""
        path = self.db_manager.get_keyframe_path("TEST001", 1)
        
        # 結果の検証
        self.assertEqual(path, "test/path/keyframe.jpg")
        
    def test_get_preview_path(self):
        """get_preview_path()メソッドのテスト"""
        path = self.db_manager.get_preview_path("TEST001", 1)
        
        # 結果の検証
        self.assertEqual(path, "test/path/preview.mp4")
        
    def test_search_scenes(self):
        """search_scenes()メソッドのテスト"""
        scenes = self.db_manager.search_scenes("テスト")
        
        # 結果の検証
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]['scene_id'], 1)
        self.assertEqual(scenes[0]['description'], "テスト説明")
        
    def test_get_database_info(self):
        """get_database_info()メソッドのテスト"""
        info = self.db_manager.get_database_info()
        
        # 結果の検証
        self.assertEqual(info['video_count'], 1)
        self.assertEqual(info['scene_count'], 1)
        self.assertEqual(info['total_duration'], 60.0)

class TestThumbnailViewer(unittest.TestCase):
    """ThumbnailGridクラスのテスト"""
    
    def setUp(self):
        """テスト前の準備"""
        # QApplicationインスタンスを作成
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)
            
        # テスト用のシーンデータ
        self.test_scenes = [
            {
                'scene_id': 1,
                'time_in': 0.0,
                'time_out': 10.0,
                'transcript': 'テストトランスクリプト1',
                'description': 'テスト説明1',
                'keyframe_path': 'test/path/keyframe1.jpg',
                'preview_path': 'test/path/preview1.mp4',
                'duration': 10.0
            },
            {
                'scene_id': 2,
                'time_in': 10.0,
                'time_out': 20.0,
                'transcript': 'テストトランスクリプト2',
                'description': 'テスト説明2',
                'keyframe_path': 'test/path/keyframe2.jpg',
                'preview_path': 'test/path/preview2.mp4',
                'duration': 10.0
            }
        ]
        
        # テスト対象のインスタンスを作成
        self.thumbnail_grid = ThumbnailGrid()
        
    def test_load_scenes(self):
        """load_scenes()メソッドのテスト"""
        # シーンデータを読み込む
        self.thumbnail_grid.load_scenes(self.test_scenes, ".")
        
        # 結果の検証
        self.assertEqual(len(self.thumbnail_grid.thumbnail_items), 2)

class TestVideoPlayer(unittest.TestCase):
    """VideoPlayerクラスのテスト"""
    
    def setUp(self):
        """テスト前の準備"""
        # QApplicationインスタンスを作成
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)
            
        # テスト対象のインスタンスを作成
        self.video_player = VideoPlayer()
        
    def test_format_time(self):
        """format_time()メソッドのテスト"""
        # 時間のフォーマットをテスト
        self.assertEqual(self.video_player.format_time(0), "00:00:00")
        self.assertEqual(self.video_player.format_time(3661000), "01:01:01")
        self.assertEqual(self.video_player.format_time(7200000), "02:00:00")

class TestSceneInfoPanel(unittest.TestCase):
    """SceneInfoPanelクラスのテスト"""
    
    def setUp(self):
        """テスト前の準備"""
        # QApplicationインスタンスを作成
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)
            
        # テスト対象のインスタンスを作成
        self.scene_info_panel = SceneInfoPanel()
        
        # テスト用のシーンデータ
        self.test_scene = {
            'scene_id': 1,
            'time_in': 0.0,
            'time_out': 10.0,
            'transcript': 'テストトランスクリプト',
            'description': 'テスト説明',
            'keyframe_path': 'test/path/keyframe.jpg',
            'preview_path': 'test/path/preview.mp4',
            'duration': 10.0
        }
        
    def test_update_info(self):
        """update_info()メソッドのテスト"""
        # シーン情報を更新
        self.scene_info_panel.update_info(self.test_scene)
        
        # 結果の検証
        self.assertEqual(self.scene_info_panel.description_text.toPlainText(), "テスト説明")
        self.assertEqual(self.scene_info_panel.transcript_text.toPlainText(), "テストトランスクリプト")
        self.assertEqual(self.scene_info_panel.time_info_label.text(), "時間: 00:00:00 - 00:00:10 (10.0秒)")
        
    def test_clear(self):
        """clear()メソッドのテスト"""
        # 一度情報を設定
        self.scene_info_panel.update_info(self.test_scene)
        
        # クリア
        self.scene_info_panel.clear()
        
        # 結果の検証
        self.assertEqual(self.scene_info_panel.description_text.toPlainText(), "")
        self.assertEqual(self.scene_info_panel.transcript_text.toPlainText(), "")
        self.assertEqual(self.scene_info_panel.time_info_label.text(), "時間: --:--:-- - --:--:-- (--秒)")
        
    def test_format_time(self):
        """format_time()メソッドのテスト"""
        # 時間のフォーマットをテスト
        self.assertEqual(self.scene_info_panel.format_time(0), "00:00:00")
        self.assertEqual(self.scene_info_panel.format_time(3661), "01:01:01")
        self.assertEqual(self.scene_info_panel.format_time(7200), "02:00:00")

class TestVideoPreviewApp(unittest.TestCase):
    """VideoPreviewAppクラスのテスト"""
    
    def setUp(self):
        """テスト前の準備"""
        # QApplicationインスタンスを作成
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)
            
        # テスト対象のインスタンスを作成
        self.video_preview_app = VideoPreviewApp()
        
    def test_ui_components(self):
        """UIコンポーネントの存在確認テスト"""
        # 主要なUIコンポーネントが存在するか確認
        self.assertIsNotNone(self.video_preview_app.video_combo)
        self.assertIsNotNone(self.video_preview_app.search_box)
        self.assertIsNotNone(self.video_preview_app.search_button)
        self.assertIsNotNone(self.video_preview_app.db_button)
        self.assertIsNotNone(self.video_preview_app.thumbnail_grid)
        self.assertIsNotNone(self.video_preview_app.video_player)
        self.assertIsNotNone(self.video_preview_app.scene_info_panel)
        self.assertIsNotNone(self.video_preview_app.statusBar)

# テストを実行
if __name__ == "__main__":
    unittest.main()
