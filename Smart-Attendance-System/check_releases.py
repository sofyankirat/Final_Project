import requests

print('Checking releases from lindevs/yolov8-face...')
url = 'https://api.github.com/repos/lindevs/yolov8-face/releases'

headers = {
    'User-Agent': 'Mozilla/5.0'
}

try:
    r = requests.get(url, headers=headers, timeout=30)
    data = r.json()
    
    if isinstance(data, list) and len(data) > 0:
        latest = data[0]
        print(f"Latest release: {latest.get('tag_name', 'unknown')}")
        print(f"Assets available:")
        for asset in latest.get('assets', []):
            print(f"  - {asset['name']}: {asset['browser_download_url']}")
    else:
        print("No releases found or API limited")
        
except Exception as e:
    print(f"Error: {e}")
