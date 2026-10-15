# SPDX-License-Identifier: Apache-2.0
import os
import shutil
import urllib.request
import zipfile

bin_dir = r"C:\HyperSpace\bin\bonsai"
os.makedirs(bin_dir, exist_ok=True)

base_url = "https://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10772-e8fd209"
packages = [
    ("llama.zip", f"{base_url}/llama-prism-b10772-e8fd209-bin-win-cuda-12.4-x64.zip"),
    ("cudart.zip", f"{base_url}/cudart-llama-bin-win-cuda-12.4-x64.zip")
]

for name, url in packages:
    zip_path = os.path.join(bin_dir, name)
    print(f"Downloading {name}...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as f:
        shutil.copyfileobj(resp, f, length=1024*1024)
    print(f"Extracting {name} ({os.path.getsize(zip_path):,} bytes)...", flush=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(bin_dir)
    os.remove(zip_path)
    print(f"Finished {name}.", flush=True)

print("\nDone. Executables in directory:", flush=True)
for fname in sorted(os.listdir(bin_dir)):
    fpath = os.path.join(bin_dir, fname)
    if os.path.isfile(fpath) and fname.endswith(".exe"):
        print(f"  {fname}: {os.path.getsize(fpath):,} bytes", flush=True)
