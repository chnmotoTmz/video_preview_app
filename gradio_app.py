import gradio as gr
import pandas as pd
import requests
import os
import math
import json
from datetime import datetime

# APIのベースURL
API_BASE_URL = "http://localhost:5000/api"

# タイムコード変換ヘルパー関数
def timecode_to_seconds(timecode):
    if not timecode or not isinstance(timecode, str):
        return 0
    parts = timecode.split(':')
    if len(parts) != 4:
        print(f"Warning: Invalid timecode format: {timecode}")
        return 0
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        frames = int(parts[3])
        frame_rate = 30
        return hours * 3600 + minutes * 60 + seconds + frames / frame_rate
    except (ValueError, IndexError) as e:
        print(f"Error parsing timecode '{timecode}': {e}")
        return 0

def seconds_to_timecode(total_seconds):
    if total_seconds is None or total_seconds < 0:
        return "00:00:00:00"
    frame_rate = 30
    total_seconds = max(0, total_seconds)
    total_frames = int(round(total_seconds * frame_rate))
    frames = total_frames % frame_rate
    total_seconds_int = total_frames // frame_rate
    seconds = total_seconds_int % 60
    total_minutes = total_seconds_int // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

# データ取得関数
def get_videos():
    try:
        response = requests.get(f"{API_BASE_URL}/videos")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"APIリクエストエラー (動画リスト取得): {e}")
        return []
    except Exception as e:
        print(f"動画リストの処理中にエラーが発生しました: {e}")
        return []

def get_combined_data(video_id):
    if not video_id:
        print("get_combined_data called with no video_id")
        return pd.DataFrame()
    try:
        url = f"{API_BASE_URL}/combined_data/{video_id}"
        print(f"Fetching combined data from: {url}")
        response = requests.get(url, timeout=10)
        print(f"API Response Status Code: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"Received data type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
        
        if isinstance(data, list) and data:
            df = pd.DataFrame(data)
            required_cols = ['transcription_id', 'scene_pk', 'scene_num', 'scene_start', 'transcription_start']
            if not all(col in df.columns for col in required_cols):
                print(f"Missing required columns: {df.columns.tolist()}")
                return pd.DataFrame()
            print(f"DataFrame created. Shape: {df.shape}")
            return df
        else:
            print("Received empty or invalid data.")
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Processing Error: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

# 画像URL生成関数
def get_thumbnail_url(scene_pk):
    if scene_pk is None or pd.isna(scene_pk):
        return None
    try:
        scene_pk_int = int(scene_pk)
        return f"{API_BASE_URL}/thumbnails/{scene_pk_int}"
    except (ValueError, TypeError):
        print(f"Warning: Invalid scene_pk for thumbnail URL: {scene_pk}")
        return None

# 動画URL生成関数
def get_video_url(video_id):
    if video_id is None:
        return None
    return f"{API_BASE_URL}/stream/{video_id}"

# 選択シーン統計の更新
def update_selected_stats(selected_ids, combined_data):
    count = len(selected_ids)
    total_duration_sec = 0

    if isinstance(combined_data, pd.DataFrame) and not combined_data.empty and selected_ids:
        try:
            # Filter the DataFrame for selected transcription IDs
            selected_rows = combined_data[combined_data['transcription_id'].isin(selected_ids)]

            # Calculate total duration based on the transcription start/end times
            if 'transcription_start' in selected_rows.columns and 'transcription_end' in selected_rows.columns:
                for _, row in selected_rows.iterrows():
                    start = timecode_to_seconds(row['transcription_start'])
                    end = timecode_to_seconds(row['transcription_end'])
                    if start is not None and end is not None and end >= start:
                        total_duration_sec += (end - start)
        except Exception as e:
            print(f"統計計算中に予期せぬエラーが発生しました: {e}")

    return count, seconds_to_timecode(total_duration_sec)

# Gradio UI構築
def create_ui():
    with gr.Blocks() as app:
        gr.Markdown("# SQLite連携 動画ビューアー")
        
        # 状態変数
        video_id_state = gr.State(None)
        video_filename_state = gr.State(None)
        selected_ids_state = gr.State(set())
        data_df_state = gr.State(pd.DataFrame())
        
        # 動画選択用データの準備
        videos = get_videos()
        video_choices = [f"{v['filename']} ({v.get('duration_seconds', 0):.1f}s)" for v in videos]
        video_ids = [v['id'] for v in videos]
        video_map = {choice: vid for choice, vid in zip(video_choices, video_ids)}
        
        with gr.Row():
            with gr.Column(scale=1):
                # サイドバーエリア
                video_dropdown = gr.Dropdown(
                    choices=["動画を選択..."] + video_choices,
                    label="動画を選択",
                    value="動画を選択...",
                    info="表示する動画を選択してください"
                )
                
                # プレビューエリア
                preview_md = gr.Markdown("### プレビュー")
                video_component = gr.Video(label="")
                scene_info = gr.Markdown(visible=False)
                
                # エクスポートエリア
                export_md = gr.Markdown("### エクスポート")
                selected_stats = gr.Markdown("選択: 0 件 / 合計時間: 00:00:00:00")
                with gr.Row():
                    edl_btn = gr.Button("EDLエクスポート (未実装)")
                    srt_btn = gr.Button("SRTエクスポート (未実装)")
            
            with gr.Column(scale=2):
                # メインコンテンツエリア
                title = gr.Markdown("### 動画が選択されていません")
                
                with gr.Tabs():
                    with gr.TabItem("統合ビュー"):
                        # データテーブル
                        data_display = gr.DataFrame(interactive=False)
                        
                        # 操作ボタン
                        with gr.Row():
                            select_all_btn = gr.Button("すべて選択")
                            deselect_all_btn = gr.Button("すべて解除")
                            toggle_select_btn = gr.Button("選択を反転")
                        
                        # シーン再生エリア
                        gr.Markdown("### シーン再生")
                        scene_buttons_container = gr.Markdown("シーンを選択してください")
                        
                    with gr.TabItem("エクスポート"):
                        gr.Markdown("### エクスポート機能")
                        gr.Markdown("エクスポート機能の詳細設定はこちらで行います。")
                        
                        with gr.Row():
                            export_edl = gr.Button("EDLエクスポート (未実装)")
                            export_srt = gr.Button("SRTエクスポート (未実装)")
        
        # イベントハンドラー
        def on_video_select(video_choice):
            if video_choice == "動画を選択...":
                return {
                    title: "### 動画が選択されていません",
                    data_display: None,
                    scene_buttons_container: "シーンを選択してください",
                    selected_stats: "選択: 0 件 / 合計時間: 00:00:00:00",
                    video_component: None,
                    scene_info: gr.update(visible=False, value=""),
                    video_id_state: None,
                    video_filename_state: None,
                    selected_ids_state: set(),
                    data_df_state: pd.DataFrame()
                }
            
            # 状態の更新
            video_id = video_map[video_choice]
            video_filename = video_choice.split(' (')[0]
            
            # データの取得
            df = get_combined_data(video_id)
            
            if not df.empty:
                # 表示用データフレームの準備
                display_df = df[[
                    'transcription_id', 'video_filename', 'scene_num', 'scene_start', 
                    'scene_end', 'scene_description', 'transcription_start', 
                    'transcription_end', 'dialogue', 'scene_pk'
                ]].copy()
                
                # 選択状態列の追加
                display_df['選択'] = ""
                
                # シーン一覧表示用テキスト
                unique_scenes = df[['scene_pk', 'scene_num', 'scene_start', 'scene_end']].drop_duplicates()
                scene_text = "### シーン一覧\n\n"
                for _, scene in unique_scenes.iterrows():
                    if pd.notna(scene['scene_pk']) and pd.notna(scene['scene_num']):
                        scene_text += f"* シーン {scene['scene_num']}: {scene['scene_start']} - {scene['scene_end']}\n"
                
                return {
                    title: f"### 統合ビュー: {video_filename}",
                    data_display: display_df,
                    scene_buttons_container: scene_text,
                    selected_stats: "選択: 0 件 / 合計時間: 00:00:00:00",
                    video_component: None,
                    scene_info: gr.update(visible=False, value=""),
                    video_id_state: video_id,
                    video_filename_state: video_filename,
                    selected_ids_state: set(),
                    data_df_state: df
                }
            else:
                return {
                    title: f"### 統合ビュー: {video_filename} (データなし)",
                    data_display: None,
                    scene_buttons_container: "表示するシーンデータがありません。",
                    selected_stats: "選択: 0 件 / 合計時間: 00:00:00:00",
                    video_component: None,
                    scene_info: gr.update(visible=False, value=""),
                    video_id_state: video_id,
                    video_filename_state: video_filename,
                    selected_ids_state: set(),
                    data_df_state: pd.DataFrame()
                }
        
        def play_scene(scene_pk, video_id, df):
            if scene_pk is None or video_id is None or df.empty:
                return None, gr.update(visible=False, value="")
            
            try:
                scene_rows = df[df['scene_pk'] == scene_pk]
                if scene_rows.empty:
                    return None, gr.update(visible=False, value="")
                
                scene_info_row = scene_rows.iloc[0]
                scene_num = scene_info_row.get('scene_num', '-')
                start_timecode = scene_info_row.get('scene_start', '00:00:00:00')
                end_timecode = scene_info_row.get('scene_end', '00:00:00:00')
                description = scene_info_row.get('scene_description', '-')
                
                # 情報テキストの生成
                info_text = f"""
                ### シーン情報
                
                **シーン番号:** {scene_num}  
                **開始:** {start_timecode}  
                **終了:** {end_timecode}  
                **説明:** {description}
                """
                
                # 動画URLの取得
                video_url = get_video_url(video_id)
                return video_url, gr.update(visible=True, value=info_text)
            except Exception as e:
                print(f"シーン再生エラー: {e}")
                return None, gr.update(visible=False, value=f"エラー: {e}")
        
        def select_all_items(df):
            if df.empty:
                return "選択: 0 件 / 合計時間: 00:00:00:00", set()
            
            selected_ids = set(df['transcription_id'].tolist())
            count, duration = update_selected_stats(selected_ids, df)
            return f"選択: {count} 件 / 合計時間: {duration}", selected_ids
        
        def deselect_all_items():
            return "選択: 0 件 / 合計時間: 00:00:00:00", set()
        
        def toggle_select_items(selected_ids, df):
            if df.empty:
                return "選択: 0 件 / 合計時間: 00:00:00:00", set()
            
            all_ids = set(df['transcription_id'].tolist())
            new_selection = all_ids - selected_ids
            count, duration = update_selected_stats(new_selection, df)
            return f"選択: {count} 件 / 合計時間: {duration}", new_selection
        
        # イベントハンドラーの接続
        video_dropdown.change(
            on_video_select,
            inputs=[video_dropdown],
            outputs=[
                title, data_display, scene_buttons_container, selected_stats, 
                video_component, scene_info, video_id_state, video_filename_state, 
                selected_ids_state, data_df_state
            ]
        )
        
        # シーン再生ボタンは、シーンデータがロードされた後にだけ表示
        # Gradioでは動的にボタンを生成できないため、外部からリクエストを受け付ける
        def on_scene_play(scene_pk_str, video_id, df):
            try:
                scene_pk = int(scene_pk_str)
                return play_scene(scene_pk, video_id, df)
            except:
                return None, gr.update(visible=False, value="不正なシーンPKです")
        
        # 選択操作ボタンのハンドラー接続
        select_all_btn.click(
            select_all_items,
            inputs=[data_df_state],
            outputs=[selected_stats, selected_ids_state]
        )
        
        deselect_all_btn.click(
            deselect_all_items,
            inputs=[],
            outputs=[selected_stats, selected_ids_state]
        )
        
        toggle_select_btn.click(
            toggle_select_items,
            inputs=[selected_ids_state, data_df_state],
            outputs=[selected_stats, selected_ids_state]
        )
        
    return app

if __name__ == "__main__":
    app = create_ui()
    app.launch(inbrowser=True) 