# データ構造分析

## template_sample（理想的な出力形式）

### ファイル構造
- `video_nodes_GH011260/keyframes/` - キーフレーム画像を格納
- `video_nodes_GH011260/previews/` - プレビュー動画を格納
- `video_nodes_GH011260/nodes.json` - シーン情報を含むJSONファイル

### JSON構造
`nodes.json`には以下のフィールドが含まれています：
```json
{
  "scenes": [
    {
      "scene_id": 数値,
      "time_in": 数値（秒）,
      "time_out": 数値（秒）,
      "transcript": "テキスト",
      "description": "テキスト",
      "keyframe_path": "ファイルパス",
      "preview_path": "ファイルパス",
      "duration": 数値（秒）
    },
    ...
  ],
  "completed": 真偽値,
  "last_update": "日時"
}
```

### 特徴
- 時間はシンプルな秒単位の数値
- キーフレームと動画プレビューの両方のパスを保持
- 各シーンの継続時間（duration）を明示的に保持
- Windowsスタイルのパス区切り文字（`\\`）を使用

## ts（現状のデータ形式）

### ファイル構造
- `ts/GH012846_captures/` - シーン画像とJSONデータを格納
- `ts/GH012847_captures/` - シーン画像とJSONデータを格納
- `ts/GH012849_captures/` - シーン画像とJSONデータを格納

### JSON構造
各キャプチャフォルダ内の`GH01xxxx_data.json`には以下のフィールドが含まれています：
```json
{
  "source_filepath": "ファイルパス",
  "file_index": 数値,
  "extracted_audio_filepath": "ファイルパス",
  "metadata": {
    "duration_seconds": 数値,
    "creation_time_utc": "日時",
    "timecode_offset": "タイムコード"
  },
  "transcription_whisper_result": {
    "text": "テキスト",
    "segments": [],
    "language": "言語コード"
  },
  "detected_scenes": [
    {
      "scene_id": 数値,
      "start_timecode": "タイムコード",
      "end_timecode": "タイムコード",
      "description": "テキスト",
      "thumbnail_path": "ファイルパス"
    },
    ...
  ],
  "final_segments": [
    {
      "start_timecode": "タイムコード",
      "end_timecode": "タイムコード",
      "transcription": "テキスト",
      "scene_id": 数値,
      "scene_description": "テキスト"
    },
    ...
  ]
}
```

### 特徴
- 時間はタイムコード形式（"00:00:00:00"）
- メタデータとして動画の詳細情報を保持
- 検出されたシーン（detected_scenes）と最終セグメント（final_segments）を分離
- Windowsスタイルのパス区切り文字（`\\`）を使用
- 画像ファイルは「scene_XXXX.jpg」という命名規則

## 主な違い

1. **時間表現の違い**:
   - template_sample: 秒単位の数値（time_in, time_out）
   - ts: タイムコード形式（"00:00:00:00"）

2. **構造の違い**:
   - template_sample: シンプルなシーンリスト
   - ts: 複数のセクション（metadata, detected_scenes, final_segments）に分かれている

3. **トランスクリプト（文字起こし）の扱い**:
   - template_sample: 各シーンに直接含まれる
   - ts: final_segmentsセクションに分離され、scene_idで関連付け

4. **ファイル命名規則**:
   - template_sample: keyframe_XXXX.jpg
   - ts: scene_XXXX.jpg

5. **プレビュー動画**:
   - template_sample: 各シーンにプレビュー動画パスあり
   - ts: プレビュー動画なし

6. **メタデータ**:
   - template_sample: 最小限（completed, last_update）
   - ts: 詳細なメタデータ（duration_seconds, creation_time_utc, timecode_offset）

7. **ファイル構成**:
   - template_sample: 1つの動画に対して1つのJSONファイル
   - ts: 複数の動画に対してそれぞれJSONファイル
