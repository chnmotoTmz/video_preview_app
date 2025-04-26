import os
import json
import logging
import requests

# ログディレクトリを作成
os.makedirs('logs', exist_ok=True)

# ロギング設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler('logs/gemini_api.log', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

# 環境変数から設定を取得
API_KEY = os.getenv('GEMINI_API_KEY')
API_URL = os.getenv('GEMINI_API_URL', 'https://api.gemini.ai/v1/chat')

def send_message(messages):
    """
    Gemini API にメッセージを送信し、レスポンスを返す
    messages: list of {"role": "user"/"system", "content": str}
    """
    request_body = {
        "model": "gemini-prototype-1",
        "messages": messages
    }
    # リクエストログを JSON ファイルへ保存
    with open('logs/gemini_request.json', 'w', encoding='utf-8') as f:
        json.dump(request_body, f, ensure_ascii=False, indent=2)
    logger.info("Gemini request: %s", request_body)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    response = requests.post(API_URL, headers=headers, json=request_body)
    try:
        response.raise_for_status()
    except Exception as e:
        logger.error("HTTP error: %s", e)
        raise

    resp_json = response.json()
    # レスポンスログを JSON ファイルへ保存
    with open('logs/gemini_response.json', 'w', encoding='utf-8') as f:
        json.dump(resp_json, f, ensure_ascii=False, indent=2)
    logger.info("Gemini response: %s", resp_json)

    # 返却値（最初のchoiceのmessage.content）
    return resp_json["choices"][0]["message"]["content"]

def main():
    """
    コマンドラインからプロンプトを受け取り、Gemini APIを呼び出して結果を表示します
    """
    import argparse
    parser = argparse.ArgumentParser(description="Gemini API テストクライアント")
    parser.add_argument("--prompt", "-p", required=True, help="ユーザープロンプト")
    args = parser.parse_args()

    messages = [
        {"role": "user", "content": args.prompt}
    ]
    reply = send_message(messages)
    print("Gemini API の応答:")
    print(reply)

if __name__ == "__main__":
    main() 