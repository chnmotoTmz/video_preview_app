import requests

API_URL = "http://localhost:5000/api/merged_data/all"
TARGET_FILENAME = "GH012936.MP4"

def test_get_video_end_timecode():
    response = requests.get(API_URL)
    response.raise_for_status()
    data = response.json()
    for row in data:
        if row.get("video_filename") == TARGET_FILENAME:
            print(f"video_end_timecode for {TARGET_FILENAME}: {row.get('video_end_timecode')}")
            return row.get('video_end_timecode')
    print(f"{TARGET_FILENAME} not found in API response.")
    return None

if __name__ == "__main__":
    test_get_video_end_timecode() 