import json
import logging
import os

from selenium.webdriver.chrome.webdriver import WebDriver
import undetected_chromedriver as uc

FLARESOLVERR_VERSION = None
CHROME_MAJOR_VERSION = None
USER_AGENT = None


def get_config_log_html() -> bool:
    return os.environ.get('LOG_HTML', 'false').lower() == 'true'


def get_flaresolverr_version() -> str:
    global FLARESOLVERR_VERSION
    if FLARESOLVERR_VERSION is not None:
        return FLARESOLVERR_VERSION

    package_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'package.json')
    with open(package_path) as f:
        FLARESOLVERR_VERSION = json.loads(f.read())['version']
        return FLARESOLVERR_VERSION


def get_webdriver() -> WebDriver:
    logging.debug('Launching web browser...')

    # undetected_chromedriver
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    # todo: this param shows a warning in chrome headfull
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # note: headless mode is detected
    # options.headless = True

    # if we are inside the Docker container, we avoid downloading the driver
    driver_exe_path = None
    version_main = None
    if os.path.exists("/app/chromedriver"):
        driver_exe_path = "/app/chromedriver"
    else:
        version_main = get_chrome_major_version()

    # downloads and patches the chromedriver
    # todo: if we don't set driver_executable_path it downloads, patches, and deletes the driver each time
    driver = uc.Chrome(options=options, driver_executable_path=driver_exe_path, version_main=version_main)

    # selenium vanilla
    # options = webdriver.ChromeOptions()
    # options.add_argument('--no-sandbox')
    # options.add_argument('--window-size=1920,1080')
    # options.add_argument('--disable-setuid-sandbox')
    # options.add_argument('--disable-dev-shm-usage')
    # driver = webdriver.Chrome(options=options)

    return driver


def get_chrome_major_version() -> str:
    global CHROME_MAJOR_VERSION
    if CHROME_MAJOR_VERSION is not None:
        return CHROME_MAJOR_VERSION

    chrome_path = uc.find_chrome_executable()
    # Example 1: 'Chromium 104.0.5112.79 Arch Linux\n'
    # Example 2: 'Google Chrome 104.0.5112.79 Arch Linux\n'
    process = os.popen(f"{chrome_path} --version")
    complete_version = process.read()
    process.close()
    CHROME_MAJOR_VERSION = complete_version.split('.')[0].split(' ')[-1]
    return CHROME_MAJOR_VERSION


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


def object_to_dict(_object):
    json_dict = json.loads(json.dumps(_object, default=lambda o: o.__dict__))
    # remove hidden fields
    return {k: v for k, v in json_dict.items() if not k.startswith('__')}
