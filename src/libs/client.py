# -*- coding:utf-8 -*-

# @Time   : 2023/10/31 09:44
# @Author : huangkewei

import json
import re
import time
import logging
import random

from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import undetected_chromedriver as uc
from dtos import (ChallengeResolutionT, V1RequestBase)
from flaresolverr_service import _resolve_challenge, SESSIONS_STORAGE
from libs.models import APIRequestModel, APIResponseModel

logger = logging.getLogger(__name__)


def browser_request(req: APIRequestModel, session_id: str, method: str = 'GET') -> APIResponseModel:
    if req.content is not None:
        # 只渲染
        return render_html(session_id, req.content)

    v1_req = api_request_to_v1(req, session_id)

    now_time = time.time()
    # 调用主方法
    v1_res = _resolve_challenge(v1_req, method)

    # 扩展方法
    session, _ = SESSIONS_STORAGE.get(session_id)
    driver = session.driver

    # 将iframe标签替换
    replace_iframe_element(driver)

    # 等待字符串
    if req.searchstr:
        wait_for_str(driver, req.searchstr, req.timeout - int(time.time() - now_time))

    # 等待正则表达式
    if req.restr:
        wait_for_restr(driver, req.restr, req.timeout - int(time.time() - now_time))

    # 等待select表达式
    if req.select_expression:
        wait_for_selector(driver, req.select_expression, req.timeout - int(time.time() - now_time))

    # 执行原始js code
    if req.code:
        execute_js_script(driver, req.code, req.context)

    # 至少等待req.sleep秒
    real_sleep = req.sleep - int(time.time() - now_time)
    if real_sleep > 0:
        time.sleep(real_sleep)

    # 获取page_source
    v1_res.result.response = driver.page_source

    res = v1_response_to_api(v1_res)

    return res


def api_request_to_v1(req: APIRequestModel, session_id: str) -> V1RequestBase:
    # 根据信息转换为V1RequestBase
    cookies = req.cookies or {}
    cookies['real-proxy'] = req.request_proxy
    cookies['real-headers'] = json.dumps(req.headers) if req.headers else None
    cookies['real-user-agent'] = req.user_agent  # todo 兼容
    cookies_new = [{'name': k, 'value': v}
                   for k, v in cookies.items() if v]

    json_data = {
        'cmd': 'request.get',
        'url': str(req.url),
        'cookies': cookies_new or None,
        'maxTimeout': req.timeout * 1000,
        'session': session_id,
        'returnOnlyCookies': req.only_cookies,
    }

    v1_req = V1RequestBase(json_data)

    return v1_req


def v1_response_to_api(res: ChallengeResolutionT) -> APIResponseModel:
    # 根据ChallengeResolutionT转换为APIResponseModel
    cookies = {d['name']: d['value']
               for d in res.result.cookies}

    json_data = {
        'url': res.result.url,
        'status_code': 200 if res.status == 'ok' else 500,
        'response': res.result.__dict__,  # todo 测试，筛选 __ 。

        'msg': 'success' if res.status == 200 else 'err',
        'content': res.result.response,
        'cookies': cookies,
    }
    print(res.result.cookies)

    api_res = APIResponseModel(**json_data)

    return api_res


def replace_iframe_element(driver):
    # todo 只测试了一个网址，其他网址需要再测试一下
    # 查找所有的 iframe 元素
    iframes = driver.find_elements(by=By.TAG_NAME, value='iframe')

    # 遍历每个 iframe，并替换源网站中的 <iframe> 标签为对应的内容
    for index, iframe in enumerate(iframes):
        # 切换到当前的 iframe
        driver.switch_to.frame(iframe)

        # 获取当前 iframe 的内容
        iframe_content = driver.page_source

        # 切换回默认的上下文
        driver.switch_to.default_content()

        # 替换源网站中的 <iframe> 标签为对应的内容
        driver.execute_script("arguments[0].outerHTML = arguments[1];", iframe, iframe_content)


def chrome_options(req: APIRequestModel):
    # todo 怎么嵌入到ChromeOptions？

    options = uc.ChromeOptions()
    # 是否开启缓存
    if req.cache_enabled:
        options.add_argument('--disk-cache-size=0')

    return options


def render_html(session_id: str, html: str):
    session, fresh = SESSIONS_STORAGE.get(session_id)
    driver = session.driver

    # 打开一个空白页面
    driver.get('about:blank')

    # 将 HTML 代码作为字符串传入 JavaScript 函数
    js_code = f'''
    document.open();
    document.write("{html}");
    document.close()
    '''
    driver.execute_script(js_code)
    driver.implicitly_wait(10)

    page_source = driver.page_source

    return page_source


def wait_for_str(driver, search_str, timeout=30):
    now = int(time.time())
    while int(time.time()) < now + timeout:
        page_source = driver.page_source
        if search_str in page_source:
            return True
        time.sleep(random.random() + 0.5)

    return False


def wait_for_restr(driver, restr, timeout=30):
    now = int(time.time())
    p = re.compile(restr, re.S)
    while int(time.time()) < now + timeout:
        page_source = driver.page_source
        res_lst = re.findall(p, page_source)
        if res_lst:
            return True
        time.sleep(random.random() + 0.5)

    return False


def wait_for_selector(driver, selector, timeout=30):
    wait = WebDriverWait(driver, timeout)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        return True
    except TimeoutException as e:
        return False


def execute_js_script(driver, script, context: dict):
    # todo 异常捕获
    driver.execute_script(script, **context)


def render_html_test():
    session_id = '123'
    with open('./必应.html', 'r') as f:
        html = f.read()
    html = '<html><body><h1>Hello, World!</h1></body></html>'
    page_source = render_html(session_id, html)

    print(page_source)


def worker_test_3():
    json_data = {
        'url': 'https://sdbhgj.youzhicai.com/index/Notice.html?id=2ed513c0-bc27-45ed-8d82-a200d52f54f7&n=1'
    }
    api_res = APIRequestModel(**json_data)
    browser_request(api_res, '132')
    # task = multiprocessing.Process(target=browser_request, args=(api_res, '132'))
    # task.start()
    # task.join()


if __name__ == '__main__':
    # render_html_test()
    worker_test_3()
