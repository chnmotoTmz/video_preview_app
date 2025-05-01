from flask import Flask, jsonify, request, send_file, Response, render_template
from flask_cors import CORS
import sqlite3
import os
import json
import tempfile
import mimetypes
from pathlib import Path
import re
import argparse
import logging
import io # For send_file with BytesIO

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)  # クロスオリジンリクエストを許可

DATABASE = 'video_data.db'  # デフォルトのデータベースパス
DEFAULT_FRAME_RATE = 30.0 # デフォルトフレームレート

def get_db_connection():
    """データベース接続を取得"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def resolve_path(relative_path):
    """データベース内の相対パスを絶対パスに解決"""
    video_base_folder = app.config.get('VIDEO_BASE_FOLDER')
    if not video_base_folder:
        logger.error("VIDEO_BASE_FOLDER is not configured")
        raise ValueError("VIDEO_BASE_FOLDER is not configured.")

    normalized_relative_path = Path(relative_path).as_posix()
    absolute_path = os.path.abspath(os.path.join(video_base_folder, normalized_relative_path))
    return absolute_path

# --- タイムコード変換ヘルパー関数 ---
def timecode_to_seconds(timecode, frame_rate=DEFAULT_FRAME_RATE):
    """Converts HH:MM:SS:FF timecode string to seconds (float)."""
    if not timecode or not isinstance(timecode, str):
        return 0.0
    parts = timecode.split(':')
    if len(parts) != 4:
        logger.warning(f"Invalid timecode format: {timecode}")
        return 0.0
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        frames = int(parts[3])
        total_seconds = hours * 3600 + minutes * 60 + seconds + frames / frame_rate
        return total_seconds
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing timecode '{timecode}': {e}")
        return 0.0

def seconds_to_timecode(total_seconds, frame_rate=DEFAULT_FRAME_RATE):
    """Converts seconds (float or int) to HH:MM:SS:FF timecode string."""
    if total_seconds is None or not isinstance(total_seconds, (int, float)) or total_seconds < 0:
        return "00:00:00:00"
    try:
        total_seconds = max(0.0, float(total_seconds))
        total_frames = int(round(total_seconds * frame_rate))
        frames = total_frames % int(frame_rate)
        total_seconds_int = total_frames // int(frame_rate)
        seconds = total_seconds_int % 60
        total_minutes = total_seconds_int // 60
        minutes = total_minutes % 60
        hours = total_minutes // 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
    except Exception as e:
        logger.error(f"Error converting seconds {total_seconds} to timecode: {e}")
        return "00:00:00:00"

def seconds_to_srt_timecode(total_seconds):
    """Converts seconds (float or int) to HH:MM:SS,ms format for SRT."""
    if total_seconds is None or not isinstance(total_seconds, (int, float)) or total_seconds < 0:
        return "00:00:00,000"
    try:
        total_seconds = max(0.0, float(total_seconds))
        milliseconds = int(round((total_seconds % 1) * 1000))
        total_seconds_int = int(total_seconds)
        seconds = total_seconds_int % 60
        total_minutes = total_seconds_int // 60
        minutes = total_minutes % 60
        hours = total_minutes // 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    except Exception as e:
        logger.error(f"Error converting seconds {total_seconds} to SRT timecode: {e}")
        return "00:00:00,000"

# seconds_to_edl_timecode は seconds_to_timecode と同じなので、エイリアスとして扱うか、そのまま使う
seconds_to_edl_timecode = seconds_to_timecode

# --- 既存のAPIエンドポイント (省略) ---

@app.route('/')
def index():
    """メインページを表示"""
    try:
        return app.send_static_file('index.html')
    except FileNotFoundError:
        return "Error: index.html not found in static folder.", 404

@app.route('/api/videos')
def get_videos():
    """全ての動画リストを取得"""
    conn = get_db_connection()
    videos = conn.execute('SELECT * FROM videos ORDER BY filename').fetchall()
    conn.close()
    return jsonify([dict(video) for video in videos])

@app.route('/api/video/<int:video_id>')
def get_video(video_id):
    """特定の動画情報を取得"""
    conn = get_db_connection()
    video = conn.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()
    conn.close()

    if video is None:
        return jsonify({"error": "Video not found"}), 404
    
    return jsonify(dict(video))

@app.route('/api/scenes/<int:video_id>')
def get_scenes(video_id):
    """動画のシーン情報を取得"""
    conn = get_db_connection()
    scenes = conn.execute(
        'SELECT * FROM scenes WHERE video_id = ? ORDER BY scene_id',
        (video_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(scene) for scene in scenes])

@app.route('/api/transcriptions/<int:video_id>')
def get_transcriptions(video_id):
    """動画の字幕情報を取得"""
    conn = get_db_connection()
    transcriptions = conn.execute(
        'SELECT * FROM transcriptions WHERE video_id = ? ORDER BY start_timecode',
        (video_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(trans) for trans in transcriptions])

@app.route('/api/thumbnails/<int:scene_pk>')
def get_thumbnail_by_scene_pk(scene_pk):
    """シーンの主キー(id)に基づいてサムネイル画像を取得"""
    conn = get_db_connection()
    scene = conn.execute('SELECT thumbnail_path FROM scenes WHERE id = ?', (scene_pk,)).fetchone()
    conn.close()

    if scene is None or not scene['thumbnail_path']:
        try:
            placeholder_path = os.path.join(app.static_folder, 'placeholder.jpg')
            if os.path.exists(placeholder_path):
                return send_file(placeholder_path, mimetype='image/jpeg')
            return jsonify({"error": "Thumbnail and placeholder not found"}), 404
        except Exception as e:
            logger.error(f"Error sending placeholder image: {e}")
            return jsonify({"error": "Error serving placeholder image"}), 500

    try:
        thumbnail_abs_path = resolve_path(scene['thumbnail_path'])
        if os.path.exists(thumbnail_abs_path):
            return send_file(thumbnail_abs_path, mimetype='image/jpeg')
        
        # ファイルが見つからない場合はプレースホルダーを試す
        placeholder_path = os.path.join(app.static_folder, 'placeholder.jpg')
        if os.path.exists(placeholder_path):
            return send_file(placeholder_path, mimetype='image/jpeg')
        return jsonify({"error": "Thumbnail and placeholder not found"}), 404
    except Exception as e:
        logger.error(f"Error serving thumbnail: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stream/<int:video_id>')
def stream_video(video_id):
    """動画ファイルをストリーミング"""
    conn = get_db_connection()
    video = conn.execute('SELECT filepath FROM videos WHERE id = ?', (video_id,)).fetchone()
    conn.close()

    if video is None:
        return jsonify({"error": "Video not found in DB"}), 404

    try:
        video_abs_path = resolve_path(video['filepath'])
        if not os.path.exists(video_abs_path):
            return jsonify({"error": f"Video file not found"}), 404

        range_header = request.headers.get('Range', None)
        file_size = os.path.getsize(video_abs_path)

        if range_header:
            byte1, byte2 = 0, None
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                groups = match.groups()
                if groups[0]:
                    byte1 = int(groups[0])
                if groups[1]:
                    byte2 = int(groups[1])

            if byte2 is None:
                byte2 = file_size - 1

            length = byte2 - byte1 + 1

            def generate_stream():
                chunk_size = 1024 * 1024  # 1MB
                with open(video_abs_path, 'rb') as f:
                    f.seek(byte1)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)

            resp = Response(
                generate_stream(),
                status=206,
                mimetype='video/mp4',
                direct_passthrough=True
            )

            resp.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
            resp.headers.add('Accept-Ranges', 'bytes')
            resp.headers.add('Content-Length', str(length))
            return resp

        return send_file(video_abs_path, mimetype='video/mp4')

    except Exception as e:
        logger.error(f"Error streaming video: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/combined_data/all')
def get_all_combined_data():
    """すべての動画に対するシーン・字幕データを一括取得"""
    try:
        conn = get_db_connection()
        query = """
            -- シーンと発言の関連データを一括取得するクエリ
            -- LEFT JOINを使用して、発言が無いシーンも取得可能
            SELECT 
                -- 動画情報
                v.id as video_id,
                v.filename as video_filename,
                
                -- シーン情報
                s.id as scene_pk,                  -- シーンの主キー
                s.scene_id as scene_number,        -- シーンの通し番号
                s.start_timecode as scene_start,   -- シーン開始時間
                s.end_timecode as scene_end,       -- シーン終了時間
                s.description as scene_description,
                s.evaluation_tag as scene_evaluation_tag,
                s.scene_good_reason,
                s.scene_bad_reason,
                s.thumbnail_path as scene_thumbnail_path,
                
                -- 発言（字幕）情報
                t.id as transcription_id,
                t.start_timecode as transcription_start,  -- 発言開始時間
                t.end_timecode as transcription_end,      -- 発言終了時間
                t.transcription as dialogue,              -- 発言内容
                t.transcription_good_reason,
                t.transcription_bad_reason
            FROM videos v
            LEFT JOIN scenes s 
                ON v.id = s.video_id
            LEFT JOIN transcriptions t 
                ON s.id = t.scene_id
            -- シーン番号とタイムコードで階層的にソート
            ORDER BY 
                v.id,                  -- 動画単位
                s.scene_id,           -- シーン順
                t.start_timecode      -- 発言順
        """
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(results)
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error in combined_data: {e}")
        return jsonify({"error": f"データ取得に失敗: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/settings/base_folder', methods=['PUT'])
def update_base_folder():
    """ベースフォルダのパスを更新"""
    data = request.json
    if not data or 'path' not in data:
        return jsonify({"error": "パスが指定されていません"}), 400
        
    new_path = data['path']
    if not os.path.isdir(new_path):
        return jsonify({"error": "指定されたパスが存在しないか、フォルダではありません"}), 400
    
    app.config['VIDEO_BASE_FOLDER'] = os.path.abspath(new_path)
    return jsonify({"success": True, "path": app.config['VIDEO_BASE_FOLDER']})

@app.route('/api/settings/base_folder', methods=['GET'])
def get_base_folder():
    """現在のベースフォルダのパスを取得"""
    return jsonify({"path": app.config.get('VIDEO_BASE_FOLDER', "")})

@app.route('/api/merged_data/all', methods=['GET'])
def get_all_merged_data():
    """
    すべての動画のシーンデータと字幕データをマージして一括で返すAPI。
    シーンを基準とし、関連する字幕データ（最初に見つかったもの）と動画情報を結合する。
    """
    logger.info("Received request for all merged data.")
    conn = None # Initialize conn to None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. すべての動画情報を取得し、IDをキーとする辞書に変換
        cursor.execute('SELECT id, filename, filepath, timecode_offset, duration_seconds FROM videos ORDER BY id')
        videos_list = cursor.fetchall()
        videos_map = {v['id']: dict(v) for v in videos_list}
        logger.info(f"Found {len(videos_map)} videos.")

        # 2. すべてのシーンデータを取得
        cursor.execute('SELECT * FROM scenes ORDER BY video_id, scene_id')
        scenes = cursor.fetchall()
        logger.info(f"Found {len(scenes)} scenes.")

        # 3. すべての字幕データを取得
        cursor.execute('SELECT * FROM transcriptions ORDER BY scene_id, start_timecode')
        transcriptions = cursor.fetchall()
        logger.info(f"Found {len(transcriptions)} transcriptions.")

        # 4. 字幕データを scene_id (scenesテーブルの主キー) をキーとする辞書に変換
        transcription_map = {}
        for t_row in transcriptions:
            transcription = dict(t_row)
            scene_id_key = transcription.get('scene_id')
            if scene_id_key is not None and scene_id_key not in transcription_map:
                transcription_map[scene_id_key] = transcription
        logger.info(f"Created transcription map with {len(transcription_map)} entries.")

        # 5. シーンデータに字幕データと動画情報をマージ
        all_merged_data = []
        for scene_row in scenes:
            scene = dict(scene_row)
            merged_row = scene.copy()
            scene_pk = scene.get('id')
            video_id = scene.get('video_id')

            # --- 字幕データのマージ ---
            related_transcription = transcription_map.get(scene_pk)
            if related_transcription:
                merged_row['transcription'] = related_transcription.get('transcription')
                merged_row['transcription_start_timecode'] = related_transcription.get('start_timecode')
                merged_row['transcription_end_timecode'] = related_transcription.get('end_timecode')
                merged_row['transcription_good_reason'] = related_transcription.get('transcription_good_reason')
                merged_row['transcription_bad_reason'] = related_transcription.get('transcription_bad_reason')
                merged_row['transcription_id'] = related_transcription.get('id')
            else:
                merged_row['transcription'] = None
                merged_row['transcription_start_timecode'] = None
                merged_row['transcription_end_timecode'] = None
                merged_row['transcription_good_reason'] = None
                merged_row['transcription_bad_reason'] = None
                merged_row['transcription_id'] = None

            # --- 動画情報のマージ ---
            related_video = videos_map.get(video_id)
            if related_video:
                merged_row['video_filename'] = related_video.get('filename')
                merged_row['video_filepath'] = related_video.get('filepath')
                # end_timecodeを計算して追加
                offset = related_video.get('timecode_offset')
                duration = related_video.get('duration_seconds')
                def timecode_to_seconds(tc, frame_rate=60.0):
                    h, m, s, f = map(int, tc.split(':'))
                    return h*3600 + m*60 + s + f/frame_rate
                def seconds_to_edl_timecode(total_seconds, frame_rate=60.0):
                    total_frames = int(round(float(total_seconds) * frame_rate))
                    frames = total_frames % int(frame_rate)
                    total_seconds_int = total_frames // int(frame_rate)
                    seconds = total_seconds_int % 60
                    total_minutes = total_seconds_int // 60
                    minutes = total_minutes % 60
                    hours = total_minutes // 60
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
                if offset and duration is not None:
                    try:
                        end_sec = timecode_to_seconds(offset) + float(duration)
                        merged_row['video_end_timecode'] = seconds_to_edl_timecode(end_sec)
                    except Exception as e:
                        merged_row['video_end_timecode'] = None
                else:
                    merged_row['video_end_timecode'] = None
            else:
                merged_row['video_filename'] = None
                merged_row['video_filepath'] = None
                merged_row['video_end_timecode'] = None
                logger.warning(f"Video info not found for video_id {video_id} referenced by scene_pk {scene_pk}")

            # --- フィールド名の整理 (任意) ---
            merged_row['scene_pk'] = scene_pk
            all_merged_data.append(merged_row)

        logger.info(f"Returning {len(all_merged_data)} merged rows.")
        return jsonify(all_merged_data)

    except sqlite3.Error as e:
        logger.error(f"Database error in get_all_merged_data: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error in get_all_merged_data: {e}", exc_info=True)
        return jsonify({"error": f"データ取得に失敗: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/export/srt', methods=['POST'])
def export_srt():
    """選択された字幕データからSRTファイルを生成"""
    data = request.json
    if not data or 'transcription_ids' not in data:
        return jsonify({"error": "transcription_idsが指定されていません"}), 400

    transcription_ids = data['transcription_ids']
    if not isinstance(transcription_ids, list):
        return jsonify({"error": "transcription_idsはリストである必要があります"}), 400

    if not transcription_ids:
        return jsonify({"error": "エクスポートする字幕が選択されていません"}), 400

    conn = None
    try:
        conn = get_db_connection()
        # 字幕データを取得
        safe_ids = [int(tid) for tid in transcription_ids]
        placeholders = ','.join('?' * len(safe_ids))
        query = f"""
            SELECT t.id, t.video_id, t.start_timecode, t.end_timecode, t.transcription
            FROM transcriptions t
            WHERE t.id IN ({placeholders})
            ORDER BY t.id
        """
        cursor = conn.cursor()
        cursor.execute(query, safe_ids)
        transcriptions = cursor.fetchall()

        # EDLと同様のロジックでレコードタイムコードを計算するために、scenesとvideosから情報を取得
        # transcriptionsに対応するvideo_idのリストを取得
        video_ids = list(set(trans['video_id'] for trans in transcriptions))
        video_placeholders = ','.join('?' * len(video_ids))
        scenes_query = f"""
            SELECT 
                s.id as scene_pk, s.video_id, s.scene_id, 
                s.start_timecode, s.end_timecode,
                v.filename as video_filename,
                v.timecode_offset,
                v.duration_seconds
            FROM scenes s
            JOIN videos v ON s.video_id = v.id
            WHERE s.video_id IN ({video_placeholders})
            ORDER BY s.video_id, s.scene_id
        """
        cursor.execute(scenes_query, video_ids)
        scenes = cursor.fetchall()

        # EDLのレコードタイムコードを計算（30fpsで）
        edl_frame_rate = 60.0
        source_frame_rate = 60.0
        record_start_seconds = 0.0
        video_record_offsets = {}  # video_id -> レコードINタイムコード（秒）

        for scene in scenes:
            # ソースタイムコードにオフセットを適用（EDLと同じロジック）
            offset_sec = timecode_to_seconds(scene['timecode_offset'], source_frame_rate) if scene['timecode_offset'] else 0.0
            source_start_sec = timecode_to_seconds(scene['start_timecode'], source_frame_rate)
            source_end_sec = timecode_to_seconds(scene['end_timecode'], source_frame_rate)
            adjusted_start_sec = source_start_sec + offset_sec
            adjusted_end_sec = source_end_sec + offset_sec

            # クリップの終了点を制限
            duration_sec = float(scene['duration_seconds']) if scene['duration_seconds'] is not None else None
            clip_end_sec = offset_sec + duration_sec if duration_sec is not None else None
            if clip_end_sec is not None and adjusted_end_sec > clip_end_sec:
                adjusted_end_sec = clip_end_sec

            # 継続時間を計算
            source_duration_sec = max(0.0, adjusted_end_sec - adjusted_start_sec)
            if source_duration_sec < 1.0 / source_frame_rate:
                adjusted_end_sec = adjusted_start_sec + (1.0 / source_frame_rate)
                source_duration_sec = 1.0 / source_frame_rate

            # レコードタイムコードの計算
            record_in_sec = record_start_seconds
            record_out_sec = record_start_seconds + source_duration_sec

            # video_idに対応するレコードINタイムコードを保存
            video_record_offsets[scene['video_id']] = record_in_sec
            record_start_seconds = record_out_sec

        # SRTファイルを生成
        srt_content = ""
        for i, trans in enumerate(transcriptions):
            # 字幕の開始・終了時間を取得（ゼロスタート）
            start_sec = timecode_to_seconds(trans['start_timecode'], source_frame_rate)
            end_sec = timecode_to_seconds(trans['end_timecode'], source_frame_rate)

            # video_idに対応するレコードINタイムコードをオフセットとして加算
            video_id = trans['video_id']
            record_offset_sec = video_record_offsets.get(video_id, 0.0)
            adjusted_start_sec = start_sec + record_offset_sec
            adjusted_end_sec = end_sec + record_offset_sec

            # SRT形式に変換
            start_srt = seconds_to_srt_timecode(adjusted_start_sec)
            end_srt = seconds_to_srt_timecode(adjusted_end_sec)
            text = trans['transcription'] if trans['transcription'] else ""

            srt_content += f"{i + 1}\n"
            srt_content += f"{start_srt} --> {end_srt}\n"
            srt_content += f"{text}\n\n"

        srt_bytes = srt_content.encode('utf-8')
        return send_file(
            io.BytesIO(srt_bytes),
            mimetype='application/x-subrip',
            as_attachment=True,
            download_name='export.srt'
        )

    except sqlite3.Error as e:
        logger.error(f"Database error during SRT export: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except ValueError:
         return jsonify({"error": "無効なtranscription_idが含まれています"}), 400
    except Exception as e:
        logger.error(f"Error during SRT export: {e}", exc_info=True)
        return jsonify({"error": f"SRTエクスポート中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/export/edl', methods=['POST'])
def export_edl():
    data = request.json
    if not data or 'scene_pks' not in data:
        return jsonify({"error": "scene_pksが指定されていません"}), 400

    scene_pks = data['scene_pks']
    if not isinstance(scene_pks, list):
        return jsonify({"error": "scene_pksはリストである必要があります"}), 400

    if not scene_pks:
        return jsonify({"error": "エクスポートするシーンが選択されていません"}), 400

    conn = None
    try:
        conn = get_db_connection()
        safe_pks = [int(pk) for pk in scene_pks]
        placeholders = ','.join('?' * len(safe_pks))
        query = f"""
            SELECT 
                s.id as scene_pk, s.video_id, s.scene_id, 
                s.start_timecode, s.end_timecode,
                v.filename as video_filename,
                v.timecode_offset,
                v.duration_seconds
            FROM scenes s
            JOIN videos v ON s.video_id = v.id
            WHERE s.id IN ({placeholders})
            ORDER BY s.video_id, s.scene_id
        """
        cursor = conn.cursor()
        cursor.execute(query, safe_pks)
        scenes = cursor.fetchall()

        edl_content = "TITLE: Video Preprocessing Export\n"
        edl_content += "FCM: NON-DROP FRAME\n\n"
        
        record_start_seconds = 0.0
        source_frame_rate = 60.0  # 元の動画は60fps
        edl_frame_rate = 60.0     # EDLも60fpsで出力（DaVinci Resolve用）

        for i, scene in scenes:
            event_num = f"{i + 1:03d}"
            reel_name = os.path.splitext(scene['video_filename'])[0][:8].upper()
            track_type = "V"
            edit_type = "C"

            # タイムコードオフセットを秒に変換（60fpsで計算）
            offset_sec = timecode_to_seconds(scene['timecode_offset'], source_frame_rate) if scene['timecode_offset'] else 0.0
            
            # シーン開始・終了タイムコードを秒に変換（60fpsで計算）
            source_start_sec = timecode_to_seconds(scene['start_timecode'], source_frame_rate)
            source_end_sec = timecode_to_seconds(scene['end_timecode'], source_frame_rate)

            # ソースタイムコードにオフセットを適用
            adjusted_start_sec = source_start_sec + offset_sec
            adjusted_end_sec = source_end_sec + offset_sec

            # クリップの終了点を計算
            duration_sec = float(scene['duration_seconds']) if scene['duration_seconds'] is not None else None
            clip_end_sec = offset_sec + duration_sec if duration_sec is not None else None

            # GH012936.MP4のとき詳細ログ出力
            if scene['video_filename'] == 'GH012936.MP4':
                logger.info(f"[EDL] GH012936.MP4: start_tc={scene['start_timecode']} end_tc={scene['end_timecode']} offset_tc={scene['timecode_offset']}")
                logger.info(f"[EDL] GH012936.MP4: source_start_sec={source_start_sec} offset_sec={offset_sec} adjusted_start_sec={adjusted_start_sec}")
                logger.info(f"[EDL] GH012936.MP4: adjusted_end_sec(before)={adjusted_end_sec}")
                if clip_end_sec is not None:
                    logger.info(f"[EDL] GH012936.MP4: duration_sec={duration_sec} clip_end_sec={clip_end_sec}")

            # 終了点が動画の長さを超えないように制限
            if clip_end_sec is not None and adjusted_end_sec > clip_end_sec:
                adjusted_end_sec = clip_end_sec
                if scene['video_filename'] == 'GH012936.MP4':
                    logger.info(f"[EDL] GH012936.MP4: 動画長さ補正後 adjusted_end_sec={adjusted_end_sec}")

            # 継続時間を計算し、最小デュレーションを保証（60fps基準）
            source_duration_sec = max(0.0, adjusted_end_sec - adjusted_start_sec)
            if source_duration_sec < 1.0 / source_frame_rate:
                adjusted_end_sec = adjusted_start_sec + (1.0 / source_frame_rate)
                source_duration_sec = 1.0 / source_frame_rate
                if scene['video_filename'] == 'GH012936.MP4':
                    logger.info(f"[EDL] GH012936.MP4: 最小デュレーション補正後 source_duration_sec={source_duration_sec}")

            # ソースタイムコードを60fpsでEDL用に変換
            source_in_tc = seconds_to_edl_timecode(adjusted_start_sec, edl_frame_rate)
            source_out_tc = seconds_to_edl_timecode(adjusted_end_sec, edl_frame_rate)

            if scene['video_filename'] == 'GH012936.MP4':
                logger.info(f"[EDL] GH012936.MP4: 60fps変換後 source_in_tc={source_in_tc} source_out_tc={source_out_tc}")

            # レコードタイムコードの計算（60fps基準）
            record_in_sec = record_start_seconds
            # ソースの継続時間（秒）は変わらないが、レコードタイムコードは60fpsで表現
            record_out_sec = record_start_seconds + source_duration_sec
            record_in_tc = seconds_to_edl_timecode(record_in_sec, edl_frame_rate)
            record_out_tc = seconds_to_edl_timecode(record_out_sec, edl_frame_rate)

            if scene['video_filename'] == 'GH012936.MP4':
                logger.info(f"[EDL] GH012936.MP4: record_in_tc={record_in_tc} record_out_tc={record_out_tc} duration={source_duration_sec}秒")

            # EDL行を生成
            edl_content += f"{event_num}  {reel_name:<8} {track_type}     {edit_type}        {source_in_tc} {source_out_tc} {record_in_tc} {record_out_tc}\n"
            edl_content += f"* FROM CLIP NAME: {scene['video_filename']}\n\n"

            record_start_seconds = record_out_sec

        edl_bytes = edl_content.encode('utf-8')
        return send_file(
            io.BytesIO(edl_bytes),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='export.edl'
        )

    except sqlite3.Error as e:
        logger.error(f"Database error during EDL export: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except ValueError:
        return jsonify({"error": "無効なscene_pkが含まれています"}), 400
    except Exception as e:
        logger.error(f"Error during EDL export: {e}", exc_info=True)
        return jsonify({"error": f"EDLエクスポート中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/scenes/delete', methods=['POST']) # Using POST for simplicity, could be DELETE
def delete_scenes():
    """選択されたシーンをデータベースから削除"""
    data = request.json
    if not data or 'scene_pks' not in data:
        return jsonify({"error": "scene_pksが指定されていません"}), 400

    scene_pks = data['scene_pks']
    if not isinstance(scene_pks, list):
        return jsonify({"error": "scene_pksはリストである必要があります"}), 400

    if not scene_pks:
        return jsonify({"error": "削除するシーンが選択されていません"}), 400

    conn = None
    deleted_count = 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Ensure IDs are integers
        safe_pks = [int(pk) for pk in scene_pks]
        placeholders = ','.join('?' * len(safe_pks))

        # --- トランザクション開始 ---
        conn.execute('BEGIN TRANSACTION')

        # 1. 関連する字幕を削除 (scene_id は scenes テーブルの主キーを参照している)
        # logger.info(f"Deleting transcriptions associated with scene_pks: {safe_pks}")
        # delete_trans_query = f"DELETE FROM transcriptions WHERE scene_id IN ({placeholders})"
        # cursor.execute(delete_trans_query, safe_pks)
        # logger.info(f"Deleted {cursor.rowcount} transcriptions.")
        # → 字幕はシーンに紐づくのではなく、動画全体に紐づく可能性もあるため、シーン削除時に字幕は削除しない方針に変更
        #   もしシーンに厳密に紐づくなら上記コメントアウトを解除

        # 2. シーン自体を削除
        logger.info(f"Deleting scenes with pks: {safe_pks}")
        delete_scene_query = f"DELETE FROM scenes WHERE id IN ({placeholders})"
        cursor.execute(delete_scene_query, safe_pks)
        deleted_count = cursor.rowcount
        logger.info(f"Deleted {deleted_count} scenes.")

        # --- トランザクションコミット ---
        conn.commit()

        return jsonify({"success": True, "deleted_count": deleted_count})

    except sqlite3.Error as e:
        if conn:
            conn.rollback() # エラー時はロールバック
        logger.error(f"Database error during scene deletion: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except ValueError:
        if conn:
            conn.rollback()
        return jsonify({"error": "無効なscene_pkが含まれています"}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error during scene deletion: {e}", exc_info=True)
        return jsonify({"error": f"シーン削除中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

# --- テーブルレコード編集用APIエンドポイント ---
@app.route('/api/videos/<int:video_id>', methods=['PUT'])
def update_video(video_id):
    """特定の動画レコードを更新する"""
    data = request.json
    if not data:
        return jsonify({"error": "データが指定されていません"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 更新可能なフィールドと型のマッピング
        allowed_fields = {
            'filename': str,
            'filepath': str,
            'duration_seconds': float,
            'timecode_offset': str,
            'description': str
        }
        
        # SQLクエリの組み立て
        update_fields = []
        update_values = []
        
        for field, value in data.items():
            if field in allowed_fields:
                # 値の型チェックと変換（None値は許可）
                if value is not None and not isinstance(value, allowed_fields[field]):
                    try:
                        if allowed_fields[field] == float:
                            value = float(value)
                        elif allowed_fields[field] == int:
                            value = int(value)
                        elif allowed_fields[field] == str:
                            value = str(value)
                    except (ValueError, TypeError):
                        return jsonify({"error": f"フィールド '{field}' の値 '{value}' は {allowed_fields[field].__name__} 型として無効です"}), 400
                
                # フィールドと値を追加
                update_fields.append(f"{field} = ?")
                update_values.append(value)
        
        if not update_fields:
            return jsonify({"error": "更新可能なフィールドが指定されていません"}), 400
        
        # 更新クエリの実行
        query = f"UPDATE videos SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(video_id)
        
        cursor.execute(query, update_values)
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({"error": f"ID {video_id} の動画レコードが見つかりません"}), 404
        
        # 更新後のデータを返す
        video = conn.execute('SELECT * FROM videos WHERE id = ?', (video_id,)).fetchone()
        return jsonify({"success": True, "data": dict(video)})
        
    except sqlite3.Error as e:
        logger.error(f"Database error during video update: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error during video update: {e}", exc_info=True)
        return jsonify({"error": f"レコード更新中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/scenes/<int:scene_id>', methods=['PUT'])
def update_scene(scene_id):
    """特定のシーンレコードを更新する"""
    data = request.json
    if not data:
        return jsonify({"error": "データが指定されていません"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 更新可能なフィールドと型のマッピング
        allowed_fields = {
            'video_id': int,
            'scene_id': int,
            'start_timecode': str,
            'end_timecode': str,
            'description': str,
            'evaluation_tag': str,
            'scene_good_reason': str,
            'scene_bad_reason': str,
            'thumbnail_path': str
        }
        
        # SQLクエリの組み立て
        update_fields = []
        update_values = []
        
        for field, value in data.items():
            if field in allowed_fields:
                # 値の型チェックと変換（None値は許可）
                if value is not None and not isinstance(value, allowed_fields[field]):
                    try:
                        if allowed_fields[field] == float:
                            value = float(value)
                        elif allowed_fields[field] == int:
                            value = int(value)
                        elif allowed_fields[field] == str:
                            value = str(value)
                    except (ValueError, TypeError):
                        return jsonify({"error": f"フィールド '{field}' の値 '{value}' は {allowed_fields[field].__name__} 型として無効です"}), 400
                
                # フィールドと値を追加
                update_fields.append(f"{field} = ?")
                update_values.append(value)
        
        if not update_fields:
            return jsonify({"error": "更新可能なフィールドが指定されていません"}), 400
        
        # 更新クエリの実行
        query = f"UPDATE scenes SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(scene_id)
        
        cursor.execute(query, update_values)
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({"error": f"ID {scene_id} のシーンレコードが見つかりません"}), 404
        
        # 更新後のデータを返す
        scene = conn.execute('SELECT * FROM scenes WHERE id = ?', (scene_id,)).fetchone()
        return jsonify({"success": True, "data": dict(scene)})
        
    except sqlite3.Error as e:
        logger.error(f"Database error during scene update: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error during scene update: {e}", exc_info=True)
        return jsonify({"error": f"レコード更新中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/transcriptions/<int:transcription_id>', methods=['PUT'])
def update_transcription(transcription_id):
    """特定の字幕レコードを更新する"""
    data = request.json
    if not data:
        return jsonify({"error": "データが指定されていません"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 更新可能なフィールドと型のマッピング
        allowed_fields = {
            'video_id': int,
            'scene_id': int,
            'start_timecode': str,
            'end_timecode': str,
            'transcription': str,
            'transcription_good_reason': str,
            'transcription_bad_reason': str
        }
        
        # SQLクエリの組み立て
        update_fields = []
        update_values = []
        
        for field, value in data.items():
            if field in allowed_fields:
                # 値の型チェックと変換（None値は許可）
                if value is not None and not isinstance(value, allowed_fields[field]):
                    try:
                        if allowed_fields[field] == float:
                            value = float(value)
                        elif allowed_fields[field] == int:
                            value = int(value)
                        elif allowed_fields[field] == str:
                            value = str(value)
                    except (ValueError, TypeError):
                        return jsonify({"error": f"フィールド '{field}' の値 '{value}' は {allowed_fields[field].__name__} 型として無効です"}), 400
                
                # フィールドと値を追加
                update_fields.append(f"{field} = ?")
                update_values.append(value)
        
        if not update_fields:
            return jsonify({"error": "更新可能なフィールドが指定されていません"}), 400
        
        # 更新クエリの実行
        query = f"UPDATE transcriptions SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(transcription_id)
        
        cursor.execute(query, update_values)
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({"error": f"ID {transcription_id} の字幕レコードが見つかりません"}), 404
        
        # 更新後のデータを返す
        transcription = conn.execute('SELECT * FROM transcriptions WHERE id = ?', (transcription_id,)).fetchone()
        return jsonify({"success": True, "data": dict(transcription)})
        
    except sqlite3.Error as e:
        logger.error(f"Database error during transcription update: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error during transcription update: {e}", exc_info=True)
        return jsonify({"error": f"レコード更新中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

# メソッドを追加して、特定レコードを取得するAPIを実装
@app.route('/api/video_fields', methods=['GET'])
def get_video_fields():
    """videos テーブルの編集可能なフィールド情報を取得"""
    fields = {
        'filename': {'type': 'string', 'description': '動画ファイル名'},
        'filepath': {'type': 'string', 'description': '動画ファイルのパス'},
        'duration_seconds': {'type': 'number', 'description': '動画の長さ（秒）'},
        'timecode_offset': {'type': 'string', 'description': 'タイムコードのオフセット（HH:MM:SS:FF形式）'},
        'description': {'type': 'string', 'description': '動画の説明'}
    }
    return jsonify(fields)

@app.route('/api/scene_fields', methods=['GET'])
def get_scene_fields():
    """scenes テーブルの編集可能なフィールド情報を取得"""
    fields = {
        'video_id': {'type': 'integer', 'description': '関連する動画ID'},
        'scene_id': {'type': 'integer', 'description': 'シーン番号'},
        'start_timecode': {'type': 'string', 'description': '開始タイムコード（HH:MM:SS:FF形式）'},
        'end_timecode': {'type': 'string', 'description': '終了タイムコード（HH:MM:SS:FF形式）'},
        'description': {'type': 'string', 'description': 'シーンの説明'},
        'evaluation_tag': {'type': 'string', 'description': '評価タグ（good/bad/neutral等）'},
        'scene_good_reason': {'type': 'string', 'description': '良い評価の理由'},
        'scene_bad_reason': {'type': 'string', 'description': '悪い評価の理由'},
        'thumbnail_path': {'type': 'string', 'description': 'サムネイル画像のパス'}
    }
    return jsonify(fields)

@app.route('/api/transcription_fields', methods=['GET'])
def get_transcription_fields():
    """transcriptions テーブルの編集可能なフィールド情報を取得"""
    fields = {
        'video_id': {'type': 'integer', 'description': '関連する動画ID'},
        'scene_id': {'type': 'integer', 'description': '関連するシーンID'},
        'start_timecode': {'type': 'string', 'description': '開始タイムコード（HH:MM:SS:FF形式）'},
        'end_timecode': {'type': 'string', 'description': '終了タイムコード（HH:MM:SS:FF形式）'},
        'transcription': {'type': 'string', 'description': '字幕のテキスト'},
        'transcription_good_reason': {'type': 'string', 'description': '良い評価の理由'},
        'transcription_bad_reason': {'type': 'string', 'description': '悪い評価の理由'}
    }
    return jsonify(fields)

@app.route('/api/mcp/tables', methods=['GET'])
def get_table_names():
    """データベース内の編集可能なテーブル一覧を取得"""
    tables = [
        {'name': 'videos', 'description': '動画情報テーブル'},
        {'name': 'scenes', 'description': 'シーン情報テーブル'},
        {'name': 'transcriptions', 'description': '字幕情報テーブル'}
    ]
    return jsonify(tables)

@app.route('/api/mcp/records/<string:table_name>', methods=['GET'])
def get_table_records(table_name):
    """指定したテーブルのレコード一覧を取得"""
    # セキュリティ対策：テーブル名のバリデーション
    allowed_tables = ['videos', 'scenes', 'transcriptions']
    if table_name not in allowed_tables:
        return jsonify({"error": f"テーブル '{table_name}' は存在しないか、アクセスできません"}), 404

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 基本的なレコード取得クエリ
        query = f"SELECT * FROM {table_name}"
        
        # オプションのクエリパラメータ
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        # ソート順（オプション）
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order', default='ASC').upper()
        
        # セキュリティ対策：並べ替え順のバリデーション
        if sort_order not in ['ASC', 'DESC']:
            sort_order = 'ASC'
        
        # フィルタリング（オプション）
        filters = []
        filter_values = []
        
        for key, value in request.args.items():
            # クエリパラメータのうち、特殊なもの以外をフィルタとして使用
            if key not in ['limit', 'offset', 'sort_by', 'sort_order'] and key.startswith('filter_'):
                field = key[7:]  # 'filter_' プレフィックスを削除
                filters.append(f"{field} LIKE ?")
                filter_values.append(f"%{value}%")
        
        # フィルタの適用
        if filters:
            query += " WHERE " + " AND ".join(filters)
        
        # ソートの適用
        if sort_by:
            query += f" ORDER BY {sort_by} {sort_order}"
        
        # ページネーションの適用
        query += f" LIMIT {limit} OFFSET {offset}"
        
        # クエリ実行
        cursor.execute(query, filter_values)
        records = cursor.fetchall()
        
        # レコード総数の取得（ページネーション情報用）
        count_query = f"SELECT COUNT(*) FROM {table_name}"
        if filters:
            count_query += " WHERE " + " AND ".join(filters)
        cursor.execute(count_query, filter_values)
        total_count = cursor.fetchone()[0]
        
        # レスポンスの構築
        return jsonify({
            "records": [dict(record) for record in records],
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        })
        
    except sqlite3.Error as e:
        logger.error(f"Database error during get_table_records: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error during get_table_records: {e}", exc_info=True)
        return jsonify({"error": f"レコード取得中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/export/combined', methods=['POST'])
def export_combined():
    """選択されたシーンから統合されたEDLまたはSRTファイルを生成するAPI"""
    data = request.json
    if not data or 'scene_pks' not in data or 'format' not in data:
        return jsonify({"error": "scene_pksとformatが指定されていません"}), 400

    scene_pks = data['scene_pks']
    export_format = data['format'].upper()

    if not isinstance(scene_pks, list) or not scene_pks:
        return jsonify({"error": "scene_pksはリストである必要があります"}), 400

    if export_format not in ['EDL', 'SRT']:
        return jsonify({"error": "formatはEDLまたはSRTである必要があります"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # シーンの順番を維持するためのCASE WHEN句
        case_statements = []
        for i, pk in enumerate(scene_pks):
            case_statements.append(f"WHEN s.id = {pk} THEN {i}")
        
        order_case = f"CASE {' '.join(case_statements)} ELSE 999999 END"
        placeholders = ','.join(['?' for _ in scene_pks])

        # シーン情報を取得（送信された順序を維持）
        query = f"""
            SELECT 
                s.id as scene_pk, s.video_id, s.scene_id, 
                s.start_timecode, s.end_timecode,
                v.filename as video_filename,
                v.timecode_offset,
                v.duration_seconds
            FROM scenes s
            JOIN videos v ON s.video_id = v.id
            WHERE s.id IN ({placeholders})
            ORDER BY {order_case}
        """
        
        logger.info(f"Generated SQL: {query}")
        logger.info(f"With parameters: {scene_pks}")
        
        cursor.execute(query, scene_pks)
        scenes = cursor.fetchall()
        
        if not scenes:
            return jsonify({"error": "指定されたシーンが見つかりません"}), 404

        # SRT生成用に字幕データも取得
        transcriptions = []
        if export_format == 'SRT':
            # 関連する字幕データの取得
            scene_pks_str = ','.join([str(scene['scene_pk']) for scene in scenes])
            trans_query = f"""
                SELECT 
                    t.id as trans_id, t.scene_id, t.start_timecode, t.end_timecode, 
                    t.transcription, s.video_id
                FROM transcriptions t
                JOIN scenes s ON t.scene_id = s.id
                WHERE t.scene_id IN ({scene_pks_str}) AND t.transcription IS NOT NULL AND t.transcription != ''
                ORDER BY t.scene_id, t.start_timecode
            """
            cursor.execute(trans_query)
            transcriptions = cursor.fetchall()

        # レコードタイムコードの計算用変数
        scene_record_times = {}  # シーンIDをキーとするレコードタイムコード情報
        edl_frame_rate = 60.0
        source_frame_rate = 60.0
        record_start_seconds = 0.0
        epsilon = 1e-9  # 浮動小数点比較用の微小値
        edl_content = "TITLE: Video Preprocessing Export\n"
        edl_content += "FCM: NON-DROP FRAME\n\n"

        # 各シーンに対してEDL行を生成
        for i, scene in enumerate(scenes):
            event_num = f"{i + 1:03d}"
            reel_name = os.path.splitext(scene['video_filename'])[0][:8].upper()
            track_type = "V"
            edit_type = "C"
            scene_pk = scene['scene_pk']

            # タイムコードオフセットを秒に変換
            offset_sec = timecode_to_seconds(scene['timecode_offset'], source_frame_rate) if scene['timecode_offset'] else 0.0
            
            # シーン開始・終了タイムコードを秒に変換
            source_start_sec = timecode_to_seconds(scene['start_timecode'], source_frame_rate)
            source_end_sec = timecode_to_seconds(scene['end_timecode'], source_frame_rate)

            # ソースタイムコードにオフセットを適用
            adjusted_start_sec = source_start_sec + offset_sec
            adjusted_end_sec = source_end_sec + offset_sec

            # クリップの終了点を制限
            clip_end_sec = None
            if scene['duration_seconds'] is not None:
                # 動画の終了時間（最後のフレームの終わり = 次のフレームの始まり）
                duration_sec = float(scene['duration_seconds'])
                clip_end_sec = offset_sec + duration_sec

            # adjusted_end_sec が clip_end_sec を超えないようにする
            # 浮動小数点誤差を考慮して比較し、超えている場合は厳密にクリップ
            if clip_end_sec is not None and adjusted_end_sec > clip_end_sec + epsilon:
                logger.warning(f"[EDL Clip] Scene PK {scene_pk}: adjusted_end_sec ({adjusted_end_sec}) exceeded clip_end_sec ({clip_end_sec}). Clipping.")
                adjusted_end_sec = clip_end_sec

            # 継続時間を計算し、最小デュレーションを保証
            source_duration_sec = max(0.0, adjusted_end_sec - adjusted_start_sec)
            min_duration = 1.0 / edl_frame_rate  # EDLのフレームレート基準
            if source_duration_sec < min_duration - epsilon:
                adjusted_end_sec = adjusted_start_sec + min_duration
                # 再度クリップが必要か確認
                if clip_end_sec is not None:
                    adjusted_end_sec = min(adjusted_end_sec, clip_end_sec)
                source_duration_sec = max(0.0, adjusted_end_sec - adjusted_start_sec)  # 再計算

            # EDL用タイムコードに変換
            source_in_tc = seconds_to_edl_timecode(adjusted_start_sec, edl_frame_rate)
            
            # OUT点計算: adjusted_end_sec が clip_end_sec とほぼ同じ場合、丸め誤差でフレームが増えるのを防ぐ
            out_sec_for_tc = adjusted_end_sec
            if clip_end_sec is not None and abs(adjusted_end_sec - clip_end_sec) < epsilon:
                # ほぼクリップの終了点の場合、わずかに小さい値を渡して round() の影響を避ける
                out_sec_for_tc = adjusted_end_sec - epsilon
                logger.debug(f"[EDL TC Adjust] Scene PK {scene_pk}: Adjusted out_sec_for_tc to {out_sec_for_tc} due to proximity to clip_end_sec.")
            elif adjusted_end_sec < epsilon:  # 0秒クリップの場合
                out_sec_for_tc = 0.0  # 念のため0にする

            source_out_tc = seconds_to_edl_timecode(out_sec_for_tc, edl_frame_rate)

            # レコードタイムコードを計算
            record_in_sec = record_start_seconds
            record_out_sec = record_start_seconds + source_duration_sec
            record_in_tc = seconds_to_edl_timecode(record_in_sec, edl_frame_rate)
            record_out_tc = seconds_to_edl_timecode(record_out_sec, edl_frame_rate)

            # シーンのレコード時間情報を保存（SRT生成用）
            scene_record_times[scene_pk] = {
                'record_in': record_in_sec,
                'record_out': record_out_sec,
                'source_start': source_start_sec  # オフセット適用前の開始秒数
            }

            # --- デバッグログ追加 ---
            logger.info(f"[EDL Export] Scene PK: {scene_pk}, Video: {scene['video_filename']}")
            logger.info(f"  Offset TC: {scene['timecode_offset']}, Offset Sec: {offset_sec:.5f}")
            logger.info(f"  Scene Start TC: {scene['start_timecode']}, Scene End TC: {scene['end_timecode']}")
            logger.info(f"  Source Start Sec (orig): {source_start_sec:.5f}, Source End Sec (orig): {source_end_sec:.5f}")
            logger.info(f"  Duration Sec (DB): {duration_sec if 'duration_sec' in locals() else None}")
            logger.info(f"  Clip End Sec (calc): {clip_end_sec}")
            logger.info(f"  Adjusted Start Sec (final): {adjusted_start_sec:.5f}")
            logger.info(f"  Adjusted End Sec (final): {adjusted_end_sec:.5f}")
            logger.info(f"  Out Sec for TC Conv: {out_sec_for_tc:.5f}")
            logger.info(f"  Source Duration Sec (final): {source_duration_sec:.5f}")
            logger.info(f"  Source IN TC (EDL): {source_in_tc}, Source OUT TC (EDL): {source_out_tc}")
            logger.info(f"  Record IN TC (EDL): {record_in_tc}, Record OUT TC (EDL): {record_out_tc}")

            # EDL行を生成
            edl_content += f"{event_num}  {reel_name:<8} {track_type}     {edit_type}        {source_in_tc} {source_out_tc} {record_in_tc} {record_out_tc}\n"
            edl_content += f"* FROM CLIP NAME: {scene['video_filename']}\n\n"

            record_start_seconds = record_out_sec  # 次のレコード開始位置を更新

        # EDLファイルを返す
        if export_format == 'EDL':
            edl_bytes = edl_content.encode('utf-8')
            return send_file(
                io.BytesIO(edl_bytes),
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name='export.edl'
            )

        # SRTファイルを生成
        if export_format == 'SRT':
            srt_content = ""
            # シーンIDでグループ化された字幕を取得
            transcriptions_by_scene = {}
            for trans in transcriptions:
                scene_id = trans['scene_id']
                if scene_id not in transcriptions_by_scene:
                    transcriptions_by_scene[scene_id] = []
                transcriptions_by_scene[scene_id].append(trans)

            # EDLのイベント順序（scene_pks）に合わせてSRTエントリを生成
            srt_idx = 1
            for scene_pk, time_info in scene_record_times.items():
                if scene_pk in transcriptions_by_scene:
                    scene_trans = transcriptions_by_scene[scene_pk]
                    
                    for trans in scene_trans:
                        # 字幕の元のタイムコードを秒数に変換
                        trans_start_sec = timecode_to_seconds(trans['start_timecode'], source_frame_rate)
                        trans_end_sec = timecode_to_seconds(trans['end_timecode'], source_frame_rate)
                        
                        # --- SRT デバッグログ ---
                        logger.debug(f"[SRT Calc] Scene PK: {scene_pk}, Trans ID: {trans['trans_id']}")
                        logger.debug(f"  Trans TC: {trans['start_timecode']} -> {trans['end_timecode']}")
                        logger.debug(f"  Trans Sec (orig): {trans_start_sec:.5f} -> {trans_end_sec:.5f}")
                        logger.debug(f"  Scene Source Start Sec: {time_info['source_start']:.5f}")
                        logger.debug(f"  Scene Record IN/OUT: {time_info['record_in']:.5f} -> {time_info['record_out']:.5f}")
                        
                        # シーンのソース時間内での相対位置を計算
                        scene_trans_start_rel = trans_start_sec - time_info['source_start']
                        scene_trans_end_rel = trans_end_sec - time_info['source_start']
                        
                        # シーンのレコード時間に配置
                        record_trans_start = time_info['record_in'] + scene_trans_start_rel
                        record_trans_end = time_info['record_in'] + scene_trans_end_rel
                        
                        logger.debug(f"  Record Trans Sec (raw): {record_trans_start:.5f} -> {record_trans_end:.5f}")

                        # シーンのレコード範囲内に収まるようにクリップ
                        # epsilon を使って比較
                        record_trans_start = max(time_info['record_in'] - epsilon, record_trans_start)
                        record_trans_end = min(time_info['record_out'] + epsilon, record_trans_end)
                        # 再度、シーンの範囲内に厳密に収める
                        record_trans_start = max(time_info['record_in'], record_trans_start)
                        record_trans_end = min(time_info['record_out'], record_trans_end)
                        
                        # 開始時間と終了時間が逆転しないように、また最小デュレーション（1フレーム）を保証
                        min_srt_duration = 1.0 / edl_frame_rate  # EDLと同じフレームレート基準
                        if record_trans_end < record_trans_start + min_srt_duration - epsilon:
                            record_trans_end = record_trans_start + min_srt_duration
                            # シーンの終了時間を超えないように再調整
                            if record_trans_end > time_info['record_out']:
                                # シーン終了に近すぎる場合、開始時間を調整
                                if time_info['record_out'] - time_info['record_in'] > min_srt_duration:
                                    record_trans_start = time_info['record_out'] - min_srt_duration
                                    record_trans_end = time_info['record_out']
                                else:
                                    # シーン自体が短すぎる場合は中央に配置
                                    middle = (time_info['record_in'] + time_info['record_out']) / 2
                                    half_duration = min_srt_duration / 2
                                    record_trans_start = middle - half_duration
                                    record_trans_end = middle + half_duration
                                    # それでもシーン範囲内に確実に収める
                                    record_trans_start = max(time_info['record_in'], record_trans_start)
                                    record_trans_end = min(time_info['record_out'], record_trans_end)
                        
                        # SRT形式のタイムコードに変換
                        logger.debug(f"  Record Trans Sec (clipped): {record_trans_start:.5f} -> {record_trans_end:.5f}")

                        start_srt = seconds_to_srt_timecode(record_trans_start)
                        end_srt = seconds_to_srt_timecode(record_trans_end)
                        
                        # SRTエントリを追加
                        text = trans['transcription'] if trans['transcription'] else ""
                        srt_content += f"{srt_idx}\n"
                        srt_content += f"{start_srt} --> {end_srt}\n"
                        logger.debug(f"  SRT Output TC: {start_srt} --> {end_srt}")
                        srt_content += f"{text}\n\n"
                        
                        srt_idx += 1

            # SRTファイルを返す
            srt_bytes = srt_content.encode('utf-8')
            return send_file(
                io.BytesIO(srt_bytes),
                mimetype='application/x-subrip',
                as_attachment=True,
                download_name='export.srt'
            )

    except sqlite3.Error as e:
        logger.error(f"Database error during combined export: {e}")
        return jsonify({"error": f"データベースエラー: {str(e)}"}), 500
    except ValueError as e:
        logger.error(f"Value error during combined export: {e}")
        return jsonify({"error": f"値エラー: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error during combined export: {e}", exc_info=True)
        return jsonify({"error": f"エクスポート中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

# --- メイン実行部分 ---
def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='Flask 動画ビューアー サーバー')
    parser.add_argument('--base-folder', required=True,
                      help='動画ファイルやキャプチャフォルダが格納されている基点フォルダのパス')
    parser.add_argument('--host', default='0.0.0.0',
                      help='サーバーがリッスンするホストアドレス (デフォルト: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                      help='サーバーがリッスンするポート番号 (デフォルト: 5000)')
    parser.add_argument('--db', default='video_data.db',
                      help='使用するSQLiteデータベースファイルのパス (デフォルト: video_data.db)')

    args = parser.parse_args()

    global DATABASE
    DATABASE = args.db

    video_base_folder_abs = os.path.abspath(args.base_folder)
    if not os.path.isdir(video_base_folder_abs):
        logger.error(f"指定された基点フォルダが見つからないか、フォルダではありません: {video_base_folder_abs}")
        exit(1)

    app.config['VIDEO_BASE_FOLDER'] = video_base_folder_abs

    # staticフォルダやindex.htmlの存在チェックは削除 (Flaskがデフォルトで処理)
    # if not os.path.exists('static') or not os.path.exists('static/index.html'):
    #     logger.warning("'static' フォルダ、または 'static/index.html' が見つかりません。")
    #     logger.warning("フロントエンドファイルが正しく配置されているか確認してください。")

    logger.info(f"データベースファイル: {os.path.abspath(DATABASE)}")
    logger.info(f"動画・サムネイル基点フォルダ: {app.config['VIDEO_BASE_FOLDER']}")
    logger.info(f"サーバーを http://{args.host}:{args.port} で起動します")

    # debug=True は開発時のみ推奨。本番環境ではFalseにするか、外部設定で制御。
    app.run(debug=True, host=args.host, port=args.port)

if __name__ == "__main__":
    main()

