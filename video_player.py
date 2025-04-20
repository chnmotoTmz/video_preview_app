# video_player.py の変更案 (抜粋ではなく全体)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import platform
import vlc  # vlcライブラリをインポート
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QSlider, QLabel, QSizePolicy, QStyle,
                            QFrame, QMessageBox) # QVideoWidgetの代わりにQFrameを使用
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QIcon, QPalette, QColor

# VLCイベントをPyQtシグナルに変換するためのヘルパークラス
class VlcEventManager(QWidget):
    positionChanged = pyqtSignal(float)
    durationChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(int)
    errorOccurred = pyqtSignal()

    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        self.event_manager = player.event_manager()
        self._register_events()

    def _register_events(self):
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPositionChanged, self._handle_position_changed)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerLengthChanged, self._handle_length_changed)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._handle_state_changed)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._handle_state_changed)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._handle_state_changed)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._handle_state_changed)
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._handle_error)

    def _post_signal(self, method_name_str, *args):
         # Ensure signals are emitted in the main Qt thread
         # Pass the method name as a string
         # print(f"Invoking method: {method_name_str} with args: {args}") # Debug print (optional)
         QMetaObject.invokeMethod(self, method_name_str, Qt.QueuedConnection, *[Q_ARG(type(arg), arg) for arg in args])

    def _handle_position_changed(self, event):
        # event.u.new_position は float (0.0 to 1.0)
        self._post_signal("onPositionChanged", event.u.new_position) # Call slot by name

    def _handle_length_changed(self, event):
        # event.u.new_length は int (milliseconds)
        self._post_signal("onDurationChanged", event.u.new_length) # Call slot by name

    def _handle_state_changed(self, event):
        new_state = self.player.get_state()
        self._post_signal("onStateChanged", new_state.value) # Call slot by name

    def _handle_error(self, event):
        self._post_signal("onErrorOccurred") # Call slot by name

    # Slots to actually emit the signals in the main thread
    @pyqtSlot(float)
    def onPositionChanged(self, value):
        self.positionChanged.emit(value)

    @pyqtSlot(int)
    def onDurationChanged(self, value):
        self.durationChanged.emit(value)

    @pyqtSlot(int)
    def onStateChanged(self, value):
        self.stateChanged.emit(value)

    @pyqtSlot()
    def onErrorOccurred(self):
        self.errorOccurred.emit()

    def detach_events(self):
        self.event_manager.event_detach(vlc.EventType.MediaPlayerPositionChanged)
        self.event_manager.event_detach(vlc.EventType.MediaPlayerLengthChanged)
        self.event_manager.event_detach(vlc.EventType.MediaPlayerPlaying)
        self.event_manager.event_detach(vlc.EventType.MediaPlayerPaused)
        self.event_manager.event_detach(vlc.EventType.MediaPlayerStopped)
        self.event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
        self.event_manager.event_detach(vlc.EventType.MediaPlayerEncounteredError)


class VideoPlayer(QWidget):
    """VLCを使用したビデオプレーヤーコンポーネント"""
    playStateChanged = pyqtSignal(bool)  # True: 再生中, False: 停止/一時停止
    playbackFinished = pyqtSignal()      # 再生が正常に終了したときに発行されるシグナル

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_scene_end_time_ms = -1 # 再生停止時間 (ミリ秒)
        self.pending_start_time_ms = -1   # 再生開始時にシークする時間
        self.media_parsed = False         # メディアの長さが取得できたか

        # VLCインスタンスとプレーヤーの作成
        try:
            # --no-xlib is for Linux, --no-hwdec disables hardware decoding - Reverting options
            # vlc_options = ['--no-xlib', '--no-hwdec'] 
            # print(f"Initializing VLC instance with options: {vlc_options}")
            # self.vlc_instance = vlc.Instance(vlc_options)
            print("Initializing VLC instance with default options ('--no-xlib')...")
            self.vlc_instance = vlc.Instance('--no-xlib') # Reverted to simpler options
            if self.vlc_instance is None:
                # Explicitly raise an error if instance creation fails
                raise vlc.VLCException("Failed to create VLC instance. Returned None.")
            self.vlc_player = self.vlc_instance.media_player_new()
        except Exception as e:
            print(f"VLCの初期化に失敗しました: {e}")
            QMessageBox.critical(self, "VLCエラー", f"VLCの初期化に失敗しました。\nVLCメディアプレーヤーが正しくインストールされているか確認してください。\nエラー: {e}")
            # アプリケーションの続行が困難な場合は終了させるなどの処理が必要
            sys.exit(1) # または適切なエラーハンドリング

        # ビデオ表示用ウィジェット (QFrameを使用)
        self.video_widget = QFrame()
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 黒背景にする
        palette = self.video_widget.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.video_widget.setPalette(palette)
        self.video_widget.setAutoFillBackground(True)

        # 再生コントロールボタン (変更なし)
        self.play_button = QPushButton()
        self.play_button.setEnabled(False)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.play_pause)

        self.stop_button = QPushButton()
        self.stop_button.setEnabled(False)
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop)

        # シークスライダー (Rangeを0-1000に変更: VLCのPositionは0.0-1.0)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 1000) # 0 から 1000 (0.0% から 100.0%)
        self.position_slider.sliderMoved.connect(self.set_position_from_slider)
        self.position_slider.valueChanged.connect(self.update_time_label_from_slider) # スライダー操作中も時間更新

        # 時間表示ラベル (変更なし)
        self.time_label = QLabel("00:00:00 / 00:00:00")

        # 音量コントロール (変更なし)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)

        self.volume_label = QLabel()
        self.volume_label.setPixmap(self.style().standardPixmap(QStyle.SP_MediaVolume))

        # VLCイベントマネージャーの設定
        self.vlc_event_manager_widget = VlcEventManager(self.vlc_player)
        self.vlc_event_manager_widget.stateChanged.connect(self.media_state_changed)
        self.vlc_event_manager_widget.positionChanged.connect(self.position_changed)
        self.vlc_event_manager_widget.durationChanged.connect(self.duration_changed)
        self.vlc_event_manager_widget.errorOccurred.connect(self.handle_error)

        # UIレイアウト設定 (変更なし)
        self.setup_ui()

        # 初期音量設定
        self.set_volume(self.volume_slider.value())

        # ウィンドウハンドルをVLCに渡す (表示後に実行する必要がある場合がある)
        # self.vlc_player.set_hwnd(self.video_widget.winId()) # setup_uiの後やshowEventで行うのが確実

        # QTimerは不要になるかもしれない (VLCイベントでUI更新するため)
        # self.update_timer = QTimer(self)
        # self.update_timer.setInterval(100)
        # self.update_timer.timeout.connect(self.update_ui)

        self.time_label.setText("00:00:00 / 00:00:00")
        self.current_scene_end_time_ms = -1 # 停止時にもリセット
        self.pending_start_time_ms = -1   # 停止時に保留シークもリセット
        print("VLC: Stop called.")
        # Note: Don't emit finished signal here unconditionally

    def setup_ui(self):
        """UIレイアウトの設定"""
        layout = QVBoxLayout()
        layout.addWidget(self.video_widget) # QFrameを配置

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.position_slider)
        control_layout.addWidget(self.time_label)
        control_layout.addWidget(self.volume_label)
        control_layout.addWidget(self.volume_slider)

        layout.addLayout(control_layout)
        self.setLayout(layout)

    # ウィジェットが表示されたときにウィンドウハンドルを設定
    def showEvent(self, event):
        super().showEvent(event)
        # ここでウィンドウハンドルを設定するのがより確実
        try:
            if platform.system() == "Windows":
                self.vlc_player.set_hwnd(int(self.video_widget.winId()))
            elif platform.system() == "Darwin": # macOS
                # macOS では NSView を渡す必要があるかもしれない
                # ctypes を使って Objective-C の view を取得・設定する必要があり複雑
                # self.vlc_player.set_nsobject(int(self.video_widget.winId())) # 要検証
                print("macOSでのVLC描画は追加設定が必要な場合があります。")
                # 代替: 別ウィンドウで開く self.vlc_player.set_macho_view(int(self.video_widget.winId())) など
            else: # Linux
                 self.vlc_player.set_xwindow(int(self.video_widget.winId()))
        except Exception as e:
             print(f"VLCへのウィンドウハンドル設定に失敗: {e}")


    def load_video(self, video_path):
        """動画を読み込む"""
        if not video_path or not os.path.exists(video_path):
            print(f"動画ファイルが見つからないか無効です: {video_path}")
            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            # 以前のメディアをクリア
            self.vlc_player.set_media(None)
            self.time_label.setText("00:00:00 / 00:00:00")
            self.position_slider.setValue(0)
            return False

        try:
            # Windowsパスの区切り文字を修正 (VLCは通常気にしないが念のため)
            # video_path = video_path.replace('\\', '/') # 必要ない場合が多い
            media = self.vlc_instance.media_new(video_path)
            self.vlc_player.set_media(media)

            # ボタンを有効化
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            print(f"VLC: Loaded video {video_path}")
            self.media_parsed = False # Reset flag on new video load
            self.pending_start_time_ms = -1 # Reset pending seek too
            self.current_scene_end_time_ms = -1
            return True
        except Exception as e:
            print(f"VLCでの動画読み込みエラー: {e}")
            self.handle_error() # エラー処理を呼ぶ
            return False

    def play_pause(self):
        """再生/一時停止の切り替え"""
        state = self.vlc_player.get_state()
        if state == vlc.State.Playing:
            self.vlc_player.pause()
        else:
            # If there's a pending seek time, apply it before playing - REMOVED FROM HERE
            # if self.pending_start_time_ms >= 0:
            #    print(f"VLC: Applying pending seek to {self.pending_start_time_ms} ms before playing.")
            #    self.set_position(self.pending_start_time_ms)
            #    # Reset pending time so it only seeks once
            #    self.pending_start_time_ms = -1

            result = self.vlc_player.play()
            if result == -1:
                print("VLC: Playback failed.")
                self.handle_error()
            else:
                 print("VLC: Playing...")
            # 再生開始時に長さ取得を試みる（初回再生時に長さがわかることが多い）
            # length = self.vlc_player.get_length()
            # if length > 0:
            #    self.duration_changed(length)


    def stop(self):
        """停止"""
        self.vlc_player.stop()
        # 停止後、UIをリセット
        self.position_slider.setValue(0)
        self.time_label.setText("00:00:00 / 00:00:00")
        self.current_scene_end_time_ms = -1 # 停止時にもリセット
        self.pending_start_time_ms = -1   # 停止時に保留シークもリセット


    def set_position_from_slider(self, value):
        """スライダーの値に基づいて再生位置を設定"""
        # スライダーの値 (0-1000) を VLC の位置 (0.0-1.0) に変換
        position = value / 1000.0
        self.vlc_player.set_position(position)

    def set_position(self, position_ms):
        """再生位置をミリ秒で設定 (外部から呼び出される場合)"""
        print(f"VLC: Setting position to {position_ms} ms")
        result = self.vlc_player.set_time(position_ms)
        if result == -1:
            print("VLC: Failed to set time (seek).")
        # シーク後、スライダー位置も更新
        # length = self.get_duration()
        # if length > 0:
        #     pos_float = position_ms / length
        #     self.position_slider.setValue(int(pos_float * 1000))


    def set_volume(self, volume):
        """音量を設定 (0-100)"""
        self.vlc_player.audio_set_volume(volume)

    def media_state_changed(self, state_value):
        """VLC再生状態変更時のハンドラ"""
        state = vlc.State(state_value)
        print(f"VLC State Changed: {state}")
        if state == vlc.State.Playing:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.playStateChanged.emit(True)

            # --- Seek here after playback actually starts AND media is parsed --- 
            if self.pending_start_time_ms >= 0 and self.media_parsed:
                print(f"VLC: State=Playing, Parsed=True. Applying pending seek to {self.pending_start_time_ms} ms.")
                self.set_position(self.pending_start_time_ms)
                self.pending_start_time_ms = -1
            # ------------------------------------------------- 

        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.playStateChanged.emit(False)
            # 再生終了または停止時にスライダーをリセット
            if state == vlc.State.Ended or state == vlc.State.Stopped:
                # Emit finished signal only if the state is Ended
                if state == vlc.State.Ended:
                    print("VLC: Playback ended naturally.")
                    print("VLC: --> BEFORE Emitting playbackFinished (due to Ended state)") # Debug print
                    self.playbackFinished.emit()
                    print("VLC: <-- AFTER Emitting playbackFinished (due to Ended state)") # Debug print

                # 少し待ってからリセットしないと、最後のpositionChangedイベントと競合することがある
                QTimer.singleShot(100, lambda: self.position_slider.setValue(0))
                QTimer.singleShot(100, lambda: self.time_label.setText(f"00:00:00 / {self.format_time(self.get_duration())}"))


    def position_changed(self, position_float):
        """再生位置変更時のハンドラ (VLCイベントから)"""
        # position_float は 0.0 から 1.0
        # スライダーがユーザーによって操作されていない場合のみ更新
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(int(position_float * 1000))

        # --- time_out 停止処理 --- 
        if self.current_scene_end_time_ms > 0 and self.is_playing():
            current_ms = self.get_current_position()
            # 終了時間に達したら停止 (少し余裕を持たせる場合もある)
            if current_ms >= self.current_scene_end_time_ms:
                end_time_debug = self.current_scene_end_time_ms # Store before reset
                print(f"VLC: Reached end time {end_time_debug} ms (current: {current_ms} ms).")
                self.vlc_player.pause()
                print("VLC: Paused due to reaching end time.")
                self.current_scene_end_time_ms = -1
                print(f"VLC: --> BEFORE Emitting playbackFinished (end time: {end_time_debug}) end_time_ms reset.") # Debug print
                self.playbackFinished.emit()
                print(f"VLC: <-- AFTER Emitting playbackFinished (end time: {end_time_debug})") # Debug print
         # ------------------------- 
 
         # 時間表示は update_time_label で更新される (sliderの値変更シグナル経由 or 直接呼び出し)
        # self.update_time_label() # ここで直接呼んでも良い

    def update_time_label_from_slider(self, value):
         """スライダーの値に基づいて時間表示ラベルを更新"""
         # スライダーが編集中でもリアルタイムで更新
         current_time_ms = int((value / 1000.0) * self.get_duration())
         duration_ms = self.get_duration()
         self.time_label.setText(f"{self.format_time(current_time_ms)} / {self.format_time(duration_ms)}")


    def duration_changed(self, duration_ms):
        """動画の長さ変更時のハンドラ (VLCイベントから)"""
        print(f"VLC Duration Changed: {duration_ms} ms")
        # スライダーのRangeは変えない (0-1000のまま)
        # self.position_slider.setRange(0, duration_ms) # 不要
        # 時間表示を更新
        self.update_time_label_from_slider(self.position_slider.value())
        self.media_parsed = True # Mark media as parsed (duration known)
        # If player is already playing, attempt seek now
        if self.is_playing() and self.pending_start_time_ms >= 0:
             print(f"VLC: Duration Changed. Player already playing. Applying pending seek to {self.pending_start_time_ms} ms.")
             self.set_position(self.pending_start_time_ms)
             self.pending_start_time_ms = -1

    def format_time(self, milliseconds):
        """ミリ秒を時間形式に変換"""
        if milliseconds < 0: milliseconds = 0 # 時々マイナスになることがある
        seconds = milliseconds // 1000
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    # def update_ui(self): # QTimerを使う場合の定期更新
    #     """UIの定期更新"""
    #     if self.vlc_player.get_state() == vlc.State.Playing:
    #         pos = self.vlc_player.get_position() # 0.0-1.0
    #         if not self.position_slider.isSliderDown():
    #             self.position_slider.setValue(int(pos * 1000))
    #         # 時間表示更新
    #         self.update_time_label()

    def handle_error(self):
        """エラーハンドラ"""
        # VLCは具体的なエラー文字列を直接提供しないことが多い
        print("VLC メディアプレーヤーエラーが発生しました。")
        # 必要であれば、vlcログを確認するなどの処理
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        # UIリセット
        self.position_slider.setValue(0)
        self.time_label.setText("00:00:00 / 00:00:00")


    def get_current_position(self):
        """現在の再生位置を取得 (ミリ秒)"""
        return self.vlc_player.get_time() # ミリ秒を返す

    def get_duration(self):
        """動画の長さを取得 (ミリ秒)"""
        return self.vlc_player.get_length() # ミリ秒を返す

    def is_playing(self):
        """再生中かどうかを取得"""
        return self.vlc_player.get_state() == vlc.State.Playing

    def cleanup(self):
        """リソースの解放"""
        print("Cleaning up VLC player...")
        if self.vlc_player:
            self.vlc_player.stop()
            self.vlc_event_manager_widget.detach_events() # イベントのデタッチ
            # self.vlc_player.release() # releaseはInstance側で行う場合がある
            self.vlc_player = None
        if self.vlc_instance:
            self.vlc_instance.release()
            self.vlc_instance = None

    def set_playback_range(self, start_ms, end_ms):
        """再生範囲を設定 (ミリ秒)

        Args:
            start_ms (int): 再生開始時間 (ミリ秒)
            end_ms (int): 再生終了時間 (ミリ秒)
        """
        print(f"VLC: Setting playback range. Start: {start_ms} ms, End: {end_ms} ms")
        self.current_scene_end_time_ms = end_ms
        # Don't seek here, store it for when play starts
        self.pending_start_time_ms = start_ms
        # self.set_position(start_ms)

# VideoPlayerクラスのテスト用コード (変更の必要性は低いが確認)
if __name__ == "__main__":
    app = QApplication(sys.argv)

    player = VideoPlayer()
    player.setWindowTitle("VLC ビデオプレーヤーテスト")
    player.resize(800, 600)

    video_path = "/path/to/test/video.mp4" # 存在する動画ファイルに変更

    if len(sys.argv) > 1:
        video_path = sys.argv[1]

    if os.path.exists(video_path):
        player.load_video(video_path)
    else:
        print(f"警告: 動画ファイルが見つかりません: {video_path}")

    def on_play_state_changed(is_playing):
        state = "再生中" if is_playing else "停止/一時停止"
        print(f"再生状態: {state}")

    player.playStateChanged.connect(on_play_state_changed)
    player.show()

    # アプリケーション終了時にVLCリソースを解放
    app.aboutToQuit.connect(player.cleanup)

    sys.exit(app.exec_())
