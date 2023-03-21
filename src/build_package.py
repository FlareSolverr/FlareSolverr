import os
import platform
import shutil
import subprocess
import sys
import zipfile

import requests


def clean_files():
    try:
        shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'build'))
    except Exception:
        pass
    try:
        shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'dist'))
    except Exception:
        pass
    try:
        shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'dist_chrome'))
    except Exception:
        pass


def download_chromium():
    # https://commondatastorage.googleapis.com/chromium-browser-snapshots/index.html?prefix=Linux_x64/
    revision = "1090006" if os.name == 'nt' else '1090007'
    arch = 'Win' if os.name == 'nt' else 'Linux_x64'
    dl_file = 'chrome-win' if os.name == 'nt' else 'chrome-linux'
    dl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'dist_chrome')
    dl_path_folder = os.path.join(dl_path, dl_file)
    dl_path_zip = dl_path_folder + '.zip'

    # response = requests.get(
    #     f'https://commondatastorage.googleapis.com/chromium-browser-snapshots/{arch}/LAST_CHANGE',
    #     timeout=30)
    # revision = response.text.strip()
    print("Downloading revision: " + revision)

    os.mkdir(dl_path)
    with requests.get(
            f'https://commondatastorage.googleapis.com/chromium-browser-snapshots/{arch}/{revision}/{dl_file}.zip',
            stream=True) as r:
        r.raise_for_status()
        with open(dl_path_zip, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print("File downloaded: " + dl_path_zip)
    with zipfile.ZipFile(dl_path_zip, 'r') as zip_ref:
        zip_ref.extractall(dl_path)
    os.remove(dl_path_zip)
    shutil.move(dl_path_folder, os.path.join(dl_path, "chrome"))


def run_pyinstaller():
    sep = ';' if os.name == 'nt' else ':'
    subprocess.check_call([sys.executable, "-m", "PyInstaller",
                           "--onefile",
                           "--icon", "resources/flaresolverr_logo.ico",
                           "--add-data", f"package.json{sep}.",
                           "--add-data", f"{os.path.join('dist_chrome', 'chrome')}{sep}chrome",
                           os.path.join("src", "flaresolverr.py")],
                          cwd=os.pardir)
    exe_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'dist')
    exe_name = 'flaresolverr.exe' if os.name == 'nt' else 'flaresolverr'
    exe_new_name = 'flaresolverr_windows_x64.exe' if os.name == 'nt' else 'flaresolverr_linux_x64'
    exe_path = os.path.join(exe_folder, exe_name)
    exe_new_path = os.path.join(exe_folder, exe_new_name)
    shutil.move(exe_path, exe_new_path)
    print("Executable path: " + exe_new_path)


if __name__ == "__main__":
    print("Building package...")
    print("Platform: " + platform.platform())

    print("Cleaning previous build...")
    clean_files()

    print("Downloading Chromium...")
    download_chromium()

    print("Building pyinstaller executable... ")
    run_pyinstaller()

# NOTE: python -m pip install pyinstaller
