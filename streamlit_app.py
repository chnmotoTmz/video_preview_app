import streamlit as st
import requests
import pandas as pd
# import json # Likely unused now
import os
import base64
from io import BytesIO
from streamlit_option_menu import option_menu
import math # For safe ceiling division

# APIのベースURL
API_BASE_URL = "http://localhost:5000/api"

# ページタイトルとレイアウト設定
st.set_page_config(
    page_title="SQLite連携 動画ビューアー",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .video-preview {
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 10px;
        margin-bottom: 15px;
    }
    .scene-info {
        background-color: #f9f9f9;
        border: 1px solid #eee;
        border-radius: 4px;
        padding: 10px;
        margin-top: 10px;
    }
    .thumbnail-img {
        width: 100%;
        max-width: 200px;
        border-radius: 4px;
        border: 1px solid #ddd;
    }
    .selected-row {
        background-color: #e6f2ff !important;
    }
    .stats-box {
        background-color: #f0f0f0;
        padding: 10px;
        border-radius: 4px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'selected_combined_ids' not in st.session_state:
    st.session_state.selected_combined_ids = set()
if 'current_video_id' not in st.session_state:
    st.session_state.current_video_id = None
if 'current_video_filename' not in st.session_state:
    st.session_state.current_video_filename = None
if 'combined_data' not in st.session_state:
    st.session_state.combined_data = pd.DataFrame()
if 'current_scene_info_for_preview' not in st.session_state:
    st.session_state.current_scene_info_for_preview = None
if 'show_video_preview' not in st.session_state:
    st.session_state.show_video_preview = False
if 'playing_scene_pk' not in st.session_state: # Track scene primary key for playback
    st.session_state.playing_scene_pk = None
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "統合ビュー"

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
@st.cache_data(ttl=300)
def get_videos():
    try:
        response = requests.get(f"{API_BASE_URL}/videos")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"APIリクエストエラー (動画リスト取得): {e}")
        return []
    except Exception as e:
        st.error(f"動画リストの処理中にエラーが発生しました: {e}")
        return []

# @st.cache_data(ttl=60) # キャッシュを一時的に無効化してテスト
def get_combined_data(video_id):
    """Fetches combined video, scene, and transcription data from the API for a given video_id."""
    if not video_id:
        print("get_combined_data called with no video_id")
        return pd.DataFrame()
    try:
        url = f"{API_BASE_URL}/combined_data/{video_id}"
        print(f"DEBUG: Fetching combined data from: {url}") # print に変更
        response = requests.get(url)
        print(f"DEBUG: API Response Status Code: {response.status_code}") # print に変更
        response.raise_for_status() # Check for HTTP errors
        data = response.json()
        print(f"DEBUG: Received data type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}") # print に変更
        if isinstance(data, list) and data:
            print(f"DEBUG: Received data sample: {data[0]}") # print に変更

        if data and isinstance(data, list): # Check if data is a non-empty list
            print(f"DEBUG: Attempting to create DataFrame from {len(data)} records.") # ここが最後のメッセージだった
            try:
                # DataFrame作成処理を try-except で囲む
                df = pd.DataFrame(data)
                print(f"DEBUG: DataFrame created successfully. Shape: {df.shape}") # ★成功した場合のログを追加
                # Basic validation after successful creation
                required_cols = ['transcription_id', 'scene_pk', 'scene_num', 'scene_start', 'transcription_start']
                if not all(col in df.columns for col in required_cols):
                    st.warning(f"作成されたDataFrameに必要な列が含まれていません。列: {df.columns.tolist()}")
                    # Return empty df or proceed cautiously
                    return pd.DataFrame() # Treat as error if columns missing
                return df
            except Exception as df_error:
                # ★エラーが発生した場合のログを追加
                print(f"!!!!!!!!!! DEBUG: DataFrame creation FAILED: {df_error} !!!!!!!!!!")
                import traceback
                traceback.print_exc() # ★詳細なスタックトレースを出力
                st.error(f"DataFrameの作成に失敗しました: {df_error}") # 画面にもエラー表示
                return pd.DataFrame() # エラー時は空のDataFrameを返す
        elif isinstance(data, list) and not data:
            print(f"Received empty list for combined data (video_id {video_id}).")
            print("DEBUG: Received empty list or non-list data. Returning empty DataFrame.") # print に変更
            return pd.DataFrame() # Return empty DataFrame for no data
        else:
            st.warning(f"APIから予期しない形式のデータが返されました (combined_data): {type(data)}")
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"APIリクエストエラー (結合データ取得 video_id={video_id}): {e}") # Keep st.error
        print(f"DEBUG: API Request Error: {e}") # print に変更
        print(f"API Request Error fetching combined data (video_id={video_id}): {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"結合データの処理中にエラーが発生しました (video_id={video_id}): {e}") # Keep st.error
        print(f"DEBUG: Processing Error: {e}") # print に変更
        print(f"Error processing combined data (video_id={video_id}): {e}")
        # Keep traceback print from previous edit
        import traceback
        print(traceback.format_exc())
        return pd.DataFrame()

# 画像URL生成関数
def get_thumbnail_url(scene_pk):
    if scene_pk is None or pd.isna(scene_pk):
         return None # Return None if scene_pk is invalid
    # Ensure scene_pk is an integer before formatting
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

# エクスポート関数
def export_edl(selected_scenes):
    if not selected_scenes or not st.session_state.current_video_id:
        st.warning("エクスポートするシーンを選択してください")
        return None
    
    selected_scene_objects = [scene for scene in st.session_state.scenes if scene['id'] in selected_scenes]
    if not selected_scene_objects:
        return None
    
    export_data = {
        "videoId": st.session_state.current_video_id,
        "scenes": selected_scene_objects
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/export/edl",
            json=export_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"EDLエクスポートに失敗しました: {e}")
        return None

def export_srt(selected_scenes):
    if not selected_scenes or not st.session_state.current_video_id:
        st.warning("エクスポートするシーンを選択してください")
        return None
    
    # 選択されたシーンに関連する字幕を取得
    selected_scene_ids = list(selected_scenes)
    selected_transcriptions = [
        trans for trans in st.session_state.transcriptions 
        if 'scene_id' in trans and trans['scene_id'] in selected_scene_ids
    ]
    
    if not selected_transcriptions:
        st.warning("選択されたシーンに関連する字幕がありません")
        return None
    
    export_data = {
        "videoId": st.session_state.current_video_id,
        "transcriptions": selected_transcriptions
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/export/srt",
            json=export_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"SRTエクスポートに失敗しました: {e}")
        return None
    
# ダウンロードリンク生成関数
def get_download_link(file_content, filename, text):
    b64 = base64.b64encode(file_content).decode()
    st.download_button(
        label=text,
        data=file_content,
        file_name=filename,
        mime='application/octet-stream'
    )

# シーン選択関数
def toggle_scene_selection(scene_id):
    if scene_id in st.session_state.selected_combined_ids:
        st.session_state.selected_combined_ids.remove(scene_id)
    else:
        st.session_state.selected_combined_ids.add(scene_id)
    st.rerun()

# 選択シーン統計の更新
def update_selected_stats():
    count = len(st.session_state.selected_combined_ids)
    total_duration = 0
    
    for scene in st.session_state.scenes:
        if scene['id'] in st.session_state.selected_combined_ids:
            start = timecode_to_seconds(scene['start_timecode'])
            end = timecode_to_seconds(scene['end_timecode'])
            if end >= start:
                total_duration += (end - start)
    
    return count, seconds_to_timecode(total_duration)

# シーン再生関数
def play_scene(scene_pk):
    if scene_pk is None or pd.isna(scene_pk):
        st.warning("無効なシーンキーが再生関数に渡されました。")
        return

    st.session_state.playing_scene_pk = scene_pk
    st.session_state.show_video_preview = True

    # Find scene info from the combined_data DataFrame using scene_pk
    combined_df = st.session_state.get('combined_data')
    st.session_state.current_scene_info_for_preview = None # Reset first

    if isinstance(combined_df, pd.DataFrame) and not combined_df.empty and 'scene_pk' in combined_df.columns:
        # Filter rows matching the scene_pk
        scene_info_rows = combined_df[combined_df['scene_pk'] == scene_pk]
        if not scene_info_rows.empty:
            # Get the first row (all rows for the same scene_pk should have the same scene info)
            scene_info_row = scene_info_rows.iloc[0]
            # Store the relevant scene information for the preview display
            st.session_state.current_scene_info_for_preview = {
                'id': scene_info_row.get('scene_pk'), # Scene Primary Key
                'scene_id': scene_info_row.get('scene_num', '-'), # Scene Sequence Number
                'start_timecode': scene_info_row.get('scene_start', '00:00:00:00'),
                'end_timecode': scene_info_row.get('scene_end', '00:00:00:00'),
                'description': scene_info_row.get('scene_description', '-'),
                'scene_evaluation_tag': scene_info_row.get('scene_evaluation_tag', '-'),
                # Add other relevant fields if needed
            }
            print(f"Preview scene info set for scene_pk: {scene_pk}")
        else:
            print(f"Warning: No scene info found in combined_data for scene_pk: {scene_pk}")
    else:
        print("Warning: combined_data is empty or missing 'scene_pk' column.")

    st.rerun() # Rerun to update the UI and show the preview

# プレビュー表示関数
def show_preview():
    st.session_state.show_video_preview = True
    st.rerun()

# プレビュー非表示関数
def hide_preview():
    st.session_state.show_video_preview = False
    st.session_state.playing_scene_pk = None
    st.session_state.current_scene_info_for_preview = None # Clear preview info
    st.rerun()

# --- 選択統計関数 (selected_combined_ids を使うように変更) ---
def update_combined_stats():
    selected_ids = st.session_state.get('selected_combined_ids', set())
    count = len(selected_ids)
    total_duration_sec = 0

    combined_data = st.session_state.get('combined_data')

    if isinstance(combined_data, pd.DataFrame) and not combined_data.empty and 'transcription_id' in combined_data.columns and selected_ids:
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
            else:
                 st.warning("統計計算に必要な時間コード列が見つかりません。")

        except KeyError as e:
            st.warning(f"統計計算エラー: 予期しない列名 {e}")
            return count, "エラー"
        except Exception as e:
            st.error(f"統計計算中に予期せぬエラーが発生しました: {e}")
            return count, "エラー"

    return count, seconds_to_timecode(total_duration_sec)

# --- データ結合関数 ---
def create_combined_data(video_filename, scenes, transcriptions):
    if not scenes or not transcriptions:
        st.warning("シーンデータまたは字幕データが空です。結合できません。")
        return pd.DataFrame()

    try:
        scenes_df = pd.DataFrame(scenes)
        transcriptions_df = pd.DataFrame(transcriptions)

        # --- Input Validation ---
        if scenes_df.empty or transcriptions_df.empty:
            st.warning("シーンデータまたは字幕データが空のDataFrameです。")
            return pd.DataFrame()

        required_scene_cols = ['id', 'scene_id', 'start_timecode', 'end_timecode']
        required_trans_cols = ['id', 'scene_id', 'start_timecode', 'end_timecode', 'transcription']

        if not all(col in scenes_df.columns for col in required_scene_cols):
            st.error(f"シーンデータの必須列が不足しています: {required_scene_cols}")
            return pd.DataFrame()
        if not all(col in transcriptions_df.columns for col in required_trans_cols):
            st.error(f"字幕データの必須列が不足しています: {required_trans_cols}")
            return pd.DataFrame()

        # --- Data Cleaning & Preparation ---
        # Drop rows where the join key (scene_id in transcriptions) is missing
        transcriptions_df = transcriptions_df.dropna(subset=['scene_id'])
        if transcriptions_df.empty:
            st.info("有効な scene_id を持つ字幕データがありません。")
            return pd.DataFrame()

        # Convert join keys to appropriate types (ensure scene_id in transcriptions matches id in scenes)
        try:
            # Attempt to convert scene_id in transcriptions to match the type of id in scenes
            # Typically, database IDs are integers.
            scenes_df['id'] = scenes_df['id'].astype(int)
            transcriptions_df['scene_id'] = transcriptions_df['scene_id'].astype(int)
        except (ValueError, TypeError) as e:
            st.error(f"シーンIDまたは文字起こしIDの型変換エラー: {e}. データを確認してください。")
            return pd.DataFrame()

        # --- Merge Data ---
        combined_df = pd.merge(
            transcriptions_df,
            scenes_df,
            left_on='scene_id', # FK in transcriptions
            right_on='id',      # PK in scenes
            how='inner',        # Only include transcriptions that have a matching scene
            suffixes=('_trans', '_scene') # Suffixes for overlapping column names
        )

        if combined_df.empty:
            st.info("シーンデータと結合できる字幕データが見つかりませんでした。")
            return pd.DataFrame()

        # --- Select and Rename Columns ---
        # Use .get() for potentially missing columns if needed, though validated above
        combined_df = combined_df[[
            'id_trans',
            'scene_id_scene', # Scene sequence number
            'start_timecode_scene',
            'end_timecode_scene',
            'description', # Scene description
            'start_timecode_trans',
            'end_timecode_trans',
            'transcription',
            'id_scene' # Scene primary key (for playback linking)
        ]].copy() # Use .copy() to avoid SettingWithCopyWarning

        combined_df.rename(columns={
            'id_trans': 'transcription_id',
            'scene_id_scene': 'scene_num',
            'start_timecode_scene': 'scene_start',
            'end_timecode_scene': 'scene_end',
            'description': 'scene_description',
            'start_timecode_trans': 'transcription_start',
            'end_timecode_trans': 'transcription_end',
            'transcription': 'dialogue',
            'id_scene': 'scene_pk' # Scene primary key
        }, inplace=True)

        # Add video filename column
        combined_df['video_filename'] = video_filename

        # --- Final Touches ---
        # Reorder columns for display
        combined_df = combined_df[[
            'transcription_id', # Key for selection
            'video_filename',
            'scene_num',
            'scene_start',
            'scene_end',
            'scene_description',
            'transcription_start',
            'transcription_end',
            'dialogue',
            'scene_pk' # Scene primary key (for playback)
        ]]

        # Sort by scene number and then transcription start time
        # Ensure columns exist before sorting
        if 'scene_num' in combined_df.columns and 'transcription_start' in combined_df.columns:
            # Handle potential non-numeric scene_num if it's not guaranteed to be int
            combined_df['scene_num'] = pd.to_numeric(combined_df['scene_num'], errors='coerce')
            combined_df.sort_values(by=['scene_num', 'transcription_start'], inplace=True, na_position='first')
        else:
             st.warning("ソートに必要な列 (scene_num, transcription_start) が見つかりません。")


        return combined_df

    except Exception as e:
        st.error(f"データ結合中にエラーが発生しました: {e}")
        import traceback
        st.error(traceback.format_exc()) # Print full traceback for debugging
        return pd.DataFrame()

# メインアプリケーション
def main():
    # サイドバー
    with st.sidebar:
        st.title("SQLite連携 動画ビューアー")
        
        # 動画選択
        videos = get_videos()
        if not videos:
            st.warning("表示できる動画がありません。データベースを確認してください。")
            return

        video_options = {f"{video['filename']} ({video.get('duration_seconds', 0):.1f}s)": video['id'] for video in videos}
        video_options_list = ["動画を選択..."] + list(video_options.keys())

        # Get the index of the currently selected video ID if it exists
        current_display_name = None
        if st.session_state.current_video_id:
            for name, vid in video_options.items():
                if vid == st.session_state.current_video_id:
                    current_display_name = name
                    break
        
        current_index = 0
        if current_display_name and current_display_name in video_options_list:
            current_index = video_options_list.index(current_display_name)

        selected_video_display = st.selectbox(
            "動画を選択",
            options=video_options_list,
            index=current_index,
            key="video_selector"
        )

        # --- Video Selection Logic ---
        selected_video_id = None
        if selected_video_display != "動画を選択...":
            selected_video_id = video_options.get(selected_video_display)

        # Proceed only if a video is selected
        if selected_video_id:
            video_filename = selected_video_display.split(' (')[0] # Extract filename

            # --- Fetch Data When Video Changes ---
            if st.session_state.current_video_id != selected_video_id:
                print(f"Video changed to: {video_filename} (ID: {selected_video_id})")
                st.session_state.current_video_id = selected_video_id
                st.session_state.current_video_filename = video_filename

                # Fetch combined data from API
                with st.spinner("結合データをAPIから取得中..."): # Show spinner
                    # ★★★ get_combined_data の結果を一時変数に格納して確認 ★★★
                    temp_df = get_combined_data(selected_video_id)
                    print(f"DEBUG: get_combined_data returned DataFrame shape: {temp_df.shape if not temp_df.empty else 'Empty'}")
                    st.session_state.combined_data = temp_df # Assign to session state
                    # ★★★ 格納直後の確認ログ ★★★
                    print(f"DEBUG: Assigned to st.session_state.combined_data. Is empty: {st.session_state.combined_data.empty}")
                    if 'combined_data' in st.session_state and not st.session_state.combined_data.empty:
                        print(f"DEBUG: st.session_state.combined_data columns after assignment: {st.session_state.combined_data.columns.tolist()}")
                    # ★★★★★★★★★★★★★★★★★★★

                # Reset states related to the previous video
                st.session_state.selected_combined_ids = set()
                st.session_state.show_video_preview = False
                st.session_state.current_scene_info_for_preview = None
                st.session_state.playing_scene_pk = None
                st.session_state.active_tab = "統合ビュー" # Default to combined view

                print("DEBUG: Rerunning after data fetch...")
                st.rerun() # Rerun to update the UI with new data

            # --- Sidebar Navigation (Simplified) ---
            # Removed Scene/Transcription tabs
            menu_options = ["統合ビュー", "エクスポート"] # プレビューはボタン制御, エクスポートをメニューに戻す
            menu_icons = ["table", "download"]      # Corresponding icons

            # Determine index based on active tab
            default_menu_index = 0
            if 'active_tab' in st.session_state:
                try:
                    # Check if the current active tab is in the available options
                    if st.session_state.active_tab in menu_options:
                        default_menu_index = menu_options.index(st.session_state.active_tab)
                    else:
                         # If active_tab has an old value (like 'combined'), default to '統合ビュー'
                         st.session_state.active_tab = "統合ビュー" # Reset to default view name
                         default_menu_index = 0
                except ValueError:
                     # Should not happen if logic above is correct, but fallback
                     st.session_state.active_tab = "統合ビュー"
                     default_menu_index = 0
            else:
                 # Initialize active_tab if it somehow doesn't exist
                 st.session_state.active_tab = "統合ビュー"
                 default_menu_index = 0

            selected_menu = option_menu(
                "メニュー",
                menu_options,
                icons=menu_icons,
                menu_icon="list",
                default_index=default_menu_index,
                orientation="vertical",
                key="main_menu"
            )

            # Update active tab based on menu selection using display names
            if selected_menu != st.session_state.active_tab:
                st.session_state.active_tab = selected_menu # Use display name directly
                print(f"DEBUG Sidebar: Menu changed, set active_tab to '{st.session_state.active_tab}'")
                st.rerun() # Rerun immediately when tab changes

            # --- Preview Section in Sidebar ---
            st.markdown("--- ")
            st.markdown("### プレビュー")
            
            # Button to show/hide preview
            if st.session_state.show_video_preview:
                if st.button("プレビューを隠す", key="hide_preview_btn"):
                    hide_preview()
                # Display preview content
                with st.container():
                    st.markdown("<div class='video-preview'>", unsafe_allow_html=True)
                    if st.session_state.current_video_id:
                        video_url = get_video_url(st.session_state.current_video_id)
                        if video_url:
                            # Determine start time for video
                            start_seconds = 0
                            # Use the stored preview info
                            preview_info = st.session_state.get('current_scene_info_for_preview')
                            if preview_info and 'start_timecode' in preview_info:
                                start_seconds = timecode_to_seconds(preview_info['start_timecode'])
                                start_seconds = max(0, int(start_seconds))

                            st.video(video_url, format="video/mp4", start_time=start_seconds)
                        else:
                            st.warning("動画URLを取得できませんでした。")

                    # Display current scene info if available
                    preview_info = st.session_state.get('current_scene_info_for_preview')
                    if preview_info:
                        st.markdown("<div class='scene-info'>", unsafe_allow_html=True)
                        thumb_url = get_thumbnail_url(preview_info.get('id'))
                        if thumb_url:
                            st.image(thumb_url, use_column_width=True, output_format="JPEG")
                        else:
                            st.caption("サムネイルなし")

                        st.markdown(f"**シーン#:** {preview_info.get('scene_id', '-')}")
                        st.markdown(f"**開始:** {preview_info.get('start_timecode', '-')}")
                        st.markdown(f"**終了:** {preview_info.get('end_timecode', '-')}")
                        st.markdown(f"**評価タグ:** {preview_info.get('scene_evaluation_tag', '-')}")
                        st.markdown(f"**説明:** {preview_info.get('description', '-')}")
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.caption("再生中のシーン情報はありません。")

                    st.markdown("</div>", unsafe_allow_html=True)

            else:
                # Show button is only relevant if a scene is selected for playback
                # Let the play buttons trigger the preview display directly
                st.caption("シーンまたは字幕の再生ボタンを押すと、ここにプレビューが表示されます。")

            # --- Export Section in Sidebar (Simplified) ---
            st.markdown("--- ")
            st.markdown("### エクスポート (統合ビュー基準)")
            count_export, duration_export = update_combined_stats()
            st.caption(f"選択: {count_export} 件 / 合計時間: {duration_export}")
            # Add actual export buttons later, passing combined_data and selected_ids
            export_disabled = st.session_state.combined_data.empty or not st.session_state.selected_combined_ids
            if st.button("EDLエクスポート (未実装)", key="export_edl_sidebar", disabled=export_disabled):
                 st.warning("EDLエクスポートはまだ実装されていません。")
            if st.button("SRTエクスポート (未実装)", key="export_srt_sidebar", disabled=export_disabled):
                 st.warning("SRTエクスポートはまだ実装されていません。")

    # ==================== Main Content Area ==================== #
    if st.session_state.current_video_id:
        # --- Debug active_tab --- (Keep this print)
        print(f"\nDEBUG: Checking main content area. Current active_tab: {st.session_state.active_tab}")

        # --- Display Content Based on Active Tab (Using Display Names) ---
        if st.session_state.active_tab == "統合ビュー": # ★★★ Check using display name ★★★
            st.subheader(f"統合ビュー: {st.session_state.current_video_filename}")

            # --- DEBUG --- (Keep existing debug checks for combined_data)
            print("DEBUG: Entering '統合ビュー' tab display logic.")
            
            combined_data_df = st.session_state.get('combined_data')
            if isinstance(combined_data_df, pd.DataFrame) and not combined_data_df.empty:
                # フィルタリングセクションを追加
                st.write("### フィルター設定")
                filter_cols = st.columns([1, 1, 1, 1])

                with filter_cols[0]:
                    # シーン番号フィルター
                    scene_filter = st.text_input("シーン番号", "", key="scene_filter")
                    
                with filter_cols[1]:
                    # 説明検索
                    description_filter = st.text_input("説明文検索", "", key="description_filter")
                    
                with filter_cols[2]:
                    # 字幕検索
                    dialogue_filter = st.text_input("字幕検索", "", key="dialogue_filter")

                with filter_cols[3]:
                    # 評価タグフィルター
                    if 'scene_evaluation_tag' in combined_data_df.columns:
                        unique_tags = ["すべて"] + sorted(combined_data_df['scene_evaluation_tag'].dropna().unique().tolist())
                        tag_filter = st.selectbox("評価タグ", unique_tags, index=0, key="tag_filter")
                    else:
                        tag_filter = st.selectbox("評価タグ", ["すべて"], key="tag_filter")

                # フィルター適用ボタン
                apply_filter = st.button("フィルターを適用", key="apply_filter")

                # フィルターリセットボタン
                reset_filter = st.button("リセット", key="reset_filter")

                # 元のDataFrameのコピーを作成（フィルタリング用）
                filtered_df = combined_data_df.copy()
                
                # リセットボタンが押された場合
                if reset_filter:
                    st.session_state.scene_filter = ""
                    st.session_state.description_filter = ""
                    st.session_state.dialogue_filter = ""
                    st.session_state.tag_filter = "すべて"
                    st.rerun()
                
                # フィルター適用ボタンが押された場合
                if apply_filter:
                    # シーン番号フィルター
                    if scene_filter:
                        try:
                            scene_num = int(scene_filter)
                            filtered_df = filtered_df[filtered_df['scene_num'] == scene_num]
                        except ValueError:
                            st.warning("シーン番号には数値を入力してください")
                    
                    # 説明検索
                    if description_filter:
                        filtered_df = filtered_df[filtered_df['scene_description'].str.contains(description_filter, na=False, case=False)]
                    
                    # 字幕検索
                    if dialogue_filter:
                        # 字幕がないシーン（dialogueがNULL）も含める
                        filtered_df = filtered_df[
                            filtered_df['dialogue'].isna() | 
                            filtered_df['dialogue'].str.contains(dialogue_filter, na=False, case=False)
                        ]
                    
                    # 評価タグフィルター
                    if tag_filter != "すべて":
                        filtered_df = filtered_df[filtered_df['scene_evaluation_tag'] == tag_filter]
                
                # フィルタリング後のデータが空かどうかチェック
                if filtered_df.empty:
                    st.warning("条件に一致するデータがありません")
                else:
                    # フィルタリング結果の件数を表示
                    st.write(f"表示: {len(filtered_df)} 件")
                    
                    # テーブル用のDataFrameを準備
                    display_df = filtered_df[[ 
                        'transcription_id', 'video_filename', 'scene_num', 'scene_start', 
                        'scene_end', 'scene_description', 'transcription_start', 
                        'transcription_end', 'dialogue', 'scene_pk'
                    ]].copy()
                    
                    # 字幕がないシーンの表示を調整
                    display_df['dialogue'] = display_df['dialogue'].fillna('（字幕なし）')
                    display_df['transcription_start'] = display_df['transcription_start'].fillna('-')
                    display_df['transcription_end'] = display_df['transcription_end'].fillna('-')
                    
                    # 選択状態を反映した列を追加
                    display_df['選択'] = display_df['transcription_id'].apply(
                        lambda x: '✔' if x in st.session_state.selected_combined_ids else ''
                    )
                    
                    # テーブル表示（Streamlitのデータフレーム）
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        column_config={
                            '選択': st.column_config.TextColumn(width='small'),
                            'scene_description': st.column_config.TextColumn(width='large'),
                            'dialogue': st.column_config.TextColumn(width='large')
                        }
                    )
                    
                    # シーンごとの再生ボタンを表示
                    st.write("### シーン再生")
                    # シーンごとに一意の値を取得
                    unique_scenes = display_df[['scene_pk', 'scene_num', 'scene_start', 'scene_end']].drop_duplicates()
                    
                    # 3列でボタンを配置
                    cols_per_row = 3
                    rows = math.ceil(len(unique_scenes) / cols_per_row)
                    
                    for row_idx in range(rows):
                        cols = st.columns(cols_per_row)
                        for col_idx in range(cols_per_row):
                            scene_idx = row_idx * cols_per_row + col_idx
                            if scene_idx < len(unique_scenes):
                                scene = unique_scenes.iloc[scene_idx]
                                scene_pk = scene['scene_pk']
                                scene_num = scene['scene_num']
                                with cols[col_idx]:
                                    if st.button(f"▶ シーン {scene_num}", key=f"play_scene_{scene_pk}"):
                                        play_scene(scene_pk)
                
                # 行ごとの選択操作ボタンを表示
                cols = st.columns(4)
                with cols[0]:
                    st.write("### 操作")
                with cols[1]:
                    if st.button("すべて選択", key="select_all_btn"):
                        # すべての transcription_id を選択状態に追加
                        st.session_state.selected_combined_ids = set(display_df['transcription_id'].tolist())
                        st.rerun()
                with cols[2]:
                    if st.button("すべて解除", key="deselect_all_btn"):
                        st.session_state.selected_combined_ids = set()
                        st.rerun()
                with cols[3]:
                    if st.button("選択を反転", key="toggle_all_btn"):
                        all_ids = set(display_df['transcription_id'].tolist())
                        st.session_state.selected_combined_ids = all_ids - st.session_state.selected_combined_ids
                        st.rerun()
                
                # 選択統計を表示
                count, duration = update_combined_stats()
                st.markdown(f"**選択統計:** {count} 件 / 合計時間: {duration}")
            else:
                st.warning("表示するデータがありません。APIからデータを取得できませんでした。")
                print(f"DEBUG: combined_data_df is {'empty' if isinstance(combined_data_df, pd.DataFrame) and combined_data_df.empty else 'not a DataFrame or None'}")
                # APIの状態をチェック
                if st.button("APIの状態を確認", key="check_api"):
                    try:
                        response = requests.get(f"{API_BASE_URL}/videos", timeout=5)
                        st.write(f"API Status: {response.status_code}")
                        if response.status_code == 200:
                            st.success("APIは正常に応答しています。問題が継続する場合はデータ取得ロジックを確認してください。")
                        else:
                            st.error(f"APIからエラーレスポンス: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"API接続エラー: {e}。サーバーが実行中か確認してください。")

        # --- Export Tab Logic (Example Placeholder) ---
        elif st.session_state.active_tab == "エクスポート": # ★★★ Check using display name ★★★
             st.subheader(f"エクスポート: {st.session_state.current_video_filename}")
             st.warning("エクスポート機能はサイドバーに移動しました。このタブは将来削除される可能性があります。")
             # You could potentially add more detailed export options here if needed
             count_export_main, duration_export_main = update_combined_stats()
             st.markdown(f"選択: {count_export_main} 件 / 合計時間: {duration_export_main}")
             export_disabled_main = st.session_state.combined_data.empty or not st.session_state.selected_combined_ids
             if st.button("EDLをエクスポート (未実装)", key="export_edl_main", disabled=export_disabled_main):
                  st.warning("EDLエクスポートはまだ実装されていません。")
             if st.button("SRTをエクスポート (未実装)", key="export_srt_main", disabled=export_disabled_main):
                  st.warning("SRTエクスポートはまだ実装されていません。")


    # --- Initial State (No video selected) ---
    else:
        st.info("← サイドバーから動画を選択してください")

# アプリケーション実行
if __name__ == "__main__":
    main() 