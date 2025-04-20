#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import contextmanager
import datetime

# データモデル定義
class Scene(BaseModel):
    scene_id: int
    time_in: float
    time_out: float
    transcript: str
    description: str
    keyframe_path: str
    preview_path: str
    duration: float

class Video(BaseModel):
    video_id: str
    source_filepath: Optional[str] = None
    duration_seconds: Optional[float] = None
    creation_time: Optional[str] = None
    completed: bool = True
    last_update: str
    scenes: List[Scene] = []

# データベース接続
DB_PATH = "/home/ubuntu/data_analysis/video_data.db"
STATIC_FILES_DIR = "/home/ubuntu/data_analysis/converted"

@contextmanager
def get_db_connection():
    """データベース接続のコンテキストマネージャ"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# FastAPIアプリケーション
app = FastAPI(
    title="動画データAPI",
    description="変換された動画データにアクセスするためのAPI",
    version="1.0.0"
)

# 静的ファイル配信の設定
app.mount("/static", StaticFiles(directory=STATIC_FILES_DIR), name="static")

@app.get("/")
async def root():
    """APIルートエンドポイント"""
    return {
        "message": "動画データAPI",
        "version": "1.0.0",
        "endpoints": [
            "/api/videos",
            "/api/videos/{video_id}",
            "/api/videos/{video_id}/scenes/{scene_id}",
            "/api/keyframes/{video_id}/{scene_id}"
        ]
    }

@app.get("/api/videos", response_model=List[Video])
async def get_videos():
    """全動画のリストを取得"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT video_id, source_filepath, duration_seconds, creation_time, 
               completed, last_update
        FROM videos
        """)
        videos = []
        for row in cursor.fetchall():
            video = Video(
                video_id=row["video_id"],
                source_filepath=row["source_filepath"],
                duration_seconds=row["duration_seconds"],
                creation_time=row["creation_time"],
                completed=bool(row["completed"]),
                last_update=row["last_update"],
                scenes=[]
            )
            videos.append(video)
        return videos

@app.get("/api/videos/{video_id}", response_model=Video)
async def get_video(video_id: str):
    """特定の動画の詳細情報とシーンリストを取得"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 動画情報を取得
        cursor.execute("""
        SELECT video_id, source_filepath, duration_seconds, creation_time, 
               completed, last_update
        FROM videos
        WHERE video_id = ?
        """, (video_id,))
        
        video_row = cursor.fetchone()
        if not video_row:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
        
        # シーン情報を取得
        cursor.execute("""
        SELECT scene_id, time_in, time_out, transcript, description, 
               keyframe_path, preview_path, duration
        FROM scenes
        WHERE video_id = ?
        ORDER BY scene_id
        """, (video_id,))
        
        scenes = []
        for row in cursor.fetchall():
            scene = Scene(
                scene_id=row["scene_id"],
                time_in=row["time_in"],
                time_out=row["time_out"],
                transcript=row["transcript"],
                description=row["description"],
                keyframe_path=row["keyframe_path"],
                preview_path=row["preview_path"],
                duration=row["duration"]
            )
            scenes.append(scene)
        
        # 動画オブジェクトを作成
        video = Video(
            video_id=video_row["video_id"],
            source_filepath=video_row["source_filepath"],
            duration_seconds=video_row["duration_seconds"],
            creation_time=video_row["creation_time"],
            completed=bool(video_row["completed"]),
            last_update=video_row["last_update"],
            scenes=scenes
        )
        
        return video

@app.get("/api/videos/{video_id}/scenes/{scene_id}", response_model=Scene)
async def get_scene(video_id: str, scene_id: int):
    """特定のシーンの詳細情報を取得"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT scene_id, time_in, time_out, transcript, description, 
               keyframe_path, preview_path, duration
        FROM scenes
        WHERE video_id = ? AND scene_id = ?
        """, (video_id, scene_id))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404, 
                detail=f"Scene {scene_id} not found for video {video_id}"
            )
        
        scene = Scene(
            scene_id=row["scene_id"],
            time_in=row["time_in"],
            time_out=row["time_out"],
            transcript=row["transcript"],
            description=row["description"],
            keyframe_path=row["keyframe_path"],
            preview_path=row["preview_path"],
            duration=row["duration"]
        )
        
        return scene

@app.get("/api/keyframes/{video_id}/{scene_id}")
async def get_keyframe(video_id: str, scene_id: int):
    """キーフレーム画像を取得"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT keyframe_path
        FROM scenes
        WHERE video_id = ? AND scene_id = ?
        """, (video_id, scene_id))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404, 
                detail=f"Keyframe for scene {scene_id} not found for video {video_id}"
            )
        
        # パスを変換（Windowsスタイル → Unixスタイル）
        keyframe_path = row["keyframe_path"].replace("\\", "/")
        
        # 静的ファイルのパスを構築
        file_path = os.path.join(STATIC_FILES_DIR, keyframe_path)
        
        # ファイルが存在するか確認
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404, 
                detail=f"Keyframe file not found: {keyframe_path}"
            )
        
        return FileResponse(file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
