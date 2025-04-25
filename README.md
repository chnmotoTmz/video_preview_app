# 動画プレビューアプリ

動画、シーン、字幕データを統合的に管理・表示するWebアプリケーションです。

## 機能

- 動画の一覧表示と選択
- シーンと字幕の統合表示
- フィルタリング機能
  - シーン番号による絞り込み
  - 説明文検索
  - 字幕検索
  - 評価タグによるフィルタリング
- シーン再生機能
- エクスポート機能（EDL、SRT形式）

## システム構成

- バックエンド: Flask (Python)
- フロントエンド: Streamlit (Python)
- データベース: SQLite

## 必要条件

- Python 3.8以上
- 必要なPythonパッケージ:
  - Flask
  - Streamlit
  - pandas
  - requests
  - streamlit-option-menu

## インストール方法

1. リポジトリをクローン:
```bash
git clone [リポジトリURL]
cd video_preview_app
```

2. 必要なパッケージをインストール:
```bash
pip install -r requirements.txt
```

## 使用方法

1. バックエンドサーバー（Flask）を起動:
```bash
python app.py --base-folder [動画ファイルのベースフォルダパス] --port 5000
```

2. フロントエンド（Streamlit）を起動:
```bash
streamlit run streamlit_app.py
```

3. ブラウザで `http://localhost:8501` にアクセス

## データベース構造

- `videos`: 動画情報
- `scenes`: シーン情報
- `transcriptions`: 字幕情報

## APIエンドポイント

- `GET /api/videos`: 動画一覧を取得
- `GET /api/combined_data/{video_id}`: 動画、シーン、字幕の統合データを取得
- `GET /api/thumbnails/{scene_pk}`: サムネイル画像を取得
- `GET /api/stream/{video_id}`: 動画をストリーミング
- `POST /api/export/edl`: EDLファイルをエクスポート
- `POST /api/export/srt`: SRTファイルをエクスポート

## 開発者向け情報

### データベースの初期化

```bash
python create_database.py
```

### テスト方法

```bash
python -m pytest tests/
```

## ライセンス

MIT License

## 作者

[作者名]

## 貢献

1. このリポジトリをフォーク
2. 新しいブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add some amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成
