#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import glob
from pathlib import Path
from datetime import datetime

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
        # 既存のテーブルを削除
        self.cursor.execute("DROP TABLE IF EXISTS transcriptions")
        self.cursor.execute("DROP TABLE IF EXISTS scenes")
        self.cursor.execute("DROP TABLE IF EXISTS audio_files")
        self.cursor.execute("DROP TABLE IF EXISTS videos")
        
        # Videosテーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE,
            filepath TEXT,
            file_index INTEGER,
            duration_seconds REAL,
            creation_time TEXT,
            timecode_offset TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # audio_filesテーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS audio_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            filename TEXT,
            filepath TEXT,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
        ''')
        
        # scenesテーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            scene_id INTEGER,
            start_timecode TEXT,
            end_timecode TEXT,
            description TEXT,
            thumbnail_path TEXT,
            scene_good_reason TEXT,
            scene_bad_reason TEXT,
            scene_evaluation_tag TEXT,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
        ''')
        
        # transcriptionsテーブル
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS transcriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            start_timecode TEXT,
            end_timecode TEXT,
            transcription TEXT,
            scene_id INTEGER,
            transcription_good_reason TEXT,
            transcription_bad_reason TEXT,
            source_timecode_offset TEXT,
            source_filename TEXT,
            file_index INTEGER,
            FOREIGN KEY (video_id) REFERENCES videos (id),
            FOREIGN KEY (scene_id) REFERENCES scenes (id)
        )
        ''')
        
        self.conn.commit()

    def parse_timecode(self, timecode):
        """タイムコードを秒数に変換"""
        if not timecode:
            return 0
        parts = timecode.split(':')
        if len(parts) != 4:
            return 0
        hours, minutes, seconds, frames = parts
        # 標準的なフレームレートは29.97fpsと仮定
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(frames) / 30

    def import_ts_data(self, parent_dir):
        """
        '_captures'フォルダーからTSデータをインポート
        
        Args:
            parent_dir (str): '_captures'フォルダーを含む親ディレクトリ
            
        Returns:
            tuple: (インポートした動画の数, エラーメッセージのリスト)
        """
        count = 0
        errors = []
        # 起点となるディレクトリの絶対パスを取得
        parent_dir_abs = os.path.abspath(parent_dir)
        
        try:
            # '_captures'フォルダーを検索
            captures_pattern = os.path.join(parent_dir_abs, "**", "*_captures")
            captures_dirs = glob.glob(captures_pattern, recursive=True)
            
            if not captures_dirs:
                errors.append(f"指定されたディレクトリ '{parent_dir}' 内に '_captures' フォルダが見つかりません。")
                return count, errors
            
            for captures_dir in captures_dirs:
                try:
                    # 動画IDを抽出（xxx_capturesからxxxを取得）
                    base_name = os.path.basename(captures_dir).replace("_captures", "")
                    captures_dir_rel = os.path.relpath(captures_dir, parent_dir_abs)
                    
                    # データJSONファイルのパス
                    json_path = os.path.join(captures_dir, f"{base_name}_data.json")
                    
                    if not os.path.exists(json_path):
                        errors.append(f"Data file not found for {base_name} in {captures_dir_rel}")
                        continue
                    
                    # JSONデータを読み込み (パス情報は無視する)
                    with open(json_path, 'r', encoding='utf-8') as f:
                        source_data = json.load(f)
                    
                    # --- ファイルパスはJSON内の値ではなく、ディレクトリ構造から決定 --- 
                    video_filename = f"{base_name}.MP4"
                    # 動画ファイルは_capturesフォルダの親にあると仮定
                    video_dir_abs = os.path.dirname(captures_dir)
                    video_filepath_abs = os.path.join(video_dir_abs, video_filename)
                    video_filepath_rel = os.path.relpath(video_filepath_abs, parent_dir_abs)

                    wav_filename = f"{base_name}.wav"
                    wav_filepath_abs = os.path.join(video_dir_abs, wav_filename)
                    wav_filepath_rel = os.path.relpath(wav_filepath_abs, parent_dir_abs)
                    # --------------------------------------------------------------
                    
                    # メタデータを取得 (パス情報以外)
                    metadata = source_data.get("metadata", {})
                    file_index = source_data.get("file_index", 0) # ファイルインデックスはJSONから取得
                    
                    # 動画ファイルの存在確認
                    if not os.path.exists(video_filepath_abs):
                        errors.append(f"Video file not found at expected location: {video_filepath_rel}")
                        # 動画ファイルが見つからない場合はスキップするか、エラー処理を継続するか選択
                        continue

                    # --- Original INSERT with Debugging and Cleaning ---
                    try:
                        print(f"\n--- Preparing original video data for: {captures_dir_rel} ---")

                        # Get raw values
                        raw_filename = video_filename
                        raw_filepath = video_filepath_rel
                        raw_file_index = file_index
                        raw_duration = metadata.get("duration_seconds", 0.0)
                        raw_creation_time = metadata.get("creation_time_utc", "")
                        raw_timecode_offset = metadata.get("timecode_offset", "")

                        # --- Debug: Print representation of string values ---
                        print(f"Repr filename: {repr(raw_filename)}")
                        print(f"Repr filepath: {repr(raw_filepath)}")
                        print(f"Repr creation_time: {repr(raw_creation_time)}")
                        print(f"Repr timecode_offset: {repr(raw_timecode_offset)}")
                        # --- End Debug ---

                        # --- Clean string values (remove leading/trailing whitespace) ---
                        clean_filename = raw_filename.strip() if isinstance(raw_filename, str) else raw_filename
                        clean_filepath = raw_filepath.strip() if isinstance(raw_filepath, str) else raw_filepath
                        clean_creation_time = raw_creation_time.strip() if isinstance(raw_creation_time, str) else raw_creation_time
                        clean_timecode_offset = raw_timecode_offset.strip() if isinstance(raw_timecode_offset, str) else raw_timecode_offset
                        # --- End Cleaning ---

                        params_videos = (
                            clean_filename,
                            clean_filepath,
                            raw_file_index, # Integer, no stripping needed
                            raw_duration,   # Float, no stripping needed
                            clean_creation_time,
                            clean_timecode_offset
                        )
                        print(f"Cleaned Params: {params_videos}")

                        # Re-enable the original INSERT statement
                        sql_videos = '''
                        INSERT OR IGNORE INTO videos (
                            filename,
                            filepath,
                            file_index,
                            duration_seconds,
                            creation_time,
                            timecode_offset
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        '''
                        print(f"--- Attempting original INSERT with cleaned params ---")
                        self.cursor.execute(sql_videos, params_videos)
                        # self.conn.commit() # Commit later after all inserts for this video

                        print("--- Original INSERT successful (tentative). ---")

                        # Get the ID (important for subsequent inserts)
                        # Use the cleaned filename/filepath for lookup
                        params_select_id = (clean_filename, clean_filepath)
                        self.cursor.execute("SELECT id FROM videos WHERE filename = ? AND filepath = ?",
                                          params_select_id)
                        video_id_result = self.cursor.fetchone()
                        if not video_id_result:
                             # This might happen if the record already existed due to UNIQUE constraint
                             # Try selecting again without filepath just in case
                             self.cursor.execute("SELECT id FROM videos WHERE filename = ?", (clean_filename,))
                             video_id_result = self.cursor.fetchone()
                             if not video_id_result:
                                 errors.append(f"Could not retrieve video_id for {clean_filename} ({clean_filepath}) after insert/ignore.")
                                 self.conn.rollback() # Rollback if ID is crucial and not found
                                 continue # Skip to next directory
                             else:
                                 print(f"--- Retrieved existing video_id: {video_id_result[0]} ---")
                        video_id = video_id_result[0]
                        print(f"--- Successfully retrieved video_id: {video_id} ---")


                    except sqlite3.Error as insert_err:
                        print(f"--- ORIGINAL INSERT FAILED: {insert_err} ---")
                        errors.append(f"Original INSERT videos failed ({captures_dir_rel}): {insert_err}")
                        try:
                            self.conn.rollback() # Rollback the failed insert
                        except sqlite3.Error as rb_err:
                             errors.append(f"Rollback failed after INSERT videos error ({captures_dir_rel}): {str(rb_err)}")
                        continue # Skip to the next directory if video insert fails
                    # --- End Original INSERT block ---


                    # --- Remove the temporary skip block ---
                    # print("--- Skipping remaining inserts for this directory (DEBUG) ---")
                    # count += 1 # Increment count even for the test
                    # break # Exit the loop after processing the first directory
                    # --- End Temporary Skip ---


                    # --- Re-enable the rest of the inserts ---
                    # 音声ファイルの情報を挿入（存在する場合）
                    if os.path.exists(wav_filepath_abs):
                        try:
                            self.cursor.execute('''
                            INSERT OR IGNORE INTO audio_files (
                                video_id,
                                filename,
                                filepath
                            ) VALUES (?, ?, ?)
                            ''', (video_id, wav_filename, wav_filepath_rel)) # Use relative path
                        except sqlite3.Error as audio_err:
                             errors.append(f"INSERT audio_files failed ({captures_dir_rel}): {audio_err}")
                             # Decide if you want to rollback everything or just log this error

                    # シーンデータを挿入
                    if 'detected_scenes' in source_data:
                        for scene in source_data['detected_scenes']:
                            try:
                                # サムネイルパスを相対パスで保存
                                scene_id_num = scene.get('scene_id', 0)
                                thumbnail_filename = f"scene_{scene_id_num:04d}.jpg"
                                thumbnail_path_abs = os.path.join(captures_dir, thumbnail_filename)
                                thumbnail_path_rel = os.path.relpath(thumbnail_path_abs, parent_dir_abs)

                                self.cursor.execute('''
                                INSERT OR IGNORE INTO scenes (
                                    video_id,
                                    scene_id,
                                    start_timecode,
                                    end_timecode,
                                    description,
                                    thumbnail_path,
                                    scene_good_reason,
                                    scene_bad_reason,
                                    scene_evaluation_tag
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    video_id,
                                    scene_id_num,
                                    scene.get("start_timecode", ""),
                                    scene.get("end_timecode", ""),
                                    scene.get("description", ""),
                                    thumbnail_path_rel, # Store relative path
                                    scene.get("scene_good_reason"),
                                    scene.get("scene_bad_reason"),
                                    scene.get("scene_evaluation_tag", "")
                                ))
                            except sqlite3.Error as scene_err:
                                errors.append(f"INSERT scenes failed (scene {scene.get('scene_id', '?')}, {captures_dir_rel}): {scene_err}")

                    # 文字起こしデータを挿入
                    if 'final_segments' in source_data:
                        for segment in source_data['final_segments']:
                            try:
                                scene_id_for_transcription = segment.get("scene_id")
                                scene_pk = None # Primary key of the scene

                                if scene_id_for_transcription is not None:
                                    self.cursor.execute("SELECT id FROM scenes WHERE video_id = ? AND scene_id = ?", (video_id, scene_id_for_transcription))
                                    scene_pk_result = self.cursor.fetchone()
                                    if scene_pk_result:
                                        scene_pk = scene_pk_result[0]
                                    else:
                                        # エラーとはせず警告に留める
                                        print(f"警告: 文字起こしに対応するシーンID {scene_id_for_transcription} が見つかりません (動画: {video_filepath_rel})")

                                self.cursor.execute('''
                                INSERT OR IGNORE INTO transcriptions (
                                    video_id,
                                    start_timecode,
                                    end_timecode,
                                    transcription,
                                    scene_id,
                                    transcription_good_reason,
                                    transcription_bad_reason,
                                    source_timecode_offset,
                                    source_filename,
                                    file_index
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    video_id,
                                    segment.get("start_timecode", ""),
                                    segment.get("end_timecode", ""),
                                    segment.get("transcription", ""),
                                    scene_pk,
                                    segment.get("transcription_good_reason"),
                                    segment.get("transcription_bad_reason"),
                                    segment.get("source_timecode_offset", ""),
                                    segment.get("source_filename", ""), # source_filenameはそのまま使う
                                    segment.get("file_index", 0)        # file_indexもそのまま使う
                                ))
                            except sqlite3.Error as trans_err:
                                errors.append(f"INSERT transcriptions failed (segment starting {segment.get('start_timecode', '?')}, {captures_dir_rel}): {trans_err}")

                    self.conn.commit() # 各 captures ディレクトリ処理後にコミット
                    count += 1
                    # --- End re-enabled block ---

                except sqlite3.Error as db_err:
                    errors.append(f"データベースエラー ({captures_dir_rel}): {str(db_err)}")
                    try:
                        self.conn.rollback() # エラー発生時にロールバック
                    except sqlite3.Error as rb_err:
                         errors.append(f"ロールバック失敗 ({captures_dir_rel}): {str(rb_err)}")
                except Exception as e:
                    errors.append(f"処理エラー ({captures_dir_rel}): {str(e)}")
                    import traceback
                    traceback.print_exc() # 詳細なエラー情報をコンソールに出力
                    try:
                        self.conn.rollback() # エラー発生時にロールバック
                    except sqlite3.Error as rb_err:
                         errors.append(f"ロールバック失敗 ({captures_dir_rel}): {str(rb_err)}")

            return count, errors

        except Exception as e:
            errors.append(f"全体処理エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return count, errors

def main():
    """
    テスト用のメイン関数
    """
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='動画データベースを作成し、TSデータをインポートします')
    parser.add_argument('--db', default='test.db', help='データベースファイルのパス')
    parser.add_argument('--dir', required=True, help='TSデータを含むディレクトリのパス')
    parser.add_argument('--test', action='store_true', help='テストモードで実行')
    parser.add_argument('--init', action='store_true', help='データベースを初期化してからインポート')
    
    args = parser.parse_args()
    
    # データベース接続
    db = VideoDatabase(args.db)
    db.connect()
    
    try:
        if args.init:
            print("データベースを初期化します...")
            db.create_schema()
            print("初期化完了")
        
        # TSデータのインポート
        count, errors = db.import_ts_data(args.dir)
        
        # 結果の表示
        print(f"インポート完了: {count}件の動画を処理")
        if errors:
            print("\nエラー一覧:")
            for error in errors:
                print(f"- {error}")
        
        # テストモードの場合、データの検証を行う
        if args.test:
            print("\n=== テスト結果 ===")
            
            # テストデータの検証
            test_video = "GH012564.MP4"
            print(f"\n動画ファイル: {test_video}")
            
            # 動画IDを取得
            db.cursor.execute("SELECT id FROM videos WHERE filename = ?", (test_video,))
            video_id_result = db.cursor.fetchone()
            if not video_id_result:
                print("エラー: テスト動画が見つかりません")
                sys.exit(1)
            video_id = video_id_result[0]
            
            # シーンデータの検証
            print("\nシーンデータの検証:")
            db.cursor.execute('''
            SELECT scene_id, scene_good_reason, scene_bad_reason, scene_evaluation_tag 
            FROM scenes 
            WHERE video_id = ?
            ORDER BY scene_id
            ''', (video_id,))
            
            scenes = db.cursor.fetchall()
            if not scenes:
                print("エラー: シーンデータが見つかりません")
            else:
                for scene in scenes:
                    print(f"\nシーンID: {scene[0]}")
                    print(f"- 良い理由: {scene[1]}")
                    print(f"- 悪い理由: {scene[2]}")
                    print(f"- 評価タグ: {scene[3]}")
            
            # 文字起こしデータの検証
            print("\n文字起こしデータの検証:")
            db.cursor.execute('''
            SELECT start_timecode, end_timecode, transcription, 
                   transcription_good_reason, transcription_bad_reason 
            FROM transcriptions 
            WHERE video_id = ?
            ORDER BY start_timecode
            ''', (video_id,))
            
            transcriptions = db.cursor.fetchall()
            if not transcriptions:
                print("エラー: 文字起こしデータが見つかりません")
            else:
                for trans in transcriptions:
                    print(f"\n時間: {trans[0]} - {trans[1]}")
                    print(f"文字起こし: {trans[2]}")
                    print(f"- 良い理由: {trans[3]}")
                    print(f"- 悪い理由: {trans[4]}")
    
    finally:
        db.close()

if __name__ == "__main__":
    main()
