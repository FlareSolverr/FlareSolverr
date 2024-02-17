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
    revision = "1260008" if os.name == 'nt' else '1260015'
    arch = 'Win_x64' if os.name == 'nt' else 'Linux_x64'
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

    chrome_path = os.path.join(dl_path, "chrome")
    shutil.move(dl_path_folder, chrome_path)
    print("Extracted in: " + chrome_path)

    if os.name != 'nt':
        # Give executable permissions for *nix
        # file * | grep executable | cut -d: -f1
        print("Giving executable permissions...")
        execs = ['chrome', 'chrome_crashpad_handler', 'chrome_sandbox', 'chrome-wrapper', 'xdg-mime', 'xdg-settings']
        for exec_file in execs:
            exec_path = os.path.join(chrome_path, exec_file)
            os.chmod(exec_path, 0o755)


def run_pyinstaller():
    sep = ';' if os.name == 'nt' else ':'
    result = subprocess.run([sys.executable, "-m", "PyInstaller",
                             "--icon", "resources/flaresolverr_logo.ico",
                             "--add-data", f"package.json{sep}.",
                             "--add-data", f"{os.path.join('dist_chrome', 'chrome')}{sep}chrome",
                             os.path.join("src", "flaresolverr.py")],
                            cwd=os.pardir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(result.stderr.decode('utf-8'))
        raise Exception("Error running pyInstaller")


def compress_package():
    dist_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'dist')
    package_folder = os.path.join(dist_folder, 'package')
    shutil.move(os.path.join(dist_folder, 'flaresolverr'), os.path.join(package_folder, 'flaresolverr'))
    print("Package folder: " + package_folder)

    compr_format = 'zip' if os.name == 'nt' else 'gztar'
    compr_file_name = 'flaresolverr_windows_x64' if os.name == 'nt' else 'flaresolverr_linux_x64'
    compr_file_path = os.path.join(dist_folder, compr_file_name)
    shutil.make_archive(compr_file_path, compr_format, package_folder)
    print("Compressed file path: " + compr_file_path)


if __name__ == "__main__":
    print("Building package...")
    print("Platform: " + platform.platform())

    print("Cleaning previous build...")
    clean_files()

    print("Downloading Chromium...")
    download_chromium()

    print("Building pyinstaller executable... ")
    run_pyinstaller()

    print("Compressing package... ")
    compress_package()

# NOTE: python -m pip install pyinstaller
