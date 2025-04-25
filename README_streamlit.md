# Streamlit 動画ビューアーフロントエンド

このプロジェクトは、既存のFlask APIバックエンドを利用して、Streamlitで実装された動画ビューアーフロントエンドです。

## 特徴

- Streamlitを使用した直感的なユーザーインターフェース
- 既存のFlask APIと連携（バックエンドの変更不要）
- 動画選択、シーン・字幕表示、エクスポート機能などの実装
- レスポンシブデザインとデータのキャッシュ

## 必要条件

- Python 3.7以上
- Streamlit
- requests
- pandas

## インストール

1. 必要なパッケージをインストールします：

```bash
pip install streamlit requests pandas
```

2. このリポジトリをクローンまたはダウンロードします。

## 使用方法

1. まず、Flask APIバックエンドを実行します：

```bash
python app.py --base-folder "動画ファイルがあるフォルダのパス"
```

2. 別のターミナルで、Streamlitフロントエンドを実行します：

```bash
streamlit run streamlit_app.py
```

3. ブラウザが自動的に開き、アプリケーションにアクセスできます（通常は http://localhost:8501 ）

## 主な機能

- **動画選択**: ドロップダウンから利用可能な動画を選択
- **シーン表示**: シーンのサムネイル、タイムコード、説明などを一覧表示
- **字幕表示**: 動画の字幕データを表示
- **動画再生**: 選択したシーンまたは字幕位置から動画を再生
- **EDL/SRTエクスポート**: 選択したシーンをEDLまたはSRT形式でエクスポート

## カスタマイズ

- `API_BASE_URL` 変数を変更することで、異なるAPIエンドポイントに接続できます（デフォルトは `http://localhost:5000/api`）
- CSSとHTMLを調整することで、テーブルやコンポーネントの外観をカスタマイズできます

## 注意点

- このアプリケーションは、既存のFlask APIが正常に動作していることを前提としています
- APIエンドポイントが変更された場合は、`streamlit_app.py` 内の対応する関数を更新する必要があります
- テーブル内のインタラクティブな要素（チェックボックスやボタン）のいくつかは、StreamlitのHTML表示の制限により、視覚的な要素として表示されている場合があります

## Flask API エンドポイント

このアプリケーションが利用する主なAPIエンドポイント：

- `GET /api/videos` - 利用可能な動画のリストを取得
- `GET /api/scenes/{video_id}` - 指定した動画のシーンデータを取得
- `GET /api/transcriptions/{video_id}` - 指定した動画の字幕データを取得
- `GET /api/thumbnails/{scene_id}` - シーンのサムネイル画像を取得
- `GET /api/stream/{video_id}` - 動画ストリームを取得
- `POST /api/export/edl` - EDL形式でエクスポート
- `POST /api/export/srt` - SRT形式でエクスポート 