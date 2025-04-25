#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import sys

def check_database(db_path):
    """データベースの内容を確認する"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # テーブル一覧を取得
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("データベース内のテーブル:")
    for table in tables:
        table_name = table[0]
        print(f"\n=== {table_name} テーブル ===")
        
        # テーブルの構造を表示
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print("\n列構造:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # レコード数を表示
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"\nレコード数: {count}")
        
        # 最初の5件を表示
        if count > 0:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
            rows = cursor.fetchall()
            print("\n最初の5件:")
            for row in rows:
                print(f"  {row}")
    
    conn.close()

if __name__ == "__main__":
    db_path = "video_data.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    check_database(db_path) 