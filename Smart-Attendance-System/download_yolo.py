import requests
import os

print('Downloading YOLOv8 model with browser headers...')
url = 'https://github.com/lindevs/yolov8-face/releases/download/v1.0.0/yolov8s-face-lindevs.pt'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

session = requests.Session()
r = session.get(url, headers=headers, timeout=300, allow_redirects=True, stream=True)

print(f'Status code: {r.status_code}')
print(f'Content length: {r.headers.get("content-length", "unknown")}')

file_path = 'models/yolov8s-face-lindevs.pt'
with open(file_path, 'wb') as f:
    for chunk in r.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)

file_size = os.path.getsize(file_path)
print(f'Downloaded file size: {file_size} bytes')

if file_size > 1000000:
    print('YOLOv8 model downloaded successfully!')
else:
    print('Warning: File size is suspiciously small!')
