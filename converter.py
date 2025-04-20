#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import shutil
import glob
import datetime
from pathlib import Path

class VideoDataConverter:
    def __init__(self, source_dir, output_dir):
        """
        初期化関数
        
        Args:
            source_dir (str): 変換元データディレクトリ（ts形式）
            output_dir (str): 変換先データディレクトリ（template_sample形式）
        """
        self.source_dir = source_dir
        self.output_dir = output_dir
        
        # 出力ディレクトリが存在しない場合は作成
        os.makedirs(output_dir, exist_ok=True)
    
    def timecode_to_seconds(self, timecode):
        """
        タイムコード形式を秒数に変換
        
        Args:
            timecode (str): "00:00:00:00"形式のタイムコード
            
        Returns:
            float: 秒数
        """
        hours, minutes, seconds, frames = map(int, timecode.split(':'))
        # フレームレートを30fpsと仮定
        return hours * 3600 + minutes * 60 + seconds + frames / 30
    
    def find_source_files(self):
        """
        変換元のJSONファイルを検索
        
        Returns:
            list: JSONファイルパスのリスト
        """
        # ts/ts/GH01xxxx_captures/GH01xxxx_data.jsonを検索
        pattern = os.path.join(self.source_dir, "ts", "ts", "*_captures", "*_data.json")
        return glob.glob(pattern)
    
    def create_output_structure(self, video_id):
        """
        出力ディレクトリ構造を作成
        
        Args:
            video_id (str): 動画ID（例: "GH012846"）
            
        Returns:
            dict: 作成したディレクトリパスの辞書
        """
        # video_nodes_GH01xxxx/keyframes/
        # video_nodes_GH01xxxx/previews/
        base_dir = os.path.join(self.output_dir, f"video_nodes_{video_id}")
        keyframes_dir = os.path.join(base_dir, "keyframes")
        previews_dir = os.path.join(base_dir, "previews")
        
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(keyframes_dir, exist_ok=True)
        os.makedirs(previews_dir, exist_ok=True)
        
        return {
            "base": base_dir,
            "keyframes": keyframes_dir,
            "previews": previews_dir
        }
    
    def copy_and_rename_images(self, source_dir, video_id, output_dirs):
        """
        画像ファイルをコピーして名前を変更
        
        Args:
            source_dir (str): 元画像ファイルのディレクトリ
            video_id (str): 動画ID
            output_dirs (dict): 出力ディレクトリ情報
            
        Returns:
            dict: シーンIDとキーフレームパスのマッピング
        """
        # scene_XXXX.jpg → keyframe_XXXX.jpg
        scene_images = glob.glob(os.path.join(source_dir, "scene_*.jpg"))
        keyframe_mapping = {}
        
        for scene_path in scene_images:
            # ファイル名から番号を抽出（scene_0001.jpg → 0001）
            scene_filename = os.path.basename(scene_path)
            scene_number = scene_filename.replace("scene_", "").replace(".jpg", "")
            
            # キーフレーム名を生成（keyframe_0001.jpg）
            keyframe_filename = f"keyframe_{scene_number}.jpg"
            keyframe_path = os.path.join(output_dirs["keyframes"], keyframe_filename)
            
            # 画像をコピー
            shutil.copy2(scene_path, keyframe_path)
            
            # 相対パスを保存（Windowsスタイルのパス区切り）
            rel_path = f"video_nodes_{video_id}\\keyframes\\{keyframe_filename}"
            keyframe_mapping[int(scene_number)] = rel_path
        
        return keyframe_mapping
    
    def generate_preview_paths(self, video_id, scene_ids):
        """
        プレビュー動画のパスを生成
        
        Args:
            video_id (str): 動画ID
            scene_ids (list): シーンIDのリスト
            
        Returns:
            dict: シーンIDとプレビューパスのマッピング
        """
        preview_mapping = {}
        
        for scene_id in scene_ids:
            # プレビューファイル名を生成（preview_0001.mp4）
            preview_filename = f"preview_{scene_id:04d}.mp4"
            
            # 相対パスを保存（Windowsスタイルのパス区切り）
            rel_path = f"video_nodes_{video_id}\\previews\\{preview_filename}"
            preview_mapping[scene_id] = rel_path
        
        return preview_mapping
    
    def convert_file(self, json_path):
        """
        1つのJSONファイルを変換
        
        Args:
            json_path (str): 変換元JSONファイルのパス
            
        Returns:
            tuple: (video_id, 変換後のJSONデータ)
        """
        # JSONファイルを読み込み
        with open(json_path, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
        
        # 動画IDを抽出（GH01xxxx_data.json → GH01xxxx）
        json_filename = os.path.basename(json_path)
        video_id = json_filename.replace("_data.json", "")
        
        # 出力ディレクトリ構造を作成
        output_dirs = self.create_output_structure(video_id)
        
        # 画像ファイルをコピーして名前を変更
        source_dir = os.path.dirname(json_path)
        keyframe_mapping = self.copy_and_rename_images(source_dir, video_id, output_dirs)
        
        # シーンIDのリストを取得
        scene_ids = [scene["scene_id"] for scene in source_data["detected_scenes"]]
        
        # プレビューパスを生成
        preview_mapping = self.generate_preview_paths(video_id, scene_ids)
        
        # トランスクリプトをシーンIDでマッピング
        transcript_mapping = {}
        for segment in source_data.get("final_segments", []):
            scene_id = segment.get("scene_id")
            if scene_id:
                transcript_mapping[scene_id] = segment.get("transcription", "")
        
        # 変換後のシーンリストを作成
        scenes = []
        for scene in source_data["detected_scenes"]:
            scene_id = scene["scene_id"]
            start_time = self.timecode_to_seconds(scene["start_timecode"])
            end_time = self.timecode_to_seconds(scene["end_timecode"])
            duration = end_time - start_time
            
            # キーフレームパスを取得（存在しない場合はデフォルト値）
            keyframe_path = keyframe_mapping.get(scene_id, f"video_nodes_{video_id}\\keyframes\\keyframe_0000.jpg")
            
            # プレビューパスを取得
            preview_path = preview_mapping.get(scene_id, "")
            
            # トランスクリプトを取得（存在しない場合は空文字）
            transcript = transcript_mapping.get(scene_id, "")
            
            # シーンデータを作成
            scene_data = {
                "scene_id": scene_id,
                "time_in": start_time,
                "time_out": end_time,
                "transcript": transcript,
                "description": scene["description"],
                "keyframe_path": keyframe_path,
                "preview_path": preview_path,
                "duration": duration
            }
            
            scenes.append(scene_data)
        
        # 変換後のJSONデータを作成
        output_data = {
            "scenes": scenes,
            "completed": True,
            "last_update": datetime.datetime.now().isoformat()
        }
        
        # 変換後のJSONファイルを保存
        output_json_path = os.path.join(output_dirs["base"], "nodes.json")
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return video_id, output_data
    
    def convert_all(self):
        """
        すべてのファイルを変換
        
        Returns:
            dict: 変換結果の辞書（動画ID: 変換後データ）
        """
        result = {}
        
        # 変換元ファイルを検索
        source_files = self.find_source_files()
        
        # 各ファイルを変換
        for json_path in source_files:
            video_id, output_data = self.convert_file(json_path)
            result[video_id] = output_data
            print(f"Converted: {video_id}")
        
        return result

if __name__ == "__main__":
    # 変換元と変換先のディレクトリを指定
    source_dir = "/home/ubuntu/data_analysis"
    output_dir = "/home/ubuntu/data_analysis/converted"
    
    # コンバータを初期化して実行
    converter = VideoDataConverter(source_dir, output_dir)
    result = converter.convert_all()
    
    print(f"Conversion completed. Converted {len(result)} video files.")
