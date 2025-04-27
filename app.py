from flask import Flask, jsonify, request, send_file, Response, render_template
import sqlite3
import os
import json
import tempfile
import mimetypes
from flask_cors import CORS
from pathlib import Path
import re
import argparse

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)  # クロスオリジンリクエストを許可

DATABASE = 'video_data.db'  # デフォルトのデータベースパス (引数で上書き可能)
# VIDEO_BASE_FOLDER = 'E:/ESD-EXS/O-YAMA-GOPRO' # ハードコードされたパスを削除


def get_db_connection():
    """データベース接続を取得"""
    # グローバル変数 DATABASE を使用
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_path(relative_path):
    """データベース内の相対パスを絶対パスに解決（設定された基準フォルダ基準）"""
    # 設定から基準フォルダパスを取得
    video_base_folder = app.config.get('VIDEO_BASE_FOLDER')
    if not video_base_folder:
        print(f"Error: VIDEO_BASE_FOLDER is not configured in app.config")
        # 実行時引数で必須にしているので通常ここには来ないはずだが念のため
        raise ValueError("VIDEO_BASE_FOLDER is not configured.")

    # パスの正規化（バックスラッシュをスラッシュに）
    normalized_relative_path = Path(relative_path).as_posix()
    # video_base_folder と結合
    absolute_path = os.path.abspath(os.path.join(video_base_folder, normalized_relative_path))
    # print(f"Resolving path: '{relative_path}' (base: '{video_base_folder}') -> '{absolute_path}'") # 必要に応じてデバッグ出力
    return absolute_path

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

    if video is None:
        conn.close()
        return jsonify({"error": "Video not found"}), 404

    result = dict(video)
    conn.close()
    return jsonify(result)

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

# サムネイル取得エンドポイントを修正
@app.route('/api/thumbnails/<int:scene_pk>')
def get_thumbnail_by_scene_pk(scene_pk):
    """シーンの主キー(id)に基づいてサムネイル画像を取得"""
    conn = get_db_connection()
    # scenes テーブルの主キー 'id' で検索
    scene = conn.execute('SELECT thumbnail_path FROM scenes WHERE id = ?', (scene_pk,)).fetchone()
    conn.close()

    if scene is None or not scene['thumbnail_path']:
        try:
            # placeholder.jpg を static フォルダから提供
            placeholder_path = os.path.join(app.static_folder, 'placeholder.jpg')
            if os.path.exists(placeholder_path):
                 return send_file(placeholder_path, mimetype='image/jpeg')
            else:
                 print("Error: placeholder.jpg not found in static folder.")
                 return jsonify({"error": "Thumbnail path not found in DB and placeholder.jpg missing"}), 404
        except Exception as e:
             print(f"Error sending placeholder image: {e}")
             return jsonify({"error": "Error serving placeholder image"}), 500

    thumbnail_rel_path = scene['thumbnail_path']
    try:
        thumbnail_abs_path = resolve_path(thumbnail_rel_path) # resolve_path を使用
    except ValueError as e: # resolve_path で VIDEO_BASE_FOLDER が設定されていない場合
        print(e)
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Error resolving thumbnail path: {e}")
        return jsonify({"error": "Error resolving thumbnail path"}), 500

    if os.path.exists(thumbnail_abs_path):
        return send_file(thumbnail_abs_path, mimetype='image/jpeg')
    else:
        print(f"Thumbnail file not found at resolved path: {thumbnail_abs_path} (relative: {thumbnail_rel_path})")
        # プレースホルダーを再度試みる
        try:
            placeholder_path = os.path.join(app.static_folder, 'placeholder.jpg')
            if os.path.exists(placeholder_path):
                 return send_file(placeholder_path, mimetype='image/jpeg')
            else:
                 print("Error: placeholder.jpg not found in static folder (fallback).")
                 return jsonify({"error": f"Thumbnail file not found at {thumbnail_abs_path} and placeholder.jpg missing"}), 404
        except Exception as e:
             print(f"Error sending placeholder image (fallback): {e}")
             return jsonify({"error": "Error serving placeholder image"}), 500


@app.route('/api/stream/<int:video_id>')
def stream_video(video_id):
    """動画ファイルをストリーミング"""
    conn = get_db_connection()
    video = conn.execute('SELECT filepath FROM videos WHERE id = ?', (video_id,)).fetchone()
    conn.close()

    if video is None:
        return jsonify({"error": "Video not found in DB"}), 404

    video_rel_path = video['filepath']
    video_abs_path = resolve_path(video_rel_path)

    # 動画ファイルが存在するか確認
    if not os.path.exists(video_abs_path):
        print(f"Video file not found at resolved path: {video_abs_path} (relative: {video_rel_path})")
        return jsonify({"error": f"Video file not found at {video_abs_path}"}), 404

    # 範囲リクエストのサポート
    range_header = request.headers.get('Range', None)
    size = os.path.getsize(video_abs_path)

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
            byte2 = size - 1

        length = byte2 - byte1 + 1
        if length < 0 or byte1 >= size or byte2 >=size:
             return Response("Requested Range Not Satisfiable", status=416)

        resp = Response(
            generate_stream(video_abs_path, byte1, length),
            status=206,
            mimetype='video/mp4',
            direct_passthrough=True
        )

        resp.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{size}')
        resp.headers.add('Accept-Ranges', 'bytes')
        resp.headers.add('Content-Length', str(length))
        return resp
    else:
        # 通常のファイル送信 (ストリーミングなし、またはRangeヘッダなしの場合)
        def generate_full():
            with open(video_abs_path, 'rb') as f:
                yield from f
        return Response(generate_full(), mimetype='video/mp4')
        # send_file は大きなファイルには向かない可能性がある
        # return send_file(
        #     video_abs_path,
        #     mimetype='video/mp4',
        #     as_attachment=False
        # )

def generate_stream(video_path, start, length):
    """動画ファイルの一部をチャンク単位でストリーミング"""
    chunk_size = 1024 * 1024  # 1MB
    bytes_sent = 0
    with open(video_path, 'rb') as f:
        f.seek(start)
        while bytes_sent < length:
            read_size = min(chunk_size, length - bytes_sent)
            chunk = f.read(read_size)
            if not chunk:
                break
            yield chunk
            bytes_sent += len(chunk)

@app.route('/api/audio/<int:video_id>')
def stream_audio(video_id):
    """音声ファイルをストリーミング"""
    conn = get_db_connection()
    audio = conn.execute(
        'SELECT a.filepath FROM audio_files a JOIN videos v ON a.video_id = v.id WHERE v.id = ?',
        (video_id,)
    ).fetchone()
    conn.close()

    if audio is None:
        return jsonify({"error": "Audio not found in DB"}), 404

    audio_rel_path = audio['filepath']
    audio_abs_path = resolve_path(audio_rel_path)

    # 音声ファイルが存在するか確認
    if not os.path.exists(audio_abs_path):
         print(f"Audio file not found at resolved path: {audio_abs_path} (relative: {audio_rel_path})")
         return jsonify({"error": f"Audio file not found at {audio_abs_path}"}), 404

    # WAVファイルは通常小さいのでsend_fileでも問題ない場合が多い
    return send_file(
        audio_abs_path,
        mimetype='audio/wav',
        as_attachment=False
    )

@app.route('/api/export/edl', methods=['POST'])
def export_edl():
    """EDLファイル（CMX3600形式）を生成してダウンロード"""
    data = request.json
    if not data or 'scenes' not in data or 'videoId' not in data:
        return jsonify({"error": "Invalid data"}), 400

    scenes_data = data['scenes'] # JSから渡されるシーンオブジェクトの配列
    video_id = data['videoId']

    conn = get_db_connection()
    video = conn.execute('SELECT filename, timecode_offset FROM videos WHERE id = ?', (video_id,)).fetchone()
    conn.close()

    if video is None:
        return jsonify({"error": "Video not found"}), 404

    filename = video['filename'] or "UNKNOWN_VIDEO"
    # timecode_offset = video['timecode_offset'] or "00:00:00:00"

    # --- EDLリール名の修正 ---
    # ファイル名から拡張子を除き、大文字にして先頭8文字を取得 (8文字未満はスペースで埋める)
    reel_name = os.path.splitext(filename)[0].upper()[:8].ljust(8)
    # --- ここまで修正 ---

    # EDLファイルを生成
    edl_content = f"TITLE: {os.path.splitext(filename)[0]}_EDL_EXPORT\nFCM: NON-DROP FRAME\n\n"

    # JSから渡されたシーンデータ（選択済み）を使う
    for i, scene_info in enumerate(scenes_data, 1):
        start_tc = scene_info.get('start_timecode', '00:00:00:00')
        end_tc = scene_info.get('end_timecode', '00:00:00:00')
        scene_id_num = scene_info.get('scene_id', '??')
        description = scene_info.get('description', '')
        
        # CMX3600 format (adjust record timecodes if needed, currently same as source)
        # --- EDLリール名を使用するように修正 ---
        edl_content += f"{i:03d}  {reel_name} V     C        {start_tc} {end_tc} {start_tc} {end_tc}\n"
        # --- ここまで修正 ---
        edl_content += f"* FROM CLIP NAME: {filename} SCENE {scene_id_num}\n"
        if description:
            edl_content += f"* COMMENT: {description}\n"
        edl_content += "\n"

    # 一時ファイルを作成して送信
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.edl', mode='w', encoding='utf-8') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(edl_content)

        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f"{os.path.splitext(filename)[0]}.edl",
            mimetype='text/plain'
        )
    finally:
        # 一時ファイルを削除 (send_fileの後でもアクセス可能な場合があるため)
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@app.route('/api/export/srt', methods=['POST'])
def export_srt():
    """SRTファイル（SubRip形式）を生成してダウンロード"""
    data = request.json
    # JSからは選択されたシーンIDに関連する文字起こしデータを送ってもらう想定
    if not data or 'transcriptions' not in data or 'videoId' not in data:
        return jsonify({"error": "Invalid data"}), 400

    transcriptions_data = data['transcriptions'] # JSから渡される文字起こしオブジェクトの配列
    video_id = data['videoId']

    conn = get_db_connection()
    video = conn.execute('SELECT filename FROM videos WHERE id = ?', (video_id,)).fetchone()
    conn.close()

    if video is None:
        return jsonify({"error": "Video not found"}), 404

    filename = video['filename'] or "UNKNOWN_VIDEO"

    # SRTファイルを生成
    srt_content = ""

    # JSから渡された文字起こしデータ（選択されたシーンのもの）を使う
    for i, trans_info in enumerate(transcriptions_data, 1):
        start_tc_srt = timecode_to_srt_format(trans_info.get('start_timecode'))
        end_tc_srt = timecode_to_srt_format(trans_info.get('end_timecode'))
        text = trans_info.get('transcription', '')

        srt_content += f"{i}\n"
        srt_content += f"{start_tc_srt} --> {end_tc_srt}\n"
        srt_content += f"{text}\n\n"

    # 一時ファイルを作成して送信
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.srt', mode='w', encoding='utf-8') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(srt_content)

        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name=f"{os.path.splitext(filename)[0]}.srt",
            mimetype='text/plain'
        )
    except Exception as e:
        print(f"Error generating SRT: {e}")
        return jsonify({"error": "Failed to generate SRT file"}), 500

def timecode_to_srt_format(timecode):
    """タイムコード（HH:MM:SS:FF）をSRT形式（HH:MM:SS,mmm）に変換"""
    if not timecode:
        return "00:00:00,000"

    match = re.match(r'(\d+):(\d+):(\d+):(\d+)', timecode)
    if not match:
        print(f"Warning: Invalid timecode format for SRT conversion: {timecode}")
        return "00:00:00,000"

    try:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        frames = int(match.group(4))

        # フレームをミリ秒に変換（30fpsと仮定 - create_database.pyと合わせる）
        # Note: 厳密には29.97fpsの場合もあるが、簡略化のため30で計算
        frame_rate = 30
        milliseconds = int((frames / frame_rate) * 1000)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    except ValueError:
        print(f"Warning: Could not parse timecode components: {timecode}")
        return "00:00:00,000"

# --- ★★★ 新しいエンドポイント (結合データ取得) ★★★ ---
@app.route('/api/combined_data/<int:video_id>', methods=['GET'])
def get_combined_data_endpoint(video_id):
    """動画、シーン、文字起こしを結合したデータを返す"""
    conn = None
    try:
        conn = get_db_connection()
        # SQLクエリ: videos, scenes, transcriptions を結合（LEFT JOINを使用）
        query = """
        SELECT
            t.id AS transcription_id,
            v.filename AS video_filename,
            s.scene_id AS scene_num,
            s.start_timecode AS scene_start,
            s.end_timecode AS scene_end,
            s.description AS scene_description,
            s.thumbnail_path AS scene_thumbnail_path,
            s.scene_good_reason,
            s.scene_bad_reason,
            s.scene_evaluation_tag,
            t.start_timecode AS transcription_start,
            t.end_timecode AS transcription_end,
            t.transcription AS dialogue,
            t.transcription_good_reason,
            t.transcription_bad_reason,
            s.id AS scene_pk -- scenesテーブルの主キー
        FROM scenes s
        LEFT JOIN transcriptions t ON s.id = t.scene_id
        JOIN videos v ON s.video_id = v.id
        WHERE s.video_id = ?
        ORDER BY s.scene_id, t.start_timecode -- シーン番号、文字起こし開始時間でソート
        """
        cursor = conn.cursor()
        cursor.execute(query, (video_id,))
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(results)
    except sqlite3.Error as e:
        print(f"Database error fetching combined data for video_id {video_id}: {e}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Error in /api/combined_data/{video_id}: {e}")
        return jsonify({"error": f"Failed to get combined data: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/settings/base_folder', methods=['PUT'])
def update_base_folder():
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
    return jsonify({"path": app.config.get('VIDEO_BASE_FOLDER', "")})

# --- Main Execution ---

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SQLite連携動画ビューアー サーバー')
    parser.add_argument('--base-folder', required=True,
                        help='動画ファイルやキャプチャフォルダが格納されている基点フォルダのパス (例: E:/O-YAMA-GOPRO)')
    parser.add_argument('--host', default='0.0.0.0',
                        help='サーバーがリッスンするホストアドレス (デフォルト: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                        help='サーバーがリッスンするポート番号 (デフォルト: 5000)')
    parser.add_argument('--db', default='video_data.db',
                        help='使用するSQLiteデータベースファイルのパス (デフォルト: video_data.db)')

    args = parser.parse_args()

    # グローバル変数 DATABASE を更新
    DATABASE = args.db

    # 絶対パスに変換してアプリ設定に保存
    video_base_folder_abs = os.path.abspath(args.base_folder)
    if not os.path.isdir(video_base_folder_abs):
        print(f"エラー: 指定された基点フォルダが見つからないか、フォルダではありません: {video_base_folder_abs}")
        exit(1) # エラーで終了
    app.config['VIDEO_BASE_FOLDER'] = video_base_folder_abs

    # staticフォルダとindex.htmlの設定確認
    if not os.path.exists('static') or not os.path.exists('static/index.html'):
        print("警告: 'static' フォルダ、または 'static/index.html' が見つかりません。")
        print("フロントエンドファイルが正しく配置されているか確認してください。")

    print(f"データベースファイル: {os.path.abspath(DATABASE)}")
    print(f"動画・サムネイル基点フォルダ: {app.config['VIDEO_BASE_FOLDER']}")
    print(f"サーバーを http://{args.host}:{args.port} で起動します")
    app.run(debug=True, host=args.host, port=args.port) 