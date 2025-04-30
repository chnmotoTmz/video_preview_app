import sys
import os
import requests
import pandas as pd
import csv
from io import StringIO
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableView, QHeaderView,
    QDockWidget, QGroupBox, QScrollArea, QMessageBox, QFileDialog,
    QAbstractItemView, QSplitter, QAction, QStatusBar, QProgressBar
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl, QThread, pyqtSignal, QAbstractTableModel, QModelIndex, QTimer, QMetaObject, pyqtSlot, QItemSelectionModel
from PyQt5.QtGui import QStandardItemModel, QStandardItem
import vlc

# --- API Base URL ---
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000/api")

# --- Pandas Model for QTableView ---
# (Displaying Pandas DataFrame in QTableView requires a custom model)
class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=QModelIndex()):
        return self._data.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole or role == Qt.EditRole:
                value = self._data.iloc[index.row(), index.column()]
                return str(value)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._data.columns[section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(self._data.index[section])
        return None

    def setData(self, index, value, role):
        # Implement if editing is needed
        return False

    def flags(self, index):
        # Make cells selectable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def sort(self, column, order):
        colname = self._data.columns[column]
        ascending = order == Qt.AscendingOrder
        self.layoutAboutToBeChanged.emit()
        # シーン長さ（秒）は数値型でソート
        if colname == 'シーン長さ（秒）':
            self._data[colname] = pd.to_numeric(self._data[colname], errors='coerce')
        try:
            self._data.sort_values(by=colname, ascending=ascending, inplace=True, kind='mergesort')
        except Exception as e:
            print(f"Sort error: {e}")
        self._data.reset_index(drop=True, inplace=True)
        self.layoutChanged.emit()

# --- Worker Thread for API Calls ---
class ApiWorker(QThread):
    data_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, endpoint):
        super().__init__()
        self.endpoint = endpoint

    def run(self):
        try:
            url = f"{API_BASE_URL}/{self.endpoint}"
            print(f"Fetching data from: {url}") # Debug print
            response = requests.get(url, timeout=30) # Add timeout
            response.raise_for_status()
            data = response.json()
            self.data_ready.emit(data)
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"APIリクエストエラー ({self.endpoint}): {e}")
        except Exception as e:
            self.error_occurred.emit(f"データ取得中にエラーが発生しました ({self.endpoint}): {e}")

# --- VLCPlayerWidget ---
class VLCPlayerWidget(QWidget):
    def __init__(self, parent=None, app_ref=None):
        super().__init__(parent)
        print("VLCPlayerWidget initializing...")  # デバッグ用ログ
        vlc_options = [
            '--avcodec-hw=none',
            '--network-caching=300',
            '--quiet',         # ログ抑制
            '--verbose=0',     # ログレベル最低
        ]
        self.instance = vlc.Instance(vlc_options)
        self.setLayout(QVBoxLayout())
        self.video_frame = QWidget(self)
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setMinimumSize(640, 360)
        self.layout().addWidget(self.video_frame)
        self.info_label = QLabel("プレビュー", self)
        self.layout().addWidget(self.info_label)
        self.setMinimumSize(640, 400)
        self.app_ref = app_ref  # VideoPreviewAppの参照を保持
        self.mediaplayer = None  # 最初はNone
        self.stop_timer = QTimer(self)
        self.stop_timer.setSingleShot(True)

    def _on_stop_timer_timeout(self):
        self.stop()
        # 連続再生中なら次のシーン再生
        if self.app_ref and hasattr(self.app_ref, 'continuous_play_list'):
            if self.app_ref.continuous_play_index + 1 < len(self.app_ref.continuous_play_list):
                self.app_ref.continuous_play_index += 1
                self.app_ref.play_next_signal.emit(self.app_ref.continuous_play_index)

    def play(self, url, start_sec=0, duration_sec=None):
        print(f"Playing URL: {url}")  # デバッグ用ログ
        try:
            if self.mediaplayer is not None:
                self.mediaplayer.stop()
                self.mediaplayer.release()
            self.mediaplayer = self.instance.media_player_new()
            if sys.platform.startswith('linux'):
                self.mediaplayer.set_xwindow(int(self.video_frame.winId()))
            elif sys.platform == "win32":
                self.mediaplayer.set_hwnd(int(self.video_frame.winId()))
            elif sys.platform == "darwin":
                self.mediaplayer.set_nsobject(int(self.video_frame.winId()))
            if self.app_ref is not None:
                em = self.mediaplayer.event_manager()
                try:
                    em.event_detach(vlc.EventType.MediaPlayerEndReached)
                except Exception as e:
                    print(f"[VLC] detach error (無視可): {e}")
                em.event_attach(vlc.EventType.MediaPlayerEndReached, self.app_ref._on_vlc_end_reached)
            print(f"[VLC] 再生ファイル: {url}")
            media = self.instance.media_new(url)
            self.mediaplayer.set_media(media)
            self.stop_timer.stop()  # 既存タイマーを止める
            self.mediaplayer.play()
            if start_sec > 0:
                def set_position():
                    print(f"Seeking to {start_sec} seconds")  # デバッグ用ログ
                    self.mediaplayer.set_time(int(start_sec * 1000))
                QTimer.singleShot(100, set_position)
            # --- ここで自動停止タイマーをセット ---
            if duration_sec is not None and duration_sec > 0:
                try:
                    self.stop_timer.timeout.disconnect(self._on_stop_timer_timeout)
                except TypeError:
                    pass
                self.stop_timer.timeout.connect(self._on_stop_timer_timeout)
                self.stop_timer.start(int(duration_sec * 1000))
            print("Play command sent successfully")  # デバッグ用ログ
        except Exception as e:
            print(f"Failed to play {url}: {e}")
            raise

    def stop(self):
        self.stop_timer.stop()
        if self.mediaplayer is not None:
            self.mediaplayer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.video_frame.setGeometry(0, 0, self.width(), self.height() - 30)

def seconds_to_srt_timecode(total_seconds):
    """秒数をSRT形式のタイムコード（HH:MM:SS,mmm）に変換"""
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
    except Exception:
        return "00:00:00,000"

def timecode_to_seconds(tc, frame_rate=30.0):
    """タイムコード文字列を秒数（浮動小数点）に変換"""
    try:
        h, m, s, f = map(int, tc.split(':'))
        return h * 3600 + m * 60 + s + f / frame_rate
    except Exception:
        return 0

def seconds_to_timecode(total_seconds, frame_rate=60.0): # EDLは60fpsに変更
    """秒数（浮動小数点）をタイムコード文字列に変換"""
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
    except Exception:
        return "00:00:00:00"

# --- Main Application Window ---
class VideoPreviewApp(QMainWindow):
    play_next_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("動画前処理ビューアー (PyQt5)")
        self.setGeometry(100, 100, 1200, 800)
        self.api_worker = None
        self.all_data_df = pd.DataFrame()
        self.filtered_data_df = pd.DataFrame()
        self.continuous_play_list = []  # 連続再生用リスト
        self.continuous_play_index = 0  # 現在の再生インデックス
        self.base_folder = ""
        self._load_base_folder()
        self._init_ui()
        self._connect_signals()
        self._load_initial_data()
        self.play_next_signal.connect(self._play_scene_by_index)
        # VLCイベントハンドラ登録はVLCPlayerWidget側で行う

    def _load_base_folder(self):
        try:
            resp = requests.get(f"{API_BASE_URL}/settings/base_folder")
            resp.raise_for_status()
            self.base_folder = resp.json().get("path", "")
            print(f"Base folder: {self.base_folder}")
        except Exception as e:
            QMessageBox.critical(self, "ベースフォルダ取得エラー", str(e))
            self.base_folder = ""

    def _init_ui(self):
        # --- Central Widget ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Use QSplitter for resizable areas
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- Main Content Area (Left/Center) ---
        main_content_widget = QWidget()
        main_content_layout = QVBoxLayout(main_content_widget)
        splitter.addWidget(main_content_widget)

        # Search Bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("検索:"))
        self.search_input = QLineEdit()
        search_layout.addWidget(self.search_input)
        main_content_layout.addLayout(search_layout)

        # Data Table
        self.data_table = QTableView()
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectRows) # Select whole rows
        self.data_table.setSelectionMode(QAbstractItemView.ExtendedSelection) # Allow multiple selection
        self.data_table.setSortingEnabled(True) # Enable sorting
        self.table_model = PandasModel(self.filtered_data_df) # Use PandasModel
        self.data_table.setModel(self.table_model)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive) # Allow resizing columns
        # self.data_table.resizeColumnsToContents() # Initial resize
        main_content_layout.addWidget(self.data_table)

        # --- Preview Area (Right) ---
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_widget.setMinimumWidth(350) # Set minimum width for preview
        splitter.addWidget(preview_widget)

        preview_layout.addWidget(QLabel("プレビュー"))
        self.vlc_player = VLCPlayerWidget(app_ref=self)
        preview_layout.addWidget(self.vlc_player)
        self.scene_info_label = QLabel("シーン情報をここに表示")
        self.scene_info_label.setWordWrap(True)
        self.scene_info_label.setAlignment(Qt.AlignTop)
        preview_layout.addWidget(self.scene_info_label)

        self.close_preview_button = QPushButton("プレビューを閉じる")
        preview_layout.addWidget(self.close_preview_button)
        preview_layout.addStretch() # Push widgets to the top

        # Hide preview initially
        preview_widget.setVisible(False)
        self.preview_widget_ref = preview_widget # Keep reference to show/hide

        # Set initial sizes for splitter (optional)
        splitter.setSizes([750, 450])

        # --- Sidebar (Dock Widget) ---
        self.sidebar = QDockWidget("コントロール", self)
        self.sidebar.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar)

        sidebar_content = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_content)
        sidebar_layout.setAlignment(Qt.AlignTop) # Align widgets to top

        # Filters Group
        filter_group = QGroupBox("絞り込み")
        filter_layout = QVBoxLayout(filter_group)
        # Add filter widgets here (e.g., QComboBox for tags)
        filter_layout.addWidget(QLabel("（フィルター機能未実装）"))
        sidebar_layout.addWidget(filter_group)

        # Selection Info Group
        selection_group = QGroupBox("選択情報")
        selection_layout = QVBoxLayout(selection_group)
        self.selected_count_label = QLabel("選択中の行数: 0")
        self.selected_duration_label = QLabel("選択中の合計時間: 00:00:00:00")
        selection_layout.addWidget(self.selected_count_label)
        selection_layout.addWidget(self.selected_duration_label)
        sidebar_layout.addWidget(selection_group)

        # Actions Group
        action_group = QGroupBox("アクション")
        action_layout = QVBoxLayout(action_group)
        self.play_selected_button = QPushButton("選択項目をプレビュー") # Changed from continuous play
        self.export_csv_button = QPushButton("選択項目をCSVエクスポート")
        self.export_srt_button = QPushButton("選択項目をSRTエクスポート")
        self.export_edl_button = QPushButton("選択項目をEDLエクスポート")
        self.delete_button = QPushButton("選択項目を削除")
        self.delete_button.setStyleSheet("color: red;") # Warning color

        action_layout.addWidget(self.play_selected_button)
        action_layout.addWidget(self.export_csv_button)
        action_layout.addWidget(self.export_srt_button)
        action_layout.addWidget(self.export_edl_button)
        action_layout.addWidget(self.delete_button)
        sidebar_layout.addWidget(action_group)

        # Add ScrollArea to sidebar content if it gets too long
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(sidebar_content)
        self.sidebar.setWidget(scroll_area)

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("準備完了")

    def _connect_signals(self):
        self.search_input.textChanged.connect(self._filter_data)
        self.data_table.selectionModel().selectionChanged.connect(self._update_selection_info)
        # Connect button clicks to methods
        self.play_selected_button.clicked.connect(self._play_selected_scene)
        self.close_preview_button.clicked.connect(self._hide_preview)
        self.export_csv_button.clicked.connect(lambda: self._export_selected('CSV'))
        self.export_srt_button.clicked.connect(lambda: self._export_selected('SRT'))
        self.export_edl_button.clicked.connect(lambda: self._export_selected('EDL'))
        self.delete_button.clicked.connect(self._delete_selected)
        # Connect media player signals if needed (e.g., for continuous play logic)
        # self.media_player.stateChanged.connect(...)
        # self.media_player.positionChanged.connect(...)
        # self.media_player.mediaStatusChanged.connect(...)

    def _load_initial_data(self):
        self.status_bar.showMessage("データを読み込み中...")
        # Use the worker thread
        self.api_worker = ApiWorker("merged_data/all") # Use the merged data endpoint
        self.api_worker.data_ready.connect(self._on_data_loaded)
        self.api_worker.error_occurred.connect(self._on_api_error)
        self.api_worker.start()

    def _on_data_loaded(self, data):
        try:
            if data and isinstance(data, list):
                self.all_data_df = pd.DataFrame(data)
                # シーン長さ（秒）を計算して追加
                if 'start_timecode' in self.all_data_df.columns and 'end_timecode' in self.all_data_df.columns:
                    self.all_data_df['scene_duration'] = self.all_data_df.apply(
                        lambda row: timecode_to_seconds(row['end_timecode']) - timecode_to_seconds(row['start_timecode']),
                        axis=1
                    )
                # Select and rename columns for display
                display_cols = {
                    'scene_pk': 'シーンPK',
                    'video_filename': '動画ファイル',
                    'scene_id': 'シーン番号',
                    'start_timecode': '開始TC',
                    'end_timecode': '終了TC',
                    'scene_duration': 'シーン長さ（秒）',  # 追加
                    'description': 'シーン説明',
                    'transcription': '字幕',
                    'evaluation_tag': '評価タグ',
                    'scene_good_reason': 'シーン良い理由',
                    'scene_bad_reason': 'シーン悪い理由',
                    'transcription_good_reason': '字幕良い理由',
                    'transcription_bad_reason': '字幕悪い理由',
                    'video_id': 'VideoID',
                    'transcription_id': 'TransID',
                    'video_filepath': 'video_filepath'
                }
                cols_to_keep = [col for col in display_cols.keys() if col in self.all_data_df.columns]
                self.all_data_df = self.all_data_df[cols_to_keep]
                self.all_data_df.rename(columns=display_cols, inplace=True)
                print(f"Loaded {len(self.all_data_df)} rows.") # Debug print
                self._filter_data() # Apply initial filter (or show all)
                self.status_bar.showMessage(f"{len(self.all_data_df)}件のデータを読み込みました", 5000)
            else:
                self._on_api_error("APIから無効なデータ形式を受け取りました。")
        except Exception as e:
             self._on_api_error(f"データ処理中にエラーが発生しました: {e}")
        finally:
            self.api_worker = None # Clean up worker reference

    def _on_api_error(self, error_message):
        QMessageBox.critical(self, "APIエラー", error_message)
        self.status_bar.showMessage(f"エラー: {error_message}", 5000)
        self.all_data_df = pd.DataFrame() # Clear data on error
        self._filter_data()
        self.api_worker = None # Clean up worker reference

    def _filter_data(self):
        search_term = self.search_input.text().lower()
        if not search_term:
            self.filtered_data_df = self.all_data_df.copy()
        else:
            # Implement search logic across relevant columns
            # This requires the original column names if renamed, or search the renamed ones
            try:
                df_to_search = self.all_data_df # Search the display DataFrame
                self.filtered_data_df = df_to_search[
                    df_to_search.apply(lambda row:
                        search_term in str(row.get('動画ファイル', '')).lower() or \
                        search_term in str(row.get('シーン説明', '')).lower() or \
                        search_term in str(row.get('字幕', '')).lower(),
                        axis=1
                    )
                ]
            except Exception as e:
                print(f"Filtering error: {e}") # Debug
                self.filtered_data_df = self.all_data_df.copy() # Fallback

        # Update the table model
        self.table_model.update_data(self.filtered_data_df)
        # Adjust column widths after data update (optional, can be slow)
        # self.data_table.resizeColumnsToContents()
        self._update_selection_info() # Reset selection info

    def _get_selected_rows_data(self):
        """Gets the DataFrame corresponding to selected rows in the QTableView."""
        selected_indexes = self.data_table.selectionModel().selectedRows()
        if not selected_indexes:
            return pd.DataFrame()

        # Get the indices from the filtered DataFrame
        selected_df_indices = [idx.row() for idx in selected_indexes]
        selected_data = self.filtered_data_df.iloc[selected_df_indices]
        return selected_data

    def _update_selection_info(self):
        selected_data = self._get_selected_rows_data()
        count = len(selected_data)
        self.selected_count_label.setText(f"選択中の行数: {count}")

        # 合計時間（秒）とタイムコード形式を計算
        total_duration_str = "0"
        if count > 0 and 'シーン長さ（秒）' in selected_data.columns:
            try:
                total_sec = selected_data['シーン長さ（秒）'].astype(float).sum()
                total_duration_str = f"{total_sec:.2f} 秒（{seconds_to_timecode(total_sec)}）"
            except Exception as e:
                total_duration_str = f"計算エラー: {e}"

        self.selected_duration_label.setText(f"選択中の合計時間: {total_duration_str}")

    def _play_selected_scene(self):
        selected_data = self._get_selected_rows_data()
        if selected_data.empty:
            QMessageBox.warning(self, "再生エラー", "プレビューする行を選択してください。")
            return
        # 複数行選択時は連続再生
        self.continuous_play_list = selected_data.to_dict('records')
        self.continuous_play_index = 0
        self._play_scene_by_index(self.continuous_play_index)

    def _highlight_playing_row(self, idx):
        # 現在再生中のデータ
        if not (0 <= idx < len(self.continuous_play_list)):
            return
        playing_row = self.continuous_play_list[idx]
        pk_col = 'シーンPK'  # 表示用カラム名
        if pk_col in self.filtered_data_df.columns and 'シーンPK' in playing_row:
            match = self.filtered_data_df[self.filtered_data_df[pk_col] == playing_row['シーンPK']]
            if not match.empty:
                row_idx = match.index[0]
                selection_model = self.data_table.selectionModel()
                if selection_model is not None:
                    selection_model.clearSelection()
                    model_index = self.table_model.index(row_idx, 0)
                    selection_model.select(model_index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
                    self.data_table.scrollTo(model_index)

    @pyqtSlot(int)
    def _play_scene_by_index(self, idx):
        print(f"Playing index {idx}, Data: {self.continuous_play_list[idx]}")
        if not (0 <= idx < len(self.continuous_play_list)):
            return
        scene_data = self.continuous_play_list[idx]
        video_filepath = scene_data.get('video_filepath')
        start_tc = scene_data.get('開始TC')
        end_tc = scene_data.get('終了TC')
        if not video_filepath or not self.base_folder:
            QMessageBox.critical(self, "再生エラー", "動画ファイルパスまたはベースフォルダが取得できません。")
            return
        abs_path = os.path.abspath(os.path.join(self.base_folder, video_filepath))
        print(f"[再生パス {idx}] {abs_path}")
        print(f"Checking file existence: {abs_path}")
        if not abs_path.startswith(os.path.abspath(self.base_folder)):
            print(f"File path security error: {abs_path}")
            QMessageBox.critical(self, "再生エラー", "不正なファイルパスです。")
            return
        if not os.path.exists(abs_path):
            print(f"File does not exist: {abs_path}")
            QMessageBox.critical(self, "再生エラー", f"ファイルが存在しません: {abs_path}")
            return
        start_seconds = timecode_to_seconds(start_tc)
        end_seconds = timecode_to_seconds(end_tc)
        duration = max(0, end_seconds - start_seconds)
        self.vlc_player.play(abs_path, start_sec=start_seconds, duration_sec=duration)
        info_text = f"ファイル: {scene_data.get('動画ファイル', 'N/A')}\n" \
                    f"シーン: {scene_data.get('シーン番号', '-')} (PK: {scene_data.get('シーンPK', '-')})\n" \
                    f"時間: {scene_data.get('開始TC', '-')} - {scene_data.get('終了TC', '-')}\n" \
                    f"説明: {scene_data.get('シーン説明', '-')}\n" \
                    f"字幕: {scene_data.get('字幕', '-') }"
        self.scene_info_label.setText(info_text)
        self.preview_widget_ref.setVisible(True)
        self.status_bar.showMessage(f"シーン {scene_data.get('シーンPK', '')} を再生中...", 3000)
        self._highlight_playing_row(idx)

    def _on_vlc_end_reached(self, event):
        print("VLC MediaPlayerEndReached event received!")  # デバッグ用
        if self.continuous_play_index + 1 < len(self.continuous_play_list):
            self.continuous_play_index += 1
            print(f"Emitting play_next_signal for index {self.continuous_play_index}")
            self.play_next_signal.emit(self.continuous_play_index)
            print(f"Scheduled next playback for index {self.continuous_play_index}")
        else:
            self.status_bar.showMessage("連続再生が終了しました", 3000)
            self.continuous_play_list = []
            self.continuous_play_index = 0

    def _hide_preview(self):
        self.vlc_player.stop()
        self.preview_widget_ref.setVisible(False)
        self.scene_info_label.setText("シーン情報をここに表示")
        self.status_bar.clearMessage()
        self.continuous_play_list = []
        self.continuous_play_index = 0

    def _export_selected(self, format):
        selected_data = self._get_selected_rows_data()
        if selected_data.empty:
            QMessageBox.warning(self, "エクスポートエラー", f"{format}エクスポートする行を選択してください。")
            return

        # 1. CSVデータを生成
        if format == 'CSV':
            filename, _ = QFileDialog.getSaveFileName(self, "CSVファイルを保存", "", "CSV Files (*.csv)")
            if filename:
                try:
                    selected_data.to_csv(filename, index=False, encoding='utf-8-sig')
                    self.status_bar.showMessage(f"CSVファイルを保存しました: {filename}", 5000)
                except Exception as e:
                    QMessageBox.critical(self, "CSV保存エラー", f"ファイルの保存中にエラーが発生しました: {e}")
            return

        # 選択されたデータを基にEDLとSRTを生成
        # 必要な列を準備
        required_cols = ['シーンPK', '動画ファイル', '開始TC', '終了TC', '字幕']
        missing_cols = [col for col in required_cols if col not in selected_data.columns]
        if missing_cols:
            QMessageBox.warning(self, "エクスポートエラー", f"必要な列が見つかりません: {', '.join(missing_cols)}")
            return

        # EDL生成用のデータ準備
        # 必要な情報を選択
        edl_data = selected_data[['シーンPK', '動画ファイル', '開始TC', '終了TC']].copy()
        edl_data['duration'] = edl_data.apply(
            lambda row: timecode_to_seconds(row['終了TC']) - timecode_to_seconds(row['開始TC']),
            axis=1
        )

        # 2. EDLデータを生成
        edl_content = "TITLE: Video Preprocessing Export\n"
        edl_content += "FCM: NON-DROP FRAME\n\n"
        record_start_seconds = 0.0
        edl_frame_rate = 60.0  # EDLも60fpsで出力するように変更
        source_frame_rate = 60.0
        video_record_offsets = {}  # 動画ファイル -> レコードINタイムコード（秒）

        for i, row in edl_data.iterrows():
            event_num = f"{i + 1:03d}"
            reel_name = os.path.splitext(row['動画ファイル'])[0][:8].upper()
            track_type = "V"
            edit_type = "C"

            # ソースタイムコード（オフセットは適用しない、ゼロスタート）
            source_start_sec = timecode_to_seconds(row['開始TC'], source_frame_rate)
            source_end_sec = timecode_to_seconds(row['終了TC'], source_frame_rate)
            source_in_tc = seconds_to_timecode(source_start_sec, edl_frame_rate)
            source_out_tc = seconds_to_timecode(source_end_sec, edl_frame_rate)

            # 継続時間を計算
            source_duration_sec = max(0.0, source_end_sec - source_start_sec)
            if source_duration_sec < 1.0 / source_frame_rate:
                source_end_sec = source_start_sec + (1.0 / source_frame_rate)
                source_out_tc = seconds_to_timecode(source_end_sec, edl_frame_rate)
                source_duration_sec = 1.0 / source_frame_rate

            # レコードタイムコード
            record_in_sec = record_start_seconds
            record_out_sec = record_start_seconds + source_duration_sec
            record_in_tc = seconds_to_timecode(record_in_sec, edl_frame_rate)
            record_out_tc = seconds_to_timecode(record_out_sec, edl_frame_rate)

            # 動画ファイルごとにレコードINタイムコードを保存
            video_record_offsets[row['動画ファイル']] = record_in_sec

            # EDL行を生成
            edl_content += f"{event_num}  {reel_name:<8} {track_type}     {edit_type}        {source_in_tc} {source_out_tc} {record_in_tc} {record_out_tc}\n"
            edl_content += f"* FROM CLIP NAME: {row['動画ファイル']}\n\n"

            record_start_seconds = record_out_sec

        # EDLファイルの保存
        if format == 'EDL':
            filename, _ = QFileDialog.getSaveFileName(self, "EDLファイルを保存", "export.edl", "EDL Files (*.edl);;All Files (*)")
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(edl_content)
                    self.status_bar.showMessage(f"EDLファイルを保存しました: {filename}", 5000)
                except Exception as e:
                    QMessageBox.critical(self, "EDL保存エラー", f"ファイルの保存中にエラーが発生しました: {e}")
            return

        # 3. CSVデータを生成（文字列として）
        csv_buffer = StringIO()
        selected_data.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()

        # 4. CSVデータをパース
        csv_reader = csv.DictReader(StringIO(csv_content))
        subtitles = []
        for row in csv_reader:
            if '字幕' in row and row['字幕'] and row['字幕'] != 'nan':  # 字幕が空でない場合のみ
                subtitles.append({
                    '動画ファイル': row['動画ファイル'],
                    'start_timecode': row['開始TC'],
                    'end_timecode': row['終了TC'],
                    'transcription': row['字幕']
                })

        # 字幕をソート（動画ファイル順、開始TC順）
        subtitles.sort(key=lambda x: (x['動画ファイル'], timecode_to_seconds(x['start_timecode'])))

        # 5. SRTデータを生成
        srt_content = ""
        for i, subtitle in enumerate(subtitles):
            filename = subtitle['動画ファイル']
            # レコードINタイムコードをオフセットとして取得
            record_offset_sec = video_record_offsets.get(filename, 0.0)

            # 字幕の開始・終了時間を取得（ゼロスタート）
            start_sec = timecode_to_seconds(subtitle['start_timecode'], source_frame_rate)
            end_sec = timecode_to_seconds(subtitle['end_timecode'], source_frame_rate)

            # オフセットを適用
            adjusted_start_sec = start_sec + record_offset_sec
            adjusted_end_sec = end_sec + record_offset_sec

            # SRT形式に変換
            start_srt = seconds_to_srt_timecode(adjusted_start_sec)
            end_srt = seconds_to_srt_timecode(adjusted_end_sec)
            text = subtitle['transcription']

            srt_content += f"{i + 1}\n"
            srt_content += f"{start_srt} --> {end_srt}\n"
            srt_content += f"{text}\n\n"

        # 6. SRTファイルの保存
        if format == 'SRT':
            filename, _ = QFileDialog.getSaveFileName(self, "SRTファイルを保存", "export.srt", "SRT Files (*.srt)")
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    self.status_bar.showMessage(f"SRTファイルを保存しました: {filename}", 5000)
                except Exception as e:
                    QMessageBox.critical(self, "SRT保存エラー", f"ファイルの保存中にエラーが発生しました: {e}")

    def _delete_selected(self):
        selected_data = self._get_selected_rows_data()
        if selected_data.empty:
            QMessageBox.warning(self, "削除エラー", "削除する行を選択してください。")
            return

        scene_pks_to_delete = selected_data['シーンPK'].dropna().astype(int).unique().tolist()

        if not scene_pks_to_delete:
            QMessageBox.warning(self, "削除エラー", "選択された行に有効なシーンPKが見つかりません。")
            return

        reply = QMessageBox.question(self, '削除確認',
                                     f"{len(scene_pks_to_delete)}件のシーンを削除しますか？\nこの操作は元に戻せません。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                self.status_bar.showMessage("シーンを削除中...")
                payload = {'scene_pks': scene_pks_to_delete}
                response = requests.post(f"{API_BASE_URL}/scenes/delete", json=payload, timeout=60)
                response.raise_for_status()
                result = response.json()
                deleted_count = result.get('deleted_count', 0)
                QMessageBox.information(self, "削除完了", f"{deleted_count}件のシーンを削除しました。")
                self.status_bar.showMessage(f"{deleted_count}件削除しました。データを再読み込みします...", 3000)
                # Reload data after deletion
                self._load_initial_data()
            except requests.exceptions.RequestException as e:
                error_detail = ""
                try:
                    error_data = response.json()
                    if 'error' in error_data: error_detail = f"\nサーバーエラー: {error_data['error']}"
                except: pass
                QMessageBox.critical(self, "削除APIエラー", f"APIリクエストエラー: {e}{error_detail}")
                self.status_bar.showMessage("削除エラー", 5000)
            except Exception as e:
                QMessageBox.critical(self, "削除エラー", f"シーン削除中にエラーが発生しました: {e}")
                self.status_bar.showMessage("削除エラー", 5000)
            finally:
                # Consider adding progress indicator
                 pass

    def closeEvent(self, event):
        # Clean up resources if needed (e.g., stop threads)
        if self.api_worker and self.api_worker.isRunning():
            # self.api_worker.quit() # Or terminate() if necessary
            # self.api_worker.wait()
            pass # Handle thread termination properly
        self.vlc_player.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    main_window = VideoPreviewApp()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
