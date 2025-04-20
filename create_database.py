#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import glob
from pathlib import Path

class VideoDatabase:
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
        """
        データベースに接続
        """
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def close(self):
        """
        データベース接続を閉じる
        """
        if self.conn:
            self.conn.close()
    
    def create_schema(self):
        """
        データベーススキーマを作成
        """
        # Videosテーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            source_filepath TEXT,
            duration_seconds REAL,
            creation_time TEXT,
            timecode_offset TEXT,
            completed BOOLEAN,
            last_update TEXT
        )
        ''')
        
        # Scenesテーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS scenes (
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
        
        # インデックス
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_video_id ON scenes(video_id)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_scene_id ON scenes(scene_id)')
        
        self.conn.commit()
    
    def insert_video(self, video_id, source_data, converted_data):
        """
        動画データをデータベースに挿入
        
        Args:
            video_id (str): 動画ID
            source_data (dict): 元のJSONデータ
            converted_data (dict): 変換後のJSONデータ
        """
        # メタデータを取得
        metadata = source_data.get("metadata", {})
        
        # Videosテーブルに挿入
        self.cursor.execute('''
        INSERT OR REPLACE INTO videos (
            video_id,
            source_filepath,
            duration_seconds,
            creation_time,
            timecode_offset,
            completed,
            last_update
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            video_id,
            source_data.get("source_filepath", ""),
            metadata.get("duration_seconds", 0.0),
            metadata.get("creation_time_utc", ""),
            metadata.get("timecode_offset", ""),
            converted_data.get("completed", True),
            converted_data.get("last_update", "")
        ))
        
        # コミット
        self.conn.commit()
    
    def insert_scenes(self, video_id, scenes):
        """
        シーンデータをデータベースに挿入
        
        Args:
            video_id (str): 動画ID
            scenes (list): シーンデータのリスト
        """
        # 既存のシーンを削除
        self.cursor.execute('DELETE FROM scenes WHERE video_id = ?', (video_id,))
        
        # シーンを挿入
        for scene in scenes:
            self.cursor.execute('''
            INSERT INTO scenes (
                video_id,
                scene_id,
                time_in,
                time_out,
                transcript,
                description,
                keyframe_path,
                preview_path,
                duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                video_id,
                scene.get("scene_id", 0),
                scene.get("time_in", 0.0),
                scene.get("time_out", 0.0),
                scene.get("transcript", ""),
                scene.get("description", ""),
                scene.get("keyframe_path", ""),
                scene.get("preview_path", ""),
                scene.get("duration", 0.0)
            ))
        
        # コミット
        self.conn.commit()
    
    def import_converted_data(self, converted_dir, source_dir):
        """
        変換済みデータをデータベースにインポート
        
        Args:
            converted_dir (str): 変換済みデータのディレクトリ
            source_dir (str): 元データのディレクトリ
            
        Returns:
            int: インポートした動画の数
        """
        # 変換済みのJSONファイルを検索
        pattern = os.path.join(converted_dir, "video_nodes_*", "nodes.json")
        converted_files = glob.glob(pattern)
        
        count = 0
        
        for json_path in converted_files:
            # 動画IDを抽出（video_nodes_GH01xxxx/nodes.json → GH01xxxx）
            dir_name = os.path.basename(os.path.dirname(json_path))
            video_id = dir_name.replace("video_nodes_", "")
            
            # 変換済みデータを読み込み
            with open(json_path, 'r', encoding='utf-8') as f:
                converted_data = json.load(f)
            
            # 元データのパスを特定
            source_json_path = os.path.join(source_dir, "ts", f"{video_id}_captures", f"{video_id}_data.json")
            
            # 元データが存在する場合は読み込み
            if os.path.exists(source_json_path):
                with open(source_json_path, 'r', encoding='utf-8') as f:
                    source_data = json.load(f)
            else:
                # 元データが見つからない場合は空の辞書
                source_data = {}
            
            # データベースに挿入
            self.insert_video(video_id, source_data, converted_data)
            self.insert_scenes(video_id, converted_data.get("scenes", []))
            
            count += 1
            print(f"Imported: {video_id}")
        
        return count

def create_database():
    """
    データベースを作成して変換済みデータをインポート
    """
    # データベースファイルのパス
    db_path = "/home/ubuntu/data_analysis/video_data.db"
    
    # 変換済みデータのディレクトリ
    converted_dir = "/home/ubuntu/data_analysis/converted"
    
    # 元データのディレクトリ
    source_dir = "/home/ubuntu/data_analysis"
    
    # データベースを初期化
    db = VideoDatabase(db_path)
    db.connect()
    
    try:
        # スキーマを作成
        db.create_schema()
        
        # データをインポート
        count = db.import_converted_data(converted_dir, source_dir)
        
        print(f"Database created successfully. Imported {count} videos.")
    finally:
        # 接続を閉じる
        db.close()

if __name__ == "__main__":
    create_database()
