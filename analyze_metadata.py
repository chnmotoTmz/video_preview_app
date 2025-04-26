import struct
import binascii

def analyze_metadata(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
            
        print(f"ファイルサイズ: {len(data)} バイト")
        print("\n最初の100バイトの16進数ダンプ:")
        
        # 16バイトごとに表示
        for i in range(0, min(100, len(data)), 16):
            hex_values = binascii.hexlify(data[i:i+16], ' ').decode()
            ascii_values = ''.join(chr(x) if 32 <= x <= 126 else '.' for x in data[i:i+16])
            print(f"{i:04x}: {hex_values:<48} {ascii_values}")
            
        # GPMF関連のキーワードを検索
        keywords = [b'DEVC', b'STRM', b'GPS5', b'GPSU', b'GPSF']
        print("\nGPMF関連キーワードの位置:")
        for keyword in keywords:
            positions = []
            pos = -1
            while True:
                pos = data.find(keyword, pos + 1)
                if pos == -1:
                    break
                positions.append(pos)
            if positions:
                print(f"{keyword.decode()}: {positions}")

if __name__ == "__main__":
    analyze_metadata("metadata.bin") 