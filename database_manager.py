#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
from PyQt5.QtCore import Qt

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
        """
        データベースに接続
        
        Returns:
            bool: 接続成功の場合はTrue
        """
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
            SELECT video_id, source_filepath, duration_seconds, creation_time, 
                   timecode_offset, completed, last_update
            FROM videos
            ORDER BY video_id
            """)
            
            videos = []
            for row in self.cursor.fetchall():
                videos.append({
                    'video_id': row['video_id'],
                    'source_filepath': row['source_filepath'],
                    'duration_seconds': row['duration_seconds'],
                    'creation_time': row['creation_time'],
                    'timecode_offset': row['timecode_offset'],
                    'completed': bool(row['completed']),
                    'last_update': row['last_update']
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
    
    def get_scene(self, video_id, scene_id):
        """
        特定のシーン情報を取得
        
        Args:
            video_id (str): 動画ID
            scene_id (int): シーンID
            
        Returns:
            dict: シーン情報の辞書、見つからない場合はNone
        """
        if not self.conn:
            return None
            
        try:
            self.cursor.execute("""
            SELECT scene_id, time_in, time_out, transcript, description, 
                   keyframe_path, preview_path, duration
            FROM scenes
            WHERE video_id = ? AND scene_id = ?
            """, (video_id, scene_id))
            
            row = self.cursor.fetchone()
            if row:
                return {
                    'scene_id': row['scene_id'],
                    'time_in': row['time_in'],
                    'time_out': row['time_out'],
                    'transcript': row['transcript'],
                    'description': row['description'],
                    'keyframe_path': row['keyframe_path'],
                    'preview_path': row['preview_path'],
                    'duration': row['duration']
                }
            return None
        except sqlite3.Error as e:
            print(f"シーン情報取得エラー: {e}")
            return None
    
    def get_keyframe_path(self, video_id, scene_id):
        """
        特定のシーンのキーフレームパスを取得
        
        Args:
            video_id (str): 動画ID
            scene_id (int): シーンID
            
        Returns:
            str: キーフレームパス、見つからない場合は空文字列
        """
        if not self.conn:
            return ""
            
        try:
            self.cursor.execute("""
            SELECT keyframe_path
            FROM scenes
            WHERE video_id = ? AND scene_id = ?
            """, (video_id, scene_id))
            
            row = self.cursor.fetchone()
            if row:
                return row['keyframe_path']
            return ""
        except sqlite3.Error as e:
            print(f"キーフレームパス取得エラー: {e}")
            return ""
    
    def get_preview_path(self, video_id, scene_id):
        """
        特定のシーンのプレビューパスを取得
        
        Args:
            video_id (str): 動画ID
            scene_id (int): シーンID
            
        Returns:
            str: プレビューパス、見つからない場合は空文字列
        """
        if not self.conn:
            return ""
            
        try:
            self.cursor.execute("""
            SELECT preview_path
            FROM scenes
            WHERE video_id = ? AND scene_id = ?
            """, (video_id, scene_id))
            
            row = self.cursor.fetchone()
            if row:
                return row['preview_path']
            return ""
        except sqlite3.Error as e:
            print(f"プレビューパス取得エラー: {e}")
            return ""
    
    def search_scenes(self, query):
        """
        シーンを検索
        
        Args:
            query (str): 検索テキスト
            
        Returns:
            list: 検索結果のシーン情報の辞書のリスト
        """
        if not self.conn or not query:
            return []
            
        try:
            # トランスクリプトと説明で検索
            self.cursor.execute("""
            SELECT s.video_id, s.scene_id, s.time_in, s.time_out, s.transcript, 
                   s.description, s.keyframe_path, s.preview_path, s.duration
            FROM scenes s
            WHERE s.transcript LIKE ? OR s.description LIKE ?
            ORDER BY s.video_id, s.scene_id
            """, (f"%{query}%", f"%{query}%"))
            
            scenes = []
            for row in self.cursor.fetchall():
                scenes.append({
                    'video_id': row['video_id'],
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
            print(f"シーン検索エラー: {e}")
            return []
    
    def get_database_info(self):
        """
        データベース情報を取得
        
        Returns:
            dict: データベース情報の辞書
        """
        if not self.conn:
            return {}
            
        try:
            # 動画数を取得
            self.cursor.execute("SELECT COUNT(*) as video_count FROM videos")
            video_count = self.cursor.fetchone()['video_count']
            
            # シーン数を取得
            self.cursor.execute("SELECT COUNT(*) as scene_count FROM scenes")
            scene_count = self.cursor.fetchone()['scene_count']
            
            # 合計時間を取得
            self.cursor.execute("SELECT SUM(duration_seconds) as total_duration FROM videos")
            total_duration = self.cursor.fetchone()['total_duration'] or 0
            
            return {
                'video_count': video_count,
                'scene_count': scene_count,
                'total_duration': total_duration,
                'db_path': self.db_path
            }
        except sqlite3.Error as e:
            print(f"データベース情報取得エラー: {e}")
            return {}

    def get_all_scenes(self):
        """すべてのシーン情報をリストで取得する"""
        if not self.conn:
            return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT scene_id, video_id, time_in, time_out, keyframe_path, description, transcript
                FROM scenes
            """)
            rows = cursor.fetchall()
            # Convert rows to list of dictionaries
            scenes = [
                {
                    'scene_id': row[0],
                    'video_id': row[1],
                    'time_in': row[2],
                    'time_out': row[3],
                    'keyframe_path': row[4],
                    'description': row[5],
                    'transcript': row[6],
                    'duration': row[3] - row[2]
                }
                for row in rows
            ]
            return scenes
        except sqlite3.Error as e:
            print(f"データベースエラー (get_all_scenes): {e}")
            return []

    def delete_scene(self, video_id, scene_id):
        """指定されたシーンをデータベースから削除する"""
        if not self.conn:
            return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM scenes WHERE video_id = ? AND scene_id = ?", (video_id, scene_id))
            self.conn.commit() # 変更を確定
            # Check if any row was affected
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"データベースエラー (delete_scene {video_id}-{scene_id}): {e}")
            self.conn.rollback() # エラー時はロールバック
            return False

    def update_scene_text(self, video_id, scene_id, description, transcript):
        """指定されたシーンの説明と文字起こしを更新する"""
        if not self.conn:
            return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE scenes
                SET description = ?, transcript = ?
                WHERE video_id = ? AND scene_id = ?
            """, (description, transcript, video_id, scene_id))
            self.conn.commit()
            return cursor.rowcount > 0 # 1行更新されたらTrue
        except sqlite3.Error as e:
            print(f"データベースエラー (update_scene_text {video_id}-{scene_id}): {e}")
            self.conn.rollback()
            return False

# テスト用コード
if __name__ == "__main__":
    # テスト用のデータベースパス
    db_path = "video_data.db"
    
    # データベースマネージャーを初期化
    db_manager = DatabaseManager(db_path)
    
    # データベースに接続
    if db_manager.connect():
        print(f"データベース接続成功: {db_path}")
        
        # データベース情報を取得
        db_info = db_manager.get_database_info()
        print(f"データベース情報:")
        print(f"  動画数: {db_info.get('video_count', 0)}")
        print(f"  シーン数: {db_info.get('scene_count', 0)}")
        print(f"  合計時間: {db_info.get('total_duration', 0):.1f}秒")
        
        # 動画リストを取得
        videos = db_manager.get_videos()
        print(f"動画数: {len(videos)}")
        
        # 最初の動画のシーンを取得
        if videos:
            first_video = videos[0]
            video_id = first_video['video_id']
            
            scenes = db_manager.get_scenes(video_id)
            print(f"動画 {video_id} のシーン数: {len(scenes)}")
            
            # 最初のシーンの情報を表示
            if scenes:
                first_scene = scenes[0]
                print(f"シーン {first_scene['scene_id']} の情報:")
                print(f"  時間: {first_scene['time_in']} - {first_scene['time_out']} ({first_scene['duration']}秒)")
                print(f"  説明: {first_scene['description'][:50]}...")
                print(f"  キーフレームパス: {first_scene['keyframe_path']}")
        
        # データベース接続を閉じる
        db_manager.close()
    else:
        print(f"データベース接続失敗: {db_path}")
