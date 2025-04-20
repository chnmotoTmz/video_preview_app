# データ変換戦略

## 概要
tsフォーマットからtemplate_sampleフォーマットへのデータ変換を行うための戦略を設計します。変換プロセスは以下の主要なステップで構成されます。

## 変換プロセス

### 1. データ読み込み
- 各`GH01xxxx_data.json`ファイルを読み込む
- 関連する画像ファイル（scene_XXXX.jpg）のパスを特定

### 2. データマッピング
以下のフィールドマッピングを実装します：

| ts形式 | template_sample形式 | 変換ロジック |
|--------|---------------------|--------------|
| detected_scenes[].scene_id | scenes[].scene_id | 直接マッピング |
| detected_scenes[].start_timecode | scenes[].time_in | タイムコード→秒数変換 |
| detected_scenes[].end_timecode | scenes[].time_out | タイムコード→秒数変換 |
| final_segments[].transcription | scenes[].transcript | scene_idに基づいて関連付け |
| detected_scenes[].description | scenes[].description | 直接マッピング |
| detected_scenes[].thumbnail_path | scenes[].keyframe_path | パス変換（命名規則変更） |
| なし | scenes[].preview_path | 生成（予測パス） |
| end_timecode - start_timecode | scenes[].duration | 秒数計算 |

### 3. ファイル構造変換
- 各動画ファイルごとに`video_nodes_GH01xxxx`ディレクトリを作成
- `keyframes`と`previews`サブディレクトリを作成
- 画像ファイルを`scene_XXXX.jpg`から`keyframe_XXXX.jpg`に変換してコピー
- プレビュー動画は実際には存在しないため、パスのみ生成

### 4. 時間形式変換
タイムコード（"00:00:00:00"）から秒数への変換関数を実装：
```python
def timecode_to_seconds(timecode):
    # "00:00:00:00" → 秒数
    hours, minutes, seconds, frames = map(int, timecode.split(':'))
    # フレームレートを30fpsと仮定
    return hours * 3600 + minutes * 60 + seconds + frames / 30
```

### 5. JSONデータ生成
- template_sample形式のJSONデータを生成
- 各動画ファイルごとに`nodes.json`ファイルを作成
- 必要なメタデータ（completed, last_update）を追加

## SQLiteデータベース設計

### テーブル構造

#### 1. Videos テーブル
```sql
CREATE TABLE videos (
    video_id TEXT PRIMARY KEY,  -- 例: "GH012846"
    source_filepath TEXT,
    duration_seconds REAL,
    creation_time TEXT,
    timecode_offset TEXT,
    completed BOOLEAN,
    last_update TEXT
);
```

#### 2. Scenes テーブル
```sql
CREATE TABLE scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT,
    scene_id INTEGER,
    time_in REAL,
    time_out REAL,
    transcript TEXT,
    description TEXT,
    keyframe_path TEXT,
    preview_path TEXT,
    duration REAL,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);
```

### インデックス
```sql
CREATE INDEX idx_video_id ON scenes(video_id);
CREATE INDEX idx_scene_id ON scenes(scene_id);
```

## FastAPI サービス設計

### エンドポイント

#### 1. 動画一覧取得
```
GET /api/videos
```
レスポンス: 全動画のリスト

#### 2. 特定動画の詳細取得
```
GET /api/videos/{video_id}
```
レスポンス: 動画の詳細情報とシーンリスト

#### 3. 特定シーンの詳細取得
```
GET /api/videos/{video_id}/scenes/{scene_id}
```
レスポンス: シーンの詳細情報

#### 4. キーフレーム画像取得
```
GET /api/keyframes/{video_id}/{scene_id}
```
レスポンス: キーフレーム画像（静的ファイル）

### データモデル（Pydantic）

```python
class Scene(BaseModel):
    scene_id: int
    time_in: float
    time_out: float
    transcript: str
    description: str
    keyframe_path: str
    preview_path: str
    duration: float

class Video(BaseModel):
    video_id: str
    source_filepath: str
    duration_seconds: float
    creation_time: str
    completed: bool
    last_update: str
    scenes: List[Scene] = []
```

## 実装計画

1. データ変換スクリプト（Python）
   - ts形式からtemplate_sample形式への変換
   - 画像ファイルの変換とコピー

2. SQLiteデータベース作成スクリプト
   - テーブル作成
   - 変換データの挿入

3. FastAPIサービス
   - データモデル定義
   - エンドポイント実装
   - 静的ファイル配信設定

4. テストスクリプト
   - 変換結果の検証
   - APIエンドポイントのテスト
