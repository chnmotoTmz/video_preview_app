# Video Scene Preview and Editor

This Python application provides a user interface for browsing, previewing, editing, and managing video scenes stored in an SQLite database.

## Features

-   **Database Integration:** Loads video and scene data from a pre-defined SQLite database (`video_data.db`).
-   **VLC Powered Playback:** Uses VLC (via `python-vlc`) for robust video playback, handling a wide range of codecs.
-   **Scene Table View:** Displays all scenes from the database in a sortable table with columns:
    -   Select (Checkbox)
    -   File (Video ID)
    -   Scene (Scene ID)
    -   Start (HH:MM:SS.mmm)
    -   End (HH:MM:SS.mmm)
    -   Description Length
    -   Transcript Length
    -   Scene Length (seconds)
-   **Numerical Sorting:** Allows sorting the table by Scene ID, Description Length, Transcript Length, and Scene Length numerically.
-   **Scene Preview:** Click any row in the table to:
    -   Load the corresponding video file (requires selecting the correct Base Directory).
    -   Play the specific scene segment (respecting start and end times).
    -   Display scene description and transcript in the right panel.
-   **Sequential Playback:** Select multiple scenes using checkboxes and click "連続再生" (Sequential Play) to play them back-to-back. Playback starts from the currently selected row if it's checked, otherwise from the first checked scene.
-   **Scene Editing:** Edit the Description and Transcript text fields in the right panel and click "説明/文字起こしを保存" (Save Description/Transcript) to update the database. Table lengths are updated automatically.
-   **Scene Deletion:** Select scenes using checkboxes and click "選択したシーンを削除" (Delete Selected Scenes) to remove them from the database (confirmation required).
-   **Base Directory Selection:** Allows specifying the root directory where the source video files (`.MP4` etc.) are located.

## Requirements

-   Python 3
-   PyQt5
-   python-vlc
-   **VLC Media Player:** The VLC media player application must be installed on your system as `python-vlc` uses its libraries. Download from [VideoLAN](https://www.videolan.org/vlc/index.ja.html).
-   An SQLite database file named `video_data.db` in the same directory as the script, containing `videos` and `scenes` tables with the expected structure.

## Installation

1.  **Clone the repository or download the scripts** (`video_preview_app.py`, `video_player.py`, `database_manager.py`).
2.  **Install VLC Media Player** if you haven't already.
3.  **Install the required Python libraries:**
    ```bash
    pip install PyQt5 python-vlc
    ```
4.  **Prepare the database:** Ensure `video_data.db` exists in the same directory and contains the necessary video and scene data.

## Usage

1.  **Run the application:**
    ```bash
    python video_preview_app.py
    ```
2.  **Select Base Directory:** Click the "ベースディレクトリ選択..." (Select Base Directory) button and choose the folder containing your source video files.
3.  **Browse and Select Scenes:** Use the table on the left to view scenes.
4.  **Preview:** Click a row to preview the scene.
5.  **Edit:** Edit text in the right panel and click the save button.
6.  **Delete:** Check scenes and click the delete button.
7.  **Sequential Playback:** Check scenes, select a starting scene (optional), and click the sequential play button.

## Code Overview

-   **`video_preview_app.py`:** The main application window (`VideoPreviewApp`). Handles UI layout, database interaction orchestration, table population, scene selection logic, sequential playback control, and connects different components.
    -   `SceneInfoPanel`: The right-side panel displaying and editing scene details.
    -   `NumericTableWidgetItem`: Custom table item for correct numerical sorting.
-   **`video_player.py`:** The video player widget (`VideoPlayer`) using `python-vlc` for playback and controls. Handles playing specific segments and emitting signals on playback completion.
-   **`database_manager.py`:** The `DatabaseManager` class handles all interactions with the SQLite database (connecting, fetching data, updating, deleting).

## Known Issues / Potential Improvements

-   VLC integration can sometimes be sensitive to environment setup (VLC installation path, 32/64-bit mismatch).
-   File ID sorting in the table might not be purely numerical due to alphanumeric prefixes.
-   Search functionality is currently disabled and needs updating for the table view.
-   No thumbnail display in the table.
-   Error handling could be more robust in some areas. # video_preview_app
