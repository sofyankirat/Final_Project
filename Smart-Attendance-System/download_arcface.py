import requests
import zipfile
import os

print('Downloading ArcFace model...')
url = 'https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip'
zip_path = 'models/buffalo_sc.zip'

r = requests.get(url, timeout=300)
with open(zip_path, 'wb') as f:
    f.write(r.content)

print('Extracting...')
with zipfile.ZipFile(zip_path, 'r') as z:
    z.extractall('models')

os.remove(zip_path)
print('ArcFace model downloaded and extracted successfully!')
