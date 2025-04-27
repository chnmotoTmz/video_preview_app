import json
import folium
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from folium.plugins import HeatMap, MarkerCluster
import os
from geopy.distance import geodesic

def calculate_distance(lat1, lon1, lat2, lon2):
    """2点間の距離をメートル単位で計算（Haversine公式）"""
    try:
        R = 6371000  # 地球の半径（メートル）
        
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance
    except Exception as e:
        print(f"距離計算エラー: {str(e)}")
        return 0

def load_gps_data(file_path):
    """JSONファイルからGPSデータを読み込み、前処理を行う"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # データをDataFrameに変換
        df = pd.DataFrame(data)
        
        # 無効なデータを除外
        df = df.dropna()
        
        # まず生のデータの範囲を確認
        print("\n元のデータの範囲:")
        print(f"緯度範囲: {df['latitude'].min():.6f} - {df['latitude'].max():.6f}")
        print(f"経度範囲: {df['longitude'].min():.6f} - {df['longitude'].max():.6f}")
        print(f"データ数: {len(df)}")
        
        # 異常値の除外（緩和した条件）
        df = df[df['speed'].between(0, 30)]  # 速度が0-30m/s以内（約0-108km/h）
        df = df[df['altitude'].between(-100, 3000)]  # 高度が-100m-3000m以内
        
        # 連続する位置の急激な変化を検出して除外
        df['lat_diff'] = df['latitude'].diff().abs()
        df['lon_diff'] = df['longitude'].diff().abs()
        df = df[df['lat_diff'] < 0.1]  # 緯度の急激な変化を除外（条件緩和）
        df = df[df['lon_diff'] < 0.1]  # 経度の急激な変化を除外（条件緩和）
        
        # フィルタリング後のデータ範囲を確認
        print("\nフィルタリング後のデータ範囲:")
        print(f"緯度範囲: {df['latitude'].min():.6f} - {df['latitude'].max():.6f}")
        print(f"経度範囲: {df['longitude'].min():.6f} - {df['longitude'].max():.6f}")
        print(f"データ数: {len(df)}")
        
        # データを時系列で並び替え
        df = df.sort_index()
        
        # データを間引く（データ量が多すぎる場合）
        if len(df) > 1000:
            df = df.iloc[::len(df)//1000]
        
        # 距離の計算
        distances = []
        total_distance = 0
        
        for i in range(len(df)):
            if i == 0:
                distances.append(0)
            else:
                dist = calculate_distance(
                    df.iloc[i-1]['latitude'], df.iloc[i-1]['longitude'],
                    df.iloc[i]['latitude'], df.iloc[i]['longitude']
                )
                # 異常な距離値を除外（条件緩和）
                if dist < 5000:  # 1回のサンプリングで5km以上の移動は除外
                    total_distance += dist
                    distances.append(dist)
                else:
                    distances.append(0)
        
        df['distance'] = distances
        df['cumulative_distance'] = np.cumsum(distances)
        
        print(f"\n有効なGPSポイント数: {len(df)}")
        print(f"総距離: {total_distance/1000:.2f}km")
        
        return df.to_dict('records')
    except Exception as e:
        print(f"データ読み込みエラー: {str(e)}")
        return []

def create_map(gps_data):
    """GPSデータから地図を生成"""
    try:
        # 最初の有効な座標を中心に設定
        center_lat = gps_data[0]['latitude']
        center_lon = gps_data[0]['longitude']
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
        
        # ルートの座標リストを作成
        coordinates = [[d['latitude'], d['longitude']] for d in gps_data]
        
        # ルートを描画
        folium.PolyLine(
            coordinates,
            weight=3,
            color='red',
            opacity=0.8,
            popup='ルート'
        ).add_to(m)
        
        # 開始点と終了点にマーカーを追加
        folium.Marker(
            coordinates[0],
            popup='開始点',
            icon=folium.Icon(color='green', icon='info-sign')
        ).add_to(m)
        
        folium.Marker(
            coordinates[-1],
            popup='終了点',
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        
        # 距離マーカーを1kmごとに追加
        df = pd.DataFrame(gps_data)
        km_points = df[df['cumulative_distance'] % 1000 < df['distance']]
        for idx, point in km_points.iterrows():
            folium.CircleMarker(
                location=[point['latitude'], point['longitude']],
                radius=5,
                color='blue',
                fill=True,
                popup=f"{point['cumulative_distance']/1000:.1f}km"
            ).add_to(m)
        
        return m
    except Exception as e:
        print(f"地図生成エラー: {str(e)}")
        return None

def create_graphs(gps_data):
    """速度と高度のグラフを生成"""
    try:
        df = pd.DataFrame(gps_data)
        
        # グラフのスタイル設定
        plt.style.use('default')
        plt.rcParams['font.family'] = 'MS Gothic'
        
        # サブプロットを作成
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12))
        
        # X軸の距離データ
        distance_km = df['cumulative_distance'] / 1000
        
        # 距離に対する速度のグラフ
        ax1.plot(distance_km, df['speed'] * 3.6, 'b-', linewidth=2)
        ax1.set_title('速度の推移', fontsize=12, pad=10)
        ax1.set_xlabel('距離 (km)', fontsize=10)
        ax1.set_ylabel('速度 (km/h)', fontsize=10)
        ax1.grid(True, linestyle='--', alpha=0.7)
        
        # 距離に対する高度のグラフ
        ax2.plot(distance_km, df['altitude'], 'r-', linewidth=2)
        ax2.set_title('高度の推移', fontsize=12, pad=10)
        ax2.set_xlabel('距離 (km)', fontsize=10)
        ax2.set_ylabel('高度 (m)', fontsize=10)
        ax2.grid(True, linestyle='--', alpha=0.7)
        
        # 累積獲得標高のグラフ
        elevation_diff = df['altitude'].diff()
        elevation_gain = elevation_diff.copy()
        elevation_gain[elevation_diff < 0] = 0
        cumulative_gain = elevation_gain.fillna(0).cumsum()
        
        ax3.plot(distance_km, cumulative_gain, 'g-', linewidth=2)
        ax3.set_title('累積獲得標高', fontsize=12, pad=10)
        ax3.set_xlabel('距離 (km)', fontsize=10)
        ax3.set_ylabel('獲得標高 (m)', fontsize=10)
        ax3.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        plt.savefig('gps_graphs.png', dpi=300, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"グラフ生成エラー: {str(e)}")

def calculate_statistics(gps_data):
    """基本的な統計情報を計算"""
    try:
        df = pd.DataFrame(gps_data)
        
        # 速度をm/sからkm/hに変換
        speed_kmh = df['speed'] * 3.6
        
        # 獲得標高を計算
        elevation_gain = df['altitude'].diff()[df['altitude'].diff() > 0].sum()
        
        stats = {
            '総距離 (km)': round(df['cumulative_distance'].iloc[-1] / 1000, 2),
            '平均速度 (km/h)': round(speed_kmh.mean(), 2),
            '最高速度 (km/h)': round(speed_kmh.max(), 2),
            '最低高度 (m)': round(df['altitude'].min(), 2),
            '最高高度 (m)': round(df['altitude'].max(), 2),
            '獲得標高 (m)': round(elevation_gain, 2),
            '所要時間 (分)': round(len(df) / 60, 1)  # GPSポイントは1秒間隔と仮定
        }
        
        print("\n統計情報:")
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        return stats
    except Exception as e:
        print(f"統計情報計算エラー: {str(e)}")
        return {}

def load_gopro_gps_data(json_file_path):
    """JSONファイルからGoProのGPSデータを読み込む"""
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # GPS5データを取得
    gps_samples = data.get('1', {}).get('streams', {}).get('GPS5', {}).get('samples', [])
    
    if not gps_samples:
        print("GPSデータが見つかりません")
        return pd.DataFrame()
    
    # データを抽出
    gps_data = []
    for sample in gps_samples:
        if 'value' in sample and len(sample['value']) >= 5:
            lat, lon, alt, speed_2d, speed_3d = sample['value']
            timestamp = sample.get('date', '')
            
            gps_data.append({
                'latitude': lat,
                'longitude': lon,
                'altitude': alt,
                'speed_2d': speed_2d,
                'speed_3d': speed_3d,
                'timestamp': timestamp
            })
    
    return pd.DataFrame(gps_data)

def create_map_visualization(df, output_path='gopro_gps_map.html'):
    """GPSデータを地図上に可視化"""
    # 中心座標を計算
    center_lat = df['latitude'].mean()
    center_lon = df['longitude'].mean()
    
    # 地図を作成
    m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
    
    # 軌跡を追加
    coordinates = df[['latitude', 'longitude']].values
    if len(coordinates) > 1:  # 2点以上あるときのみ軌跡を描画
        folium.PolyLine(
            locations=coordinates,
            color='blue',
            weight=3,
            opacity=0.8
        ).add_to(m)
    
    # 開始点と終了点にマーカーを追加
    if len(df) > 0:
        folium.Marker(
            location=[df['latitude'].iloc[0], df['longitude'].iloc[0]],
            popup='開始',
            icon=folium.Icon(color='green')
        ).add_to(m)
        
        folium.Marker(
            location=[df['latitude'].iloc[-1], df['longitude'].iloc[-1]],
            popup='終了',
            icon=folium.Icon(color='red')
        ).add_to(m)
    
    # 速度に基づくヒートマップを作成
    heat_data = []
    for _, row in df.iterrows():
        heat_data.append([row['latitude'], row['longitude'], row['speed_2d']])
    
    HeatMap(heat_data).add_to(m)
    
    # 地図を保存
    m.save(output_path)
    print(f"地図を {output_path} に保存しました")
    return m

def plot_altitude_profile(df, output_path='altitude_profile.png'):
    """高度プロファイルをプロット"""
    plt.figure(figsize=(12, 6))
    plt.plot(range(len(df)), df['altitude'])
    plt.title('高度プロファイル')
    plt.xlabel('サンプル')
    plt.ylabel('高度（m）')
    plt.grid(True)
    plt.savefig(output_path)
    print(f"高度プロファイルを {output_path} に保存しました")
    plt.close()

def plot_speed_profile(df, output_path='speed_profile.png'):
    """速度プロファイルをプロット"""
    plt.figure(figsize=(12, 6))
    plt.plot(range(len(df)), df['speed_2d'], label='2D速度')
    plt.plot(range(len(df)), df['speed_3d'], label='3D速度')
    plt.title('速度プロファイル')
    plt.xlabel('サンプル')
    plt.ylabel('速度（m/s）')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_path)
    print(f"速度プロファイルを {output_path} に保存しました")
    plt.close()

def export_to_gpx(df, output_path='gopro_track.gpx'):
    """GPSデータをGPXファイルにエクスポート"""
    import gpxpy
    import gpxpy.gpx
    
    gpx = gpxpy.gpx.GPX()
    
    # 新しいトラックを作成
    track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(track)
    
    # トラックセグメントを作成
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)
    
    # ポイントを追加
    for _, row in df.iterrows():
        point = gpxpy.gpx.GPXTrackPoint(
            latitude=row['latitude'],
            longitude=row['longitude'],
            elevation=row['altitude']
        )
        segment.points.append(point)
    
    # GPXファイルを保存
    with open(output_path, 'w') as f:
        f.write(gpx.to_xml())
    
    print(f"GPXファイルを {output_path} に保存しました")

def analyze_gps_data(df):
    """GPSデータの統計情報を計算"""
    # 基本統計
    stats = {
        'ポイント数': len(df),
        '平均高度': f"{df['altitude'].mean():.1f}m",
        '最高高度': f"{df['altitude'].max():.1f}m",
        '最低高度': f"{df['altitude'].min():.1f}m",
        '高度差': f"{(df['altitude'].max() - df['altitude'].min()):.1f}m",
        '平均速度': f"{df['speed_2d'].mean():.1f}m/s",
        '最高速度': f"{df['speed_2d'].max():.1f}m/s"
    }
    
    # 総距離の計算
    total_distance = 0
    prev_point = None
    
    for _, row in df.iterrows():
        current_point = (row['latitude'], row['longitude'])
        if prev_point:
            distance = geodesic(prev_point, current_point).meters
            total_distance += distance
        prev_point = current_point
    
    stats['総距離'] = f"{total_distance/1000:.2f}km"
    
    return stats

def main(json_file_path):
    """メイン関数"""
    print(f"GPSデータを読み込み中: {json_file_path}")
    
    # GPSデータをロード
    df = load_gopro_gps_data(json_file_path)
    if df.empty:
        print("GPSデータが見つかりませんでした")
        return
    
    print("\n=== GPS統計情報 ===")
    stats = analyze_gps_data(df)
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("\n=== 可視化を作成中 ===")
    # 地図を作成
    create_map_visualization(df)
    
    # 高度プロファイルをプロット
    plot_altitude_profile(df)
    
    # 速度プロファイルをプロット
    plot_speed_profile(df)
    
    # GPXファイルにエクスポート
    export_to_gpx(df)
    
    print("\n処理が完了しました。以下のファイルが生成されました：")
    print("- gopro_gps_map.html (ブラウザで開いてください)")
    print("- altitude_profile.png")
    print("- speed_profile.png")
    print("- gopro_track.gpx")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    else:
        json_file = "GH012866_telemetry.json"  # デフォルトのファイル名
    
    if not os.path.exists(json_file):
        print(f"エラー: ファイル '{json_file}' が見つかりません")
        sys.exit(1)
    
    main(json_file) 