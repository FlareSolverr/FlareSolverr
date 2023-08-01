import json
import logging
import os
import re
import shutil

from selenium.webdriver.chrome.webdriver import WebDriver
import undetected_chromedriver as uc

FLARESOLVERR_VERSION = None
CHROME_EXE_PATH = None
CHROME_MAJOR_VERSION = None
USER_AGENT = None
XVFB_DISPLAY = None
PATCHED_DRIVER_PATH = None


def get_config_log_html() -> bool:
    return os.environ.get('LOG_HTML', 'false').lower() == 'true'


def get_config_headless() -> bool:
    return os.environ.get('HEADLESS', 'true').lower() == 'true'


def get_flaresolverr_version() -> str:
    global FLARESOLVERR_VERSION
    if FLARESOLVERR_VERSION is not None:
        return FLARESOLVERR_VERSION

    package_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'package.json')
    if not os.path.isfile(package_path):
        package_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'package.json')
    with open(package_path) as f:
        FLARESOLVERR_VERSION = json.loads(f.read())['version']
        return FLARESOLVERR_VERSION


def get_webdriver(proxy: dict = None) -> WebDriver:
    global PATCHED_DRIVER_PATH
    logging.debug('Launching web browser...')

    # undetected_chromedriver
    options = uc.ChromeOptions()
#    options.add_argument('--no-sandbox')
#    options.add_argument('--window-size=1920,1080')
    # todo: this param shows a warning in chrome head-full
#   options.add_argument('--disable-setuid-sandbox')
#   options.add_argument('--disable-dev-shm-usage')
    # this option removes the zygote sandbox (it seems that the resolution is a bit faster)
 #  options.add_argument('--no-zygote')
    # attempt to fix Docker ARM32 build
#   options.add_argument('--disable-gpu-sandbox')
#   options.add_argument('--disable-software-rasterizer')
    #options.add_argument('--ignore-certificate-errors')
    #options.add_argument('--ignore-ssl-errors')
    # fix GL errors in ASUSTOR NAS
    # https://github.com/FlareSolverr/FlareSolverr/issues/782
    # https://github.com/microsoft/vscode/issues/127800#issuecomment-873342069
    # https://peter.sh/experiments/chromium-command-line-switches/#use-gl
    #options.add_argument('--use-gl=swiftshader')
    # workaround for updated 'verify your are human' check
    # https://github.com/FlareSolverr/FlareSolverr/issues/811
    options.add_argument('--auto-open-devtools-for-tabs')
#    options.add_argument('--headless=true')
    options.add_argument("--disable-popup-blocking")

    options.headless = True
    options.add_argument( '--headless' )
    


    if proxy and 'url' in proxy:
        proxy_url = proxy['url']
        logging.debug("Using webdriver proxy: %s", proxy_url)
        #options.add_argument('--proxy-server=%s' % proxy_url)

    # note: headless mode is detected (options.headless = True)
    # we launch the browser in head-full mode with the window hidden
    #windows_headless = False
    #if get_config_headless():
    #    if os.name == 'nt':
    #        windows_headless = True
    #    else:
    #        start_xvfb_display()

    # if we are inside the Docker container, we avoid downloading the driver
    driver_exe_path = None
    version_main = None
    if os.path.exists("/app/chromedriver"):
        # running inside Docker
        driver_exe_path = "/app/chromedriver"
    else:
        version_main = get_chrome_major_version()
        if PATCHED_DRIVER_PATH is not None:
            driver_exe_path = PATCHED_DRIVER_PATH

    # detect chrome path
    browser_executable_path = str('/bin/chromium')
#    browser_executable_path = get_chrome_exe_path()

    # downloads and patches the chromedriver
    # if we don't set driver_executable_path it downloads, patches, and deletes the driver each time
 #   driver = uc.Chrome(options=options, browser_executable_path=browser_executable_path,
  #                     driver_executable_path=driver_exe_path, version_main=version_main,
  #                     windows_headless=windows_headless)
    driver = uc.Chrome( options = options)
    # save the patched driver to avoid re-downloads
#    if driver_exe_path is None:
#        PATCHED_DRIVER_PATH = os.path.join(driver.patcher.data_path, driver.patcher.exe_name)
#        shutil.copy(driver.patcher.executable_path, PATCHED_DRIVER_PATH)
        
    # workaround for updated 'verify your are human' check
    # https://github.com/FlareSolverr/FlareSolverr/issues/811
#    driver.execute_script('''window.open("","_blank");''')
#    driver.switch_to.window(window_name=driver.window_handles[0])
#    driver.close()
#    driver.switch_to.window(window_name=driver.window_handles[0])

    # selenium vanilla
    # options = webdriver.ChromeOptions()
    # options.add_argument('--no-sandbox')
    # options.add_argument('--window-size=1920,1080')
    # options.add_argument('--disable-setuid-sandbox')
    # options.add_argument('--disable-dev-shm-usage')
    # driver = webdriver.Chrome(options=options)

    return driver


def get_chrome_exe_path() -> str:
    global CHROME_EXE_PATH
    if CHROME_EXE_PATH is not None:
        return CHROME_EXE_PATH
    # linux pyinstaller bundle
    chrome_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chrome', "chrome")
    if os.path.exists(chrome_path):
        if not os.access(chrome_path, os.X_OK):
            raise Exception(f'Chrome binary "{chrome_path}" is not executable. '
                            f'Please, extract the archive with "tar xzf <file.tar.gz>".')
        CHROME_EXE_PATH = chrome_path
        return CHROME_EXE_PATH
    # windows pyinstaller bundle
    chrome_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chrome', "chrome.exe")
    if os.path.exists(chrome_path):
        CHROME_EXE_PATH = chrome_path
        return CHROME_EXE_PATH
    # system
    CHROME_EXE_PATH = uc.find_chrome_executable()
    return CHROME_EXE_PATH


def get_chrome_major_version() -> str:
    global CHROME_MAJOR_VERSION
    if CHROME_MAJOR_VERSION is not None:
        return CHROME_MAJOR_VERSION

    if os.name == 'nt':
        # Example: '104.0.5112.79'
        try:
            complete_version = extract_version_nt_executable(get_chrome_exe_path())
        except Exception:
            try:
                complete_version = extract_version_nt_registry()
            except Exception:
                # Example: '104.0.5112.79'
                complete_version = extract_version_nt_folder()
    else:
        chrome_path = get_chrome_exe_path()
        process = os.popen(f'"{chrome_path}" --version')
        # Example 1: 'Chromium 104.0.5112.79 Arch Linux\n'
        # Example 2: 'Google Chrome 104.0.5112.79 Arch Linux\n'
        complete_version = process.read()
        process.close()

    CHROME_MAJOR_VERSION = complete_version.split('.')[0].split(' ')[-1]
    return CHROME_MAJOR_VERSION


def extract_version_nt_executable(exe_path: str) -> str:
    import pefile
    pe = pefile.PE(exe_path, fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
    )
    return pe.FileInfo[0][0].StringTable[0].entries[b"FileVersion"].decode('utf-8')


def extract_version_nt_registry() -> str:
    stream = os.popen(
        'reg query "HKLM\\SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Google Chrome"')
    output = stream.read()
    google_version = ''
    for letter in output[output.rindex('DisplayVersion    REG_SZ') + 24:]:
        if letter != '\n':
            google_version += letter
        else:
            break
    return google_version.strip()


def extract_version_nt_folder() -> str:
    # Check if the Chrome folder exists in the x32 or x64 Program Files folders.
    for i in range(2):
        path = 'C:\\Program Files' + (' (x86)' if i else '') + '\\Google\\Chrome\\Application'
        if os.path.isdir(path):
            paths = [f.path for f in os.scandir(path) if f.is_dir()]
            for path in paths:
                filename = os.path.basename(path)
                pattern = '\d+\.\d+\.\d+\.\d+'
                match = re.search(pattern, filename)
                if match and match.group():
                    # Found a Chrome version.
                    return match.group(0)
    return ''


def get_user_agent(driver=None) -> str:
    global USER_AGENT
    if USER_AGENT is not None:
        return USER_AGENT

    try:
        if driver is None:
            driver = get_webdriver()
        USER_AGENT = driver.execute_script("return navigator.userAgent")
        return USER_AGENT
    except Exception as e:
        raise Exception("Error getting browser User-Agent. " + str(e))
    finally:
        if driver is not None:
            driver.quit()


def start_xvfb_display():
    global XVFB_DISPLAY
    if XVFB_DISPLAY is None:
        from xvfbwrapper import Xvfb
        XVFB_DISPLAY = Xvfb()
        XVFB_DISPLAY.start()


def object_to_dict(_object):
    json_dict = json.loads(json.dumps(_object, default=lambda o: o.__dict__))
    # remove hidden fields
    return {k: v for k, v in json_dict.items() if not k.startswith('__')}
