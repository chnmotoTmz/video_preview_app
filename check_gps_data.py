import json

def main():
    try:
        with open('gps_data.json', 'r') as f:
            data = json.load(f)
            
        print(f"総データ数: {len(data)}")
        print("\n最初の10件のGPSデータ:")
        for i, point in enumerate(data[:10]):
            print(f"\nポイント {i+1}:")
            print(f"  緯度: {point['latitude']}")
            print(f"  経度: {point['longitude']}")
            print(f"  高度: {point['altitude']}m")
            print(f"  速度: {point['speed']}m/s")
            print(f"  時刻: {point['timestamp']}")

    except FileNotFoundError:
        print("GPSデータファイルが見つかりません")
    except json.JSONDecodeError:
        print("JSONファイルの解析に失敗しました")
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")

if __name__ == "__main__":
    main() 