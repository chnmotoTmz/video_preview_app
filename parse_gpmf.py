import struct
import json
import datetime
import logging
from pathlib import Path

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GPMFParser:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.data = None
        self.position = 0
        self.gps_data = []

    def read_binary_file(self):
        """バイナリファイルを読み込む"""
        try:
            with open(self.file_path, 'rb') as f:
                self.data = f.read()
            logger.info(f"ファイルを読み込みました: {self.file_path.name}")
            logger.info(f"ファイルサイズ: {len(self.data)} bytes")
            return True
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {e}")
            return False

    def parse_fourcc(self):
        """FourCCコードを解析する"""
        if self.position + 4 > len(self.data):
            return None
        fourcc = self.data[self.position:self.position + 4].decode('ascii')
        self.position += 4
        return fourcc

    def parse_size(self):
        """データタイプのサイズを取得"""
        if self.position + 4 > len(self.data):
            return None
        size = struct.unpack('>I', self.data[self.position:self.position + 4])[0]
        self.position += 4
        return size

    def parse_gps_data(self):
        """GPSデータを解析する"""
        while self.position < len(self.data):
            try:
                fourcc = self.parse_fourcc()
                if not fourcc:
                    break

                size = self.parse_size()
                if not size:
                    break

                logger.debug(f'FourCC: {fourcc}, Size: {size}')

                if fourcc == 'GPS5':
                    num_points = size // 20  # GPS5データは20バイトごと
                    for _ in range(num_points):
                        if self.position + 20 > len(self.data):
                            break
                        
                        gps_point = struct.unpack('>fffff', self.data[self.position:self.position + 20])
                        self.position += 20
                        
                        self.gps_data.append({
                            'latitude': gps_point[0],
                            'longitude': gps_point[1],
                            'altitude': gps_point[2],
                            'speed': gps_point[3],
                            'speed3d': gps_point[4]
                        })
                else:
                    # 他のブロックはスキップ
                    self.position += size

                # 4バイト境界に合わせる
                self.position = (self.position + 3) & ~3

            except Exception as e:
                logger.error(f'GPSデータ解析エラー: {e}')
                break

    def save_gps_data(self, output_file):
        """GPS データをJSONファイルとして保存"""
        if not self.gps_data:
            logger.warning('GPSデータが見つかりませんでした。')
            return False

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_points': len(self.gps_data),
                    'timestamp': datetime.datetime.now().isoformat(),
                    'gps_data': self.gps_data
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f'GPSデータを保存しました: {output_file}')
            logger.info(f'GPSデータポイント数: {len(self.gps_data)}')
            return True
        except Exception as e:
            logger.error(f'データ保存エラー: {e}')
            return False

def main():
    """メイン関数"""
    # 入力ファイルパス
    input_file = "metadata.bin"
    output_file = "gps_data.json"
    
    if not Path(input_file).exists():
        logger.error(f"入力ファイルが見つかりません: {input_file}")
        return
    
    parser = GPMFParser(input_file)
    
    if not parser.read_binary_file():
        return
    
    parser.parse_gps_data()
    
    if parser.gps_data:
        logger.info(f"GPSデータポイント数: {len(parser.gps_data)}")
        parser.save_gps_data(output_file)
    else:
        logger.warning("GPSデータが見つかりませんでした。")

if __name__ == "__main__":
    main() 