import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
from create_database import VideoDatabase

# Database path (same as api_service.py)
DB_PATH = "video_data.db"

def run_import(folder_path, status_label, browse_button, import_button):
    """Runs the import process and updates the Tkinter GUI."""
    status_label.config(text="Importing... Please wait.")
    browse_button.config(state=tk.DISABLED)
    import_button.config(state=tk.DISABLED)

    db = None
    try:
        db = VideoDatabase(DB_PATH)
        db.connect()
        db.create_schema() # Ensure schema exists

        count, errors = db.import_ts_data(folder_path)

        result_message = f"Import completed. Imported {count} videos (metadata only)."
        if errors:
            error_details = "\n".join([f"- {error}" for error in errors])
            messagebox.showerror("Import Errors", f"{result_message}\n\nErrors encountered:\n{error_details}")
        else:
            messagebox.showinfo("Import Successful", result_message)
        status_label.config(text="Import finished. See message box for details.")

    except Exception as e:
        messagebox.showerror("Import Error", f"An unexpected error occurred: {e}")
        status_label.config(text=f"An unexpected error occurred: {e}")
    finally:
        if db:
            db.close()
        browse_button.config(state=tk.NORMAL)
        import_button.config(state=tk.NORMAL)

def browse_folder(folder_entry):
    """Opens folder dialog and updates the entry field."""
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        folder_entry.config(state=tk.NORMAL)
        folder_entry.delete(0, tk.END)
        folder_entry.insert(0, folder_selected)
        folder_entry.config(state='readonly') # Make readonly again after insert
        # Enable import button only if folder is selected
        import_button.config(state=tk.NORMAL)
    else:
        import_button.config(state=tk.DISABLED)

# --- Main Application Setup ---
def main():
    root = tk.Tk()
    root.title("Video Data Importer")

    # Frame for folder selection
    folder_frame = ttk.Frame(root, padding="10")
    folder_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

    ttk.Label(folder_frame, text="Select parent directory containing the '_captures' folders:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
    folder_path_var = tk.StringVar()
    folder_entry = ttk.Entry(folder_frame, textvariable=folder_path_var, width=50, state='readonly')
    folder_entry.grid(row=1, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))

    global browse_button # Make browse_button global for run_import
    browse_button = ttk.Button(folder_frame, text="Browse...", command=lambda: browse_folder(folder_entry))
    browse_button.grid(row=1, column=1, padx=5, pady=5)

    # Frame for import button and status
    action_frame = ttk.Frame(root, padding="10")
    action_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

    global import_button # Make import_button global
    import_button = ttk.Button(
        action_frame, 
        text="Import Data", 
        state=tk.DISABLED, # Initially disabled
        command=lambda: threading.Thread(
            target=run_import, 
            args=(folder_path_var.get(), status_label, browse_button, import_button),
            daemon=True
        ).start() # Pass necessary widgets
    )
    import_button.pack(pady=10)

    status_label = ttk.Label(action_frame, text="Select a parent directory containing '_captures' folders.", wraplength=400)
    status_label.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main() # Run the main function 