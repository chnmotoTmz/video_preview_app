import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
from create_database import VideoDatabase

# Database path (same as api_service.py)
DB_PATH = "video_data.db"

def run_import(folder_path, status_label, browse_button, import_button):
    """Runs the import process and updates the Tkinter GUI."""
    status_label.config(text="データベースを初期化中...")
    browse_button.config(state=tk.DISABLED)
    import_button.config(state=tk.DISABLED)

    db = None
    try:
        # データベースファイルが存在する場合は削除
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            status_label.config(text="既存のデータベースを削除しました。")

        db = VideoDatabase(DB_PATH)
        db.connect()
        
        # スキーマを作成（テーブルも初期化される）
        status_label.config(text="新しいデータベースを作成中...")
        db.create_schema()

        # データのインポート
        status_label.config(text="データをインポート中...")
        count, errors = db.import_ts_data(folder_path)

        result_message = f"インポート完了。{count}件の動画をインポートしました。"
        if errors:
            error_details = "\n".join([f"- {error}" for error in errors])
            messagebox.showerror("インポートエラー", f"{result_message}\n\nエラー:\n{error_details}")
        else:
            messagebox.showinfo("インポート成功", result_message)
        status_label.config(text="インポート完了。メッセージボックスで詳細を確認してください。")

    except Exception as e:
        messagebox.showerror("エラー", f"予期せぬエラーが発生しました: {e}")
        status_label.config(text=f"エラー: {e}")
    finally:
        if db:
            db.close()
        browse_button.config(state=tk.NORMAL)
        import_button.config(state=tk.NORMAL)

def browse_folder(folder_entry):
    """フォルダ選択ダイアログを開き、エントリーフィールドを更新します。"""
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        folder_entry.config(state=tk.NORMAL)
        folder_entry.delete(0, tk.END)
        folder_entry.insert(0, folder_selected)
        folder_entry.config(state='readonly')  # 入力後に読み取り専用に戻す
        # フォルダが選択された場合のみインポートボタンを有効化
        import_button.config(state=tk.NORMAL)
    else:
        import_button.config(state=tk.DISABLED)

# --- メインアプリケーションのセットアップ ---
def main():
    root = tk.Tk()
    root.title("動画データインポーター")

    # フォルダ選択用フレーム
    folder_frame = ttk.Frame(root, padding="10")
    folder_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

    ttk.Label(folder_frame, text="'_captures'フォルダを含む親ディレクトリを選択してください:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
    folder_path_var = tk.StringVar()
    folder_entry = ttk.Entry(folder_frame, textvariable=folder_path_var, width=50, state='readonly')
    folder_entry.grid(row=1, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))

    global browse_button
    browse_button = ttk.Button(folder_frame, text="参照...", command=lambda: browse_folder(folder_entry))
    browse_button.grid(row=1, column=1, padx=5, pady=5)

    # インポートボタンとステータス用フレーム
    action_frame = ttk.Frame(root, padding="10")
    action_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

    global import_button
    import_button = ttk.Button(
        action_frame, 
        text="データをインポート", 
        state=tk.DISABLED,  # 初期状態は無効
        command=lambda: threading.Thread(
            target=run_import, 
            args=(folder_path_var.get(), status_label, browse_button, import_button),
            daemon=True
        ).start()
    )
    import_button.pack(pady=10)

    status_label = ttk.Label(action_frame, text="'_captures'フォルダを含む親ディレクトリを選択してください。", wraplength=400)
    status_label.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main() 