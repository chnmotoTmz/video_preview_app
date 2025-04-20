#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QLabel, QComboBox, 
                            QScrollArea, QPushButton, QSplitter, QFrame,
                            QTextEdit, QStatusBar, QFileDialog, QMessageBox,
                            QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QAbstractItemView)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QUrl, QTimer
from PyQt5.QtGui import QPixmap, QImage, QStandardItemModel, QStandardItem, QColor

# --- Custom Table Widget Item for Numerical Sorting ---
class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        # Try converting text to float for comparison
        try:
            return float(self.text()) < float(other.text())
        except (ValueError, TypeError):
            # Fallback to default string comparison if conversion fails
            return super().__lt__(other)

# 自作コンポーネントをインポート
from database_manager import DatabaseManager
from video_player import VideoPlayer

class SceneInfoPanel(QWidget):
    """シーン情報表示パネル"""
    sceneDataChanged = pyqtSignal(dict) # Signal emitted after saving changes
    
    def __init__(self, parent=None):
        """
        初期化関数
        
        Args:
            parent: 親ウィジェット
        """
        super().__init__(parent)
        
        # レイアウト設定
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # タイトルラベル
        title_label = QLabel("シーン情報:")
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)
        
        # 説明テキストエリア
        self.description_label = QLabel("説明:")
        layout.addWidget(self.description_label)
        
        self.description_text = QTextEdit()
        # self.description_text.setReadOnly(True) # Make editable
        self.description_text.setMaximumHeight(100)
        layout.addWidget(self.description_text)
        
        # 文字起こしテキストエリア
        self.transcript_label = QLabel("文字起こし:")
        layout.addWidget(self.transcript_label)
        
        self.transcript_text = QTextEdit()
        # self.transcript_text.setReadOnly(True) # Make editable
        layout.addWidget(self.transcript_text)
        
        # Save Button
        self.save_button = QPushButton("説明/文字起こしを保存")
        self.save_button.setEnabled(False) # Initially disabled
        self.save_button.clicked.connect(self.save_scene_changes)
        layout.addWidget(self.save_button)
        
        # 時間情報ラベル
        self.time_info_label = QLabel("時間: --:--:-- - --:--:-- (--秒)")
        layout.addWidget(self.time_info_label)
        
        self.db_manager = None # Initialize db_manager as None
        self.current_scene_data = None # Store the current scene data
        
    def set_db_manager(self, db_manager):
        """データベースマネージャーを設定する"""
        print("SceneInfoPanel: Setting DB Manager")
        self.db_manager = db_manager

    def update_info(self, scene_data):
        """
        シーン情報を更新
        
        Args:
            scene_data (dict): シーン情報
        """
        if not scene_data:
            self.clear()
            return
            
        self.current_scene_data = scene_data # Store current data
        self.save_button.setEnabled(True) # Enable save button

        # 説明を設定
        self.description_text.setText(scene_data.get('description', ''))
        
        # 文字起こしを設定
        self.transcript_text.setText(scene_data.get('transcript', ''))
        
        # 時間情報を設定
        time_in = self.format_time(scene_data.get('time_in', 0))
        time_out = self.format_time(scene_data.get('time_out', 0))
        duration = scene_data.get('duration', 0)
        
        self.time_info_label.setText(f"時間: {time_in} - {time_out} ({duration:.1f}秒)")
        
    def clear(self):
        """情報をクリア"""
        self.current_scene_data = None # Clear stored data
        self.save_button.setEnabled(False) # Disable save button
        self.description_text.clear()
        self.transcript_text.clear()
        self.time_info_label.setText("時間: --:--:-- - --:--:-- (--秒)")
        
    def format_time(self, seconds):
        """秒数を時間形式に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def save_scene_changes(self):
        """現在の説明と文字起こしをデータベースに保存する"""
        if not self.current_scene_data or not self.db_manager:
            QMessageBox.warning(self, "エラー", "保存するシーン情報がないか、データベースに接続されていません。")
            return

        video_id = self.current_scene_data.get('video_id')
        scene_id = self.current_scene_data.get('scene_id')
        new_description = self.description_text.toPlainText()
        new_transcript = self.transcript_text.toPlainText()

        if video_id is None or scene_id is None:
            QMessageBox.critical(self, "エラー", "シーンIDまたはビデオIDが見つかりません。")
            return

        success = self.db_manager.update_scene_text(video_id, scene_id, new_description, new_transcript)

        if success:
            QMessageBox.information(self, "保存完了", "シーン情報を更新しました。")
            # Update the stored data
            self.current_scene_data['description'] = new_description
            self.current_scene_data['transcript'] = new_transcript
            # Emit signal with updated data
            self.sceneDataChanged.emit(self.current_scene_data)
        else:
            QMessageBox.critical(self, "保存エラー", "シーン情報の更新中にエラーが発生しました。")

    def populate_scene_table(self):
        """データベース情報に基づいてシーンテーブルを構築する"""
        print("Populating scene table...") # Check if method is called
        if not self.db_manager:
            print("  DB Manager not available.")
            return

        self.scene_table_widget.clearContents() # Use clearContents for better visual clearing
        self.scene_table_widget.setRowCount(0)    # Ensure row count is also reset
        self.scene_table_widget.setSortingEnabled(False) # Disable sorting during population

        all_scenes = self.db_manager.get_all_scenes() # Get all scenes at once
        print(f"  Found {len(all_scenes)} total scenes.")

        # Sort scenes maybe by video_id then scene_id?
        all_scenes.sort(key=lambda s: (s.get('video_id', ''), s.get('scene_id', 0)))

        self.scene_table_widget.setRowCount(len(all_scenes))

        for row_idx, scene in enumerate(all_scenes):
            # --- Column 0: Checkbox --- 
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Unchecked)
            self.scene_table_widget.setItem(row_idx, 0, chk_item)

            # --- Column 1: File ID --- 
            # Use NumericTableWidgetItem, assuming File ID might be sortable numerically if prefix is removed?
            # Or, if File ID is purely alphanumeric, standard sort might be better. Let's try Numeric first.
            file_id_str = scene.get('video_id', '?')
            file_item = NumericTableWidgetItem(file_id_str)
            self.scene_table_widget.setItem(row_idx, 1, file_item)

            # --- Column 2: Scene ID --- 
            # Use NumericTableWidgetItem for Scene ID
            scene_id_str = str(scene.get('scene_id', '?'))
            scene_id_item = NumericTableWidgetItem(scene_id_str)
            self.scene_table_widget.setItem(row_idx, 2, scene_id_item)

            # --- Column 3: Start Time --- 
            start_item = QTableWidgetItem(self.format_seconds(scene.get('time_in', 0)))
            self.scene_table_widget.setItem(row_idx, 3, start_item)

            # --- Column 4: End Time --- 
            end_item = QTableWidgetItem(self.format_seconds(scene.get('time_out', 0)))
            self.scene_table_widget.setItem(row_idx, 4, end_item)

            # --- Column 5: Description Length --- 
            desc_len = len(scene.get('description', '') or '') # Handle None or empty string
            desc_len_item = NumericTableWidgetItem(str(desc_len)) 
            desc_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter) # Align right
            self.scene_table_widget.setItem(row_idx, 5, desc_len_item)

            # --- Column 6: Transcript Length --- 
            trans_len = len(scene.get('transcript', '') or '') # Handle None or empty string
            trans_len_item = NumericTableWidgetItem(str(trans_len)) 
            trans_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter) # Align right
            self.scene_table_widget.setItem(row_idx, 6, trans_len_item)

            # --- Column 7: Scene Length (Duration) --- 
            # Duration is already calculated in get_all_scenes
            scene_duration = scene.get('duration', 0)
            # Format duration to show seconds with milliseconds
            duration_str = f"{scene_duration:.3f}" 
            scene_len_item = NumericTableWidgetItem(duration_str)
            scene_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter) # Align right
            self.scene_table_widget.setItem(row_idx, 7, scene_len_item)

            # Store the full scene data in the row (e.g., in the first item)
            chk_item.setData(Qt.UserRole + 1, scene)
            # You could also store it per row using vertical headers, but this is simpler

        self.scene_table_widget.setSortingEnabled(True) # Re-enable sorting

class VideoPreviewApp(QMainWindow):
    """ビデオプレビューアプリケーションのメインウィンドウ"""
    
    def __init__(self):
        """初期化関数"""
        super().__init__()
        
        # アプリケーション設定
        self.setWindowTitle("ビデオプレビューアプリ")
        self.setGeometry(100, 100, 1200, 800)
        
        # データベースマネージャー
        self.db_manager = None
        # Fixed database path
        self.db_path = r"C:\Users\motoc\データ構造を分析しSQLiteに格納する方法\video_data.db"
        self.base_dir = "e:\100GOPRO"
        
        # 現在選択されているシーン情報
        self.current_scene = None
        
        # Continuous playback state
        self.playback_playlist = None
        self.current_playlist_index = -1
        
        # UIの設定
        self.setup_ui()

        # Automatically load the fixed database after UI setup
        # The signal connection should happen *after* the player is initialized
        # if os.path.exists(self.db_path):
        #     self.load_database(self.db_path)
        #     # Connect player signal after player is potentially initialized - Moved from here
        #     # self.video_player.playbackFinished.connect(self.play_next_in_playlist)
        # else:
        #      QMessageBox.critical(self, "エラー", f"固定データベースファイルが見つかりません:\n{self.db_path}")
        #      self.statusBar.showMessage("エラー: データベースファイルが見つかりません")

        # Ensure player is created before connecting signals
        # Since db is loaded automatically in setup_ui, player should exist here
        if hasattr(self, 'video_player') and self.video_player:
             print("Connecting playbackFinished signal in __init__...")
             self.video_player.playbackFinished.connect(self.play_next_in_playlist, Qt.QueuedConnection)
             # Connect scene data changed signal
             if hasattr(self, 'scene_info_panel'):
                 print("Connecting sceneDataChanged signal in __init__...")
                 self.scene_info_panel.sceneDataChanged.connect(self.on_scene_data_updated)
             else:
                  print("Warning: Scene info panel not found for signal connection.")
        else:
             print("Warning: Video player not found in __init__ for signal connection.")
        
    def setup_ui(self):
        """UIの設定"""
        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout(central_widget)
        
        # 上部コントロールエリア
        top_layout = QHBoxLayout()
        
        # ベースディレクトリ選択
        self.base_dir_label = QLabel("ベースディレクトリ: 未選択")
        self.base_dir_label.setMinimumWidth(250) # Adjust width as needed
        top_layout.addWidget(self.base_dir_label)

        self.base_dir_button = QPushButton("ベースディレクトリ選択...")
        self.base_dir_button.clicked.connect(self.select_base_directory)
        top_layout.addWidget(self.base_dir_button)
        
        # メインレイアウトに追加
        main_layout.addLayout(top_layout)
        
        # スプリッター（左: テーブルビュー, 右: 動画再生領域）
        splitter = QSplitter(Qt.Horizontal)
        
        # 左側のテーブルビュー
        self.scene_table_widget = QTableWidget()
        self.scene_table_widget.setColumnCount(8) # Columns: Select, File, Scene, Start, End, Desc Len, Trans Len, Scene Len
        self.scene_table_widget.setHorizontalHeaderLabels(["選択", "ファイル", "シーン", "開始", "終了", "説明文字数", "文字起こし文字数", "シーン長(秒)"])
        self.scene_table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scene_table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.scene_table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers) # Disable editing
        # Adjust column widths
        header = self.scene_table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # File
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Scene ID
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Start
        header.setSectionResizeMode(4, QHeaderView.Stretch) # End stretches
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Desc Len
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Trans Len
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents) # Scene Len
        self.scene_table_widget.cellClicked.connect(self.on_table_cell_clicked)
        
        # 右側のウィジェット（動画プレーヤーとシーン情報）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # ビデオプレーヤー
        self.video_player = VideoPlayer()
        
        # シーン情報パネル
        self.scene_info_panel = SceneInfoPanel()
        
        # 右側レイアウトに追加
        right_layout.addWidget(self.video_player, 3)  # 比率3
        right_layout.addWidget(self.scene_info_panel, 2)  # 比率2
        
        # スプリッターに追加
        splitter.addWidget(self.scene_table_widget) # Add TableWidget to the left
        splitter.addWidget(right_widget)
        
        # スプリッターの初期サイズ比率を設定
        splitter.setSizes([400, 800])
        
        # --- Left Panel Bottom Controls ---
        left_bottom_layout = QHBoxLayout()
        self.delete_scene_button = QPushButton("選択したシーンを削除")
        self.delete_scene_button.clicked.connect(self.delete_selected_scenes)
        self.play_sequential_button = QPushButton("連続再生")
        self.play_sequential_button.clicked.connect(self.play_selected_sequentially)
        left_bottom_layout.addWidget(self.delete_scene_button)
        left_bottom_layout.addWidget(self.play_sequential_button)
        left_bottom_layout.addStretch() # Add stretch to push button to the left

        # Combine table and bottom controls in a vertical layout for the left side
        left_panel_layout = QVBoxLayout()
        left_panel_layout.addWidget(self.scene_table_widget)
        left_panel_layout.addLayout(left_bottom_layout)

        # Create a widget to hold the left panel layout
        left_panel_widget = QWidget()
        left_panel_widget.setLayout(left_panel_layout)

        # Add the left and right panels to the splitter
        splitter.addWidget(left_panel_widget)
        splitter.addWidget(right_widget)
        
        # メインレイアウトに追加
        main_layout.addWidget(splitter)
        
        # ステータスバー
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        # Updated initial message as DB is loaded automatically
        self.statusBar.showMessage("ベースディレクトリを選択してください")

        if os.path.exists(self.db_path):
            self.load_database(self.db_path)
            # Connect player signal after player is potentially initialized - REMOVED FROM HERE
            # self.video_player.playbackFinished.connect(self.play_next_in_playlist)
        else:
             QMessageBox.critical(self, "エラー", f"固定データベースファイルが見つかりません:\n{self.db_path}")
             self.statusBar.showMessage("エラー: データベースファイルが見つかりません")
        
    def select_base_directory(self):
        """ベースディレクトリを選択"""
        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(
            self,
            "ベースディレクトリを選択",
            self.base_dir if self.base_dir else "", # Start from current base_dir if set
            options=options
        )

        if directory:
            self.base_dir = directory
            self.base_dir_label.setText(f"ベースディレクトリ: {self.base_dir}")
            self.update_status_bar() # Use a helper function for status updates
            # Always repopulate the tree view after selecting a base directory
            # as thumbnail paths might become valid.
            self.populate_scene_table()

    def load_database(self, db_path):
        """
        データベースを読み込む
        
        Args:
            db_path (str): データベースファイルのパス
        """
        # 既存の接続を閉じる
        if self.db_manager:
            self.db_manager.close()
            
        # データベースマネージャーを初期化
        print("Initializing DB Manager...") # Added print
        self.db_manager = DatabaseManager(db_path)

        # データベースに接続
        print("Connecting to DB...") # Added print
        if not self.db_manager.connect():
            print("DB Connection failed.") # Added print
            QMessageBox.critical(self, "エラー", "データベースに接続できませんでした")
            self.db_manager = None # Reset if connection fails
            return # Stop if connection fails

        print("DB Connection successful.") # Added print
        # データベースパスを保存
        self.db_path = db_path

        # Pass the valid db_manager to the panel
        if hasattr(self, 'scene_info_panel') and self.scene_info_panel:
             self.scene_info_panel.set_db_manager(self.db_manager)
        else:
             print("Error: Scene info panel not available when setting db manager.")

        # Load videos / populate tree
        print("Calling populate_scene_table from load_database...")
        self.populate_scene_table()

        # ステータスバーを更新
        print("Updating status bar...") # Added print
        self.update_status_bar()
        print("load_database finished.") # Added print
        
    def populate_scene_table(self):
        """データベース情報に基づいてシーンテーブルを構築する"""
        print("Populating scene table...") # Check if method is called
        if not self.db_manager:
            print("  DB Manager not available.")
            return

        self.scene_table_widget.clearContents() # Use clearContents for better visual clearing
        self.scene_table_widget.setRowCount(0)    # Ensure row count is also reset
        self.scene_table_widget.setSortingEnabled(False) # Disable sorting during population

        all_scenes = self.db_manager.get_all_scenes() # Get all scenes at once
        print(f"  Found {len(all_scenes)} total scenes.")

        # Sort scenes maybe by video_id then scene_id?
        all_scenes.sort(key=lambda s: (s.get('video_id', ''), s.get('scene_id', 0)))

        self.scene_table_widget.setRowCount(len(all_scenes))

        for row_idx, scene in enumerate(all_scenes):
            # --- Column 0: Checkbox --- 
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Unchecked)
            self.scene_table_widget.setItem(row_idx, 0, chk_item)

            # --- Column 1: File ID --- 
            # Use NumericTableWidgetItem, assuming File ID might be sortable numerically if prefix is removed?
            # Or, if File ID is purely alphanumeric, standard sort might be better. Let's try Numeric first.
            file_id_str = scene.get('video_id', '?')
            file_item = NumericTableWidgetItem(file_id_str)
            self.scene_table_widget.setItem(row_idx, 1, file_item)

            # --- Column 2: Scene ID --- 
            # Use NumericTableWidgetItem for Scene ID
            scene_id_str = str(scene.get('scene_id', '?'))
            scene_id_item = NumericTableWidgetItem(scene_id_str)
            self.scene_table_widget.setItem(row_idx, 2, scene_id_item)

            # --- Column 3: Start Time --- 
            start_item = QTableWidgetItem(self.format_seconds(scene.get('time_in', 0)))
            self.scene_table_widget.setItem(row_idx, 3, start_item)

            # --- Column 4: End Time --- 
            end_item = QTableWidgetItem(self.format_seconds(scene.get('time_out', 0)))
            self.scene_table_widget.setItem(row_idx, 4, end_item)

            # --- Column 5: Description Length --- 
            desc_len = len(scene.get('description', '') or '') # Handle None or empty string
            desc_len_item = NumericTableWidgetItem(str(desc_len)) 
            desc_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter) # Align right
            self.scene_table_widget.setItem(row_idx, 5, desc_len_item)

            # --- Column 6: Transcript Length --- 
            trans_len = len(scene.get('transcript', '') or '') # Handle None or empty string
            trans_len_item = NumericTableWidgetItem(str(trans_len)) 
            trans_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter) # Align right
            self.scene_table_widget.setItem(row_idx, 6, trans_len_item)

            # --- Column 7: Scene Length (Duration) --- 
            # Duration is already calculated in get_all_scenes
            scene_duration = scene.get('duration', 0)
            # Format duration to show seconds with milliseconds
            duration_str = f"{scene_duration:.3f}" 
            scene_len_item = NumericTableWidgetItem(duration_str)
            scene_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter) # Align right
            self.scene_table_widget.setItem(row_idx, 7, scene_len_item)

            # Store the full scene data in the row (e.g., in the first item)
            chk_item.setData(Qt.UserRole + 1, scene)
            # You could also store it per row using vertical headers, but this is simpler

        self.scene_table_widget.setSortingEnabled(True) # Re-enable sorting

    def on_table_cell_clicked(self, row, column):
        """テーブルセルクリック時のハンドラ"""
        print(f"Table cell clicked: row={row}, col={column}")

        # Get the checkbox item (column 0) to retrieve the scene data
        item = self.scene_table_widget.item(row, 0) 
        if not item:
            print("  Could not get item from row.")
            return

        scene_data = item.data(Qt.UserRole + 1)
        if not scene_data:
            print("  Item has no scene data.")
            return

        print(f"  Scene data found: {scene_data.get('video_id')} - Scene {scene_data.get('scene_id')}")

        # 現在のシーン情報を更新
        self.current_scene = scene_data
        
        # シーン情報パネルを更新
        self.scene_info_panel.update_info(scene_data)
        
        # 動画を読み込む
        self.load_video_for_scene(scene_data)
        
        # ステータスバーを更新
        self.update_status_bar(f"シーン選択: {scene_data.get('video_id','?')} - シーン {scene_data.get('scene_id','?')}")
        
    def load_video_for_scene(self, scene_data):
        """
        シーンに対応する動画を読み込む
        
        Args:
            scene_data (dict): シーン情報
        """
        if not scene_data:
            return
            
        if not self.base_dir:
             QMessageBox.warning(self, "警告", "動画を読み込むにはベースディレクトリを選択してください。")
             return

        # キーフレームパスを取得
        keyframe_path = scene_data.get('keyframe_path', '')
        
        if not keyframe_path:
            QMessageBox.warning(self, "警告", "キーフレーム画像のパスがありません")
            return
            
        # Windowsスタイルのパスをシステムに合わせて変換
        keyframe_path = keyframe_path.replace('\\', os.path.sep)
        
        # 完全なパスを構築
        full_keyframe_path = os.path.join(self.base_dir, keyframe_path)
        
        # キーフレーム画像が存在するか確認
        if not os.path.exists(full_keyframe_path):
            QMessageBox.warning(self, "警告", f"キーフレーム画像が見つかりません: {full_keyframe_path}")
            return
            
        # プレビューパスを取得
        preview_path = scene_data.get('preview_path', '')
        
        # 実際の動画ファイルがない場合は、キーフレーム画像を表示する代替処理
        # ここでは、キーフレーム画像のパスを元に動画ファイルのパスを推測
        
        # 元の動画ファイルのパスを取得（データベースから）
        if self.db_manager:
            videos = self.db_manager.get_videos()
            # Get video_id from the scene data
            current_video_id = scene_data.get('video_id')
            if not current_video_id:
                print("Error: Scene data missing video_id")
                return

            video_data = next((v for v in videos if v['video_id'] == current_video_id), None)
            
            if video_data and video_data.get('source_filepath'):
                source_filepath = video_data.get('source_filepath')
                
                # Windowsスタイルのパスをシステムに合わせて変換
                source_filepath = source_filepath.replace('\\', os.path.sep)
                
                # 完全なパスを構築
                full_video_path = os.path.join(self.base_dir, source_filepath)
                print(f"Attempting to load video: {full_video_path}") # Log attempt

                # 動画ファイルが存在するか確認
                if os.path.exists(full_video_path):
                    # 動画を読み込む
                    print(f"Video file found. Loading...")
                    if self.video_player.load_video(full_video_path):
                        print("Video loaded successfully.")
                        # シーンの開始時間と終了時間を取得 (ミリ秒)
                        start_ms = int(scene_data.get('time_in', 0) * 1000)
                        end_ms = int(scene_data.get('time_out', 0) * 1000)

                        # 再生範囲を設定
                        self.video_player.set_playback_range(start_ms, end_ms)

                        # 自動再生
                        self.video_player.play_pause()

                        return # Success!
                    else:
                        # load_videoがFalseを返した場合
                        error_msg = self.video_player.media_player.errorString()
                        print(f"Failed to load video. Error: {error_msg}")
                        QMessageBox.warning(
                            self,
                            "警告",
                            f"動画ファイルの読み込みに失敗しました。\nError: {error_msg}\nファイル: {full_video_path}"
                        )
                        return
                else:
                    # ファイルが存在しない場合
                    print(f"Video file not found at: {full_video_path}")
                    QMessageBox.warning(
                        self,
                        "警告",
                        f"動画ファイルが見つかりません。\nパス: {full_video_path}\nデータベースの source_filepath とベースディレクトリを確認してください。"
                    )
                    return

        # video_data がない、または source_filepath がない場合
        print("Video source filepath not found in database for current video ID.")
        QMessageBox.warning(
            self,
            "警告",
            f"現在の動画 ({self.current_video_id}) の source_filepath がデータベースに見つかりません。"
        )
        
        # 代替として、キーフレーム画像を表示する処理を追加することも可能
        
    def format_seconds(self, seconds):
        """秒数を時間形式 HH:MM:SS.mmm に変換"""
        if seconds is None or seconds < 0:
            return "00:00:00.000"
        # Calculate hours, minutes, seconds, and milliseconds
        total_milliseconds = int(seconds * 1000)
        milliseconds = total_milliseconds % 1000
        total_seconds = total_milliseconds // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"

    def update_status_bar(self, message=""):
        """ステータスバーのメッセージを更新するヘルパー関数"""
        if not self.db_manager:
            status = "データベースを選択してください"
        elif not self.base_dir:
            status = "ベースディレクトリを選択してください"
        else:
            status = f"準備完了 (DB: {os.path.basename(self.db_path)}, DIR: {os.path.basename(self.base_dir)})"

        if message:
            self.statusBar.showMessage(f"{message} | {status}")
        else:
            self.statusBar.showMessage(status)

    def closeEvent(self, event):
        """
        ウィンドウを閉じる際のイベントハンドラ
        
        Args:
            event: クローズイベント
        """
        # データベース接続を閉じる
        if self.db_manager:
            self.db_manager.close()
        
        # イベントを受け入れる
        event.accept()

    def delete_selected_scenes(self):
        """テーブルでチェックされたシーンを削除する"""
        if not self.db_manager:
            QMessageBox.warning(self, "警告", "データベースが接続されていません。")
            return

        selected_scenes = []
        for row in range(self.scene_table_widget.rowCount()):
            chk_item = self.scene_table_widget.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                scene_data = chk_item.data(Qt.UserRole + 1)
                if scene_data:
                    selected_scenes.append(scene_data)

        if not selected_scenes:
            QMessageBox.information(self, "情報", "削除するシーンが選択されていません。")
            return

        reply = QMessageBox.question(self, "確認",
                                   f"{len(selected_scenes)} 件のシーンをデータベースから削除しますか？\nこの操作は元に戻せません。",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            deleted_count = 0
            errors = []
            for scene in selected_scenes:
                video_id = scene.get('video_id')
                scene_id = scene.get('scene_id')
                if video_id and scene_id is not None:
                    if self.db_manager.delete_scene(video_id, scene_id):
                        deleted_count += 1
                        print(f"Deleted scene: {video_id} - {scene_id}")
                    else:
                        errors.append(f"{video_id} - {scene_id}")

            if errors:
                QMessageBox.warning(self, "削除エラー",
                                    f"{deleted_count} 件のシーンを削除しました。\n以下のシーンの削除中にエラーが発生しました:\n" +
                                    "\n".join(errors))
            else:
                QMessageBox.information(self, "削除完了", f"{deleted_count} 件のシーンを削除しました。")

            # テーブルを再読み込みする代わりに、削除された行をテーブルウィジェットから直接削除
            # populate_scene_table()
            # 後ろからループして行を削除（インデックスがずれないように）
            rows_to_delete = sorted([row for row in range(self.scene_table_widget.rowCount()) 
                                   if self.scene_table_widget.item(row, 0).checkState() == Qt.Checked], reverse=True)
            for row in rows_to_delete:
                # Check if the deleted scene matches the data in the row before removing
                chk_item = self.scene_table_widget.item(row, 0)
                scene_data_in_row = chk_item.data(Qt.UserRole + 1)
                # Find the corresponding deleted scene (simple check, might need improvement if IDs aren't unique across videos initially)
                scene_deleted_in_db = any(s.get('video_id') == scene_data_in_row.get('video_id') and \
                                         s.get('scene_id') == scene_data_in_row.get('scene_id') for s in selected_scenes)
                
                if scene_deleted_in_db:
                    self.scene_table_widget.removeRow(row)
            
            # クリア情報パネルとプレーヤー（遅延実行）
            print("  Scheduling clear_player_and_info from end of playlist.") # Log call
            QTimer.singleShot(50, self.clear_player_and_info) # Delay clearing

    def clear_player_and_info(self):
        """プレーヤーとシーン情報パネルをクリアするヘルパースロット"""
        print("Clearing player and info panel after delay...")
        # Check if player exists before stopping/loading
        if not self.video_player:
             print("  Video player already gone.")
             return
        self.current_scene = None
        self.scene_info_panel.clear()
        print("  Calling video_player.stop()")
        self.video_player.stop()
        print("  Calling video_player.set_media(None)")
        self.video_player.set_media(None) # Release the media object
        print("  Finished clearing player and info.")

    def play_selected_sequentially(self):
        """チェックされたシーンをテーブルの表示順に連続再生する。
        現在選択されている行にチェックが入っていれば、そこから開始する。
        """
        if not self.db_manager:
            QMessageBox.warning(self, "警告", "データベースが接続されていません。")
            return

        checked_scenes_playlist = []
        # テーブルの現在の表示順（ソートされている可能性も考慮）で行を取得
        # QTableWidgetでは単純にrow indexで良い
        for row in range(self.scene_table_widget.rowCount()):
            chk_item = self.scene_table_widget.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                scene_data = chk_item.data(Qt.UserRole + 1)
                if scene_data:
                    # Store row index along with scene data
                    checked_scenes_playlist.append({'data': scene_data, 'row': row})

        if not checked_scenes_playlist:
            QMessageBox.information(self, "情報", "連続再生するシーンが選択されていません。")
            self.playback_playlist = None
            self.current_playlist_index = -1
            return

        # 現在選択されている行を取得
        current_selected_row = self.scene_table_widget.currentRow()
        print(f"DEBUG: Current selected row index: {current_selected_row}") # Debug print
        start_playlist_index = 0 # デフォルトは最初のチェック項目から

        # 選択されている行がチェック済みリストに含まれているか確認
        found_selected_in_checked = False
        if current_selected_row >= 0:
            selected_item_widget = self.scene_table_widget.item(current_selected_row, 0)
            if selected_item_widget and selected_item_widget.checkState() == Qt.Checked:
                print(f"DEBUG: Selected row {current_selected_row} is checked.") # Debug print
                # 選択行がチェックされていた場合、そのシーンがプレイリストの何番目かを探す
                selected_scene_data = selected_item_widget.data(Qt.UserRole + 1)
                if selected_scene_data:
                    print(f"DEBUG: Selected scene data: {selected_scene_data.get('video_id')} - {selected_scene_data.get('scene_id')}") # Debug print
                    for idx, item_in_playlist in enumerate(checked_scenes_playlist):
                        # print(f"DEBUG: Checking playlist item {idx}: {item_in_playlist['data']}") # Very verbose
                        # video_id と scene_id で一致を確認 (より確実に)
                        if (item_in_playlist['data'].get('video_id') == selected_scene_data.get('video_id') and
                            item_in_playlist['data'].get('scene_id') == selected_scene_data.get('scene_id')):
                            start_playlist_index = idx
                            found_selected_in_checked = True
                            print(f"DEBUG: Match found in playlist at index {idx}. Setting start index.") # Debug print
                            break
                    if not found_selected_in_checked:
                        print("DEBUG: Selected scene data not found in checked_scenes_playlist.") # Debug print
                else:
                     print("DEBUG: Could not retrieve scene data from selected item.") # Debug print
            else:
                 print(f"DEBUG: Selected row {current_selected_row} is NOT checked or item widget is None.") # Debug print
        else:
             print("DEBUG: No row selected (currentRow is < 0).") # Debug print

        if not found_selected_in_checked:
             print(f"INFO: Starting playback from the first checked item (index 0). Reason: Selected row {current_selected_row} not checked or not found in playlist.") # Modified log

        # プレイリストと開始インデックスを設定
        self.playback_playlist = checked_scenes_playlist
        self.current_playlist_index = start_playlist_index

        print(f"DEBUG: Final start_playlist_index = {start_playlist_index}") # Debug print
        print(f"DEBUG: Setting self.current_playlist_index = {self.current_playlist_index}") # Debug print

        print(f"Starting sequential playback with {len(self.playback_playlist)} scenes from playlist index {self.current_playlist_index}.")

        # 最初のシーン（開始インデックスのシーン）を読み込んで再生
        # Check if playlist is valid and index is within bounds
        if self.playback_playlist and 0 <= self.current_playlist_index < len(self.playback_playlist):
            start_item = self.playback_playlist[self.current_playlist_index]
            # 既存のクリックハンドラを呼び出して再生開始
            self.on_table_cell_clicked(start_item['row'], 0)
            # 最初の行をハイライト
            self.highlight_playing_row(start_item['row'])
            self.update_status_bar(
                f"連続再生中 ({self.current_playlist_index + 1}/{len(self.playback_playlist)}) - シーン {start_item['data']['scene_id']}"
            )
        else:
            print(f"ERROR: Invalid start index ({self.current_playlist_index}) or empty playlist.")
            QMessageBox.warning(self, "エラー", "連続再生の開始に失敗しました。")
            self.playback_playlist = None
            self.current_playlist_index = -1

    def play_next_in_playlist(self):
        """プレイリストの次のシーンを再生する (playbackFinishedシグナルから呼び出される)"""
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!") # ADDED
        print("!!! play_next_in_playlist SLOT ENTERED !!!") # ADDED
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!") # ADDED
        print(f"  Playlist object: {self.playback_playlist}") # ADDED
        print(f"  Current playlist index: {self.current_playlist_index}") # ADDED
        # print(f"play_next_in_playlist called. Current index: {self.current_playlist_index}") # Log entry - Replaced

        if self.playback_playlist is None or self.current_playlist_index < 0:
            print("  No active playlist or index invalid. Returning.") # Modified log
            return # Not in sequential playback mode

        # Unhighlight previous row (optional)
        self.highlight_playing_row(-1)

        next_index = self.current_playlist_index + 1
        print(f"  Checking for next index: {next_index} against playlist length: {len(self.playback_playlist)}") # Log check

        if next_index < len(self.playback_playlist):
            self.current_playlist_index = next_index # Increment index here
            next_item = self.playback_playlist[self.current_playlist_index]
            print(f"  Playing next scene: index={self.current_playlist_index}, scene_id={next_item['data']['scene_id']}")
            # Load and play the next scene
            self.on_table_cell_clicked(next_item['row'], 0) # Simulate click
            # Highlight the new playing row (optional)
            self.highlight_playing_row(next_item['row'])
            self.update_status_bar(f"連続再生中 ({self.current_playlist_index + 1}/{len(self.playback_playlist)}) - シーン {next_item['data']['scene_id']}")
        else:
            print(f"  Playlist finished. Reached index {next_index}.") # Log finished
            # Show message first, then cleanup *after* the event loop gets a chance
            QMessageBox.information(self, "連続再生完了", "プレイリストの最後まで再生しました。")
            print("  Playlist finished. Leaving last scene paused.")
            # Do not call clear_player_and_info to avoid stop()/set_media(None) errors.
            # The last scene remains paused.
            self.update_status_bar("連続再生完了")
            # Reset playlist state
            self.playback_playlist = None
            self.current_playlist_index = -1

    def highlight_playing_row(self, playing_row):
        """指定された行をハイライトし、他の行のハイライトを解除する。\n        また、ハイライトされた行が表示されるようにスクロールする。"""
        item_to_scroll_to = None
        for row in range(self.scene_table_widget.rowCount()):
            is_playing = (row == playing_row)
            color = QColor(200, 255, 200) if is_playing else self.scene_table_widget.palette().base().color()
            for col in range(self.scene_table_widget.columnCount()):
                item = self.scene_table_widget.item(row, col)
                if item:
                    item.setBackground(color)
                    if is_playing and col == 0: # Use the item from the first column for scrolling
                        item_to_scroll_to = item

        # Scroll to the highlighted item if it exists
        if item_to_scroll_to:
            print(f"Scrolling to row {playing_row}, item text: {item_to_scroll_to.text()}") # Debug print
            # self.scene_table_widget.scrollToItem(item_to_scroll_to, QAbstractItemView.ScrollHint.PositionAtCenter)
            self.scene_table_widget.scrollToItem(item_to_scroll_to, QAbstractItemView.ScrollHint.EnsureVisible) # Try EnsureVisible
        else:
            if playing_row != -1:
                 print(f"Warning: Could not find item to scroll to for row {playing_row}") # Debug print

    def on_scene_data_updated(self, updated_scene_data):
        """シーン情報が更新されたときにテーブルの文字数を更新するスロット"""
        print("on_scene_data_updated called")
        video_id = updated_scene_data.get('video_id')
        scene_id = updated_scene_data.get('scene_id')
        if video_id is None or scene_id is None:
            return

        new_desc_len = len(updated_scene_data.get('description', '') or '')
        new_trans_len = len(updated_scene_data.get('transcript', '') or '')

        # Find the corresponding row in the table and update length columns
        for row in range(self.scene_table_widget.rowCount()):
            chk_item = self.scene_table_widget.item(row, 0)
            if chk_item:
                row_scene_data = chk_item.data(Qt.UserRole + 1)
                if (row_scene_data and 
                    row_scene_data.get('video_id') == video_id and 
                    row_scene_data.get('scene_id') == scene_id):
                    
                    desc_len_item = self.scene_table_widget.item(row, 5)
                    if desc_len_item:
                        desc_len_item.setText(str(new_desc_len))
                    else: # Create item if it doesn't exist (shouldn't happen normally)
                        desc_len_item = NumericTableWidgetItem(str(new_desc_len))
                        desc_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        self.scene_table_widget.setItem(row, 5, desc_len_item)
                        
                    trans_len_item = self.scene_table_widget.item(row, 6)
                    if trans_len_item:
                        trans_len_item.setText(str(new_trans_len))
                    else:
                        trans_len_item = NumericTableWidgetItem(str(new_trans_len))
                        trans_len_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        self.scene_table_widget.setItem(row, 6, trans_len_item)

                    print(f"Updated table lengths for {video_id}-{scene_id} at row {row}")
                    # Update the stored data in the table item as well
                    chk_item.setData(Qt.UserRole + 1, updated_scene_data)                    
                    break # Found the row, no need to continue searching

# アプリケーションのメイン関数
def main():
    app = QApplication(sys.argv)
    
    # スタイルシートを設定（オプション）
    app.setStyle("Fusion")
    
    # メインウィンドウを作成
    window = VideoPreviewApp()
    window.show()
    
    # コマンドライン引数でデータベースファイルを指定可能
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        # Check if the argument is a database file
        if sys.argv[1].lower().endswith('.db'):
             print(f"Loading database from command line: {sys.argv[1]}")
             window.load_database(sys.argv[1])
        else:
             print(f"Command line argument ignored (not a .db file): {sys.argv[1]}")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
