# -*- coding:utf-8 -*-

# @Time   : 2023/10/31 09:55
# @Author : huangkewei


from typing import Union, List
from pydantic import BaseModel, HttpUrl, Field, field_validator

from enum import Enum


class Method(str, Enum):
    get = 'get'
    GET = 'GET'
    post = 'post'
    POST = 'POST'


class FetchType(str, Enum):
    random = 1
    local = 2


class WaitUntil(str, Enum):
    load = 'load'
    dom_content_loaded = 'domcontentloaded'
    network_idle_0 = 'networkidle0'
    network_idle_2 = 'networkidle2'


class RequestProxyType(str, Enum):
    http = 'http'
    socks5 = 'socks5'


class APIRequestModel(BaseModel):
    url: HttpUrl = Field(description='请求网址')
    headers: dict = Field(default_factory=dict, description='请求头')
    cookies: dict = Field(None, description='cookies')
    user_agent: str = Field('', description='指定浏览器UA')
    timeout: int = Field(30, description='设置访问超时，默认30秒')
    cache_enabled: bool = Field(True, description='是否允许缓存')
    sleep: int = Field(0, description='单位:s。 延迟返回，网页加载完成后等待指定时间执行。')
    proxy: Union[dict, str] = Field(None, description='指定代理服务')
    fetch_type: FetchType = Field(FetchType.random, description='1. 随机分配一台机器请求。 2. 采用本地模式请求')  # todo 本地模式。nginx处理
    js_source: str = Field(None, description='执行自定义Puppeteer js')  # todo 转换为source js
    uri: str = Field(None, description='请求接口类型参数，方法分流。')
    content: str = Field(None, description='传入原始html 渲染 不进行url请求')
    wait_until: WaitUntil = Field(WaitUntil.load, description="等待加载")  # todo Selenium 中没有对应的等待策略
    searchstr: str = Field(None, description='网页中出现指定字符串才返回，否则一直等待30s')
    restr: str = Field(None, description=' 网页中出现指定正则表达式匹配结果才返回，否则一直等待30s')
    select_expression: str = Field(None, description='出现指定 select 路径，否则一直等待30s')
    ignore_resource: List[str] = Field(default_factory=list, description='不加载指定资源')  # todo Selenium 中没有直接忽略资源的方法
    offline_mode: bool = Field(False, description='离线模式。静态网页渲染可尝试设置离线模式，加快返回速度')  # todo 在线和离线有什么区别？
    sdk_version: str = Field(None, description='兼容老版本')  # todo
    code: str = Field(None, description='function 执行原始方法')
    print_stack: bool = Field(False, description='打印请求堆栈')  # todo 返回请求堆栈
    context: dict = Field(default_factory=dict, description='function 接口传入参数')
    request_proxy: str = Field('', description=" 请求代理  '115.216.42.180:31081'，实际使用的代理。")  # 和proxy有啥区别
    request_proxy_type: RequestProxyType = Field(RequestProxyType.http, description="代理类型  http  socks5")
    ignore_proxy_resource: str = Field(None, description=" 忽略代理资源   图片 js  css 默认不走代理")


    # 老版本无头保留，加一个字段可以在nginx进行分流。

    # self
    method: Method = Method.GET
    params: dict = None
    data: dict = None

    only_cookies: bool = False

    @field_validator('ignore_resource')
    @classmethod
    def validate_ignore_resource(cls, value: List[str]) -> List[str]:
        allowed_values = ["image", "stylesheet", "media", "eventsource", "websocket"]
        for resource in value:
            if resource not in allowed_values:
                raise ValueError(f'Invalid resource: {resource}')
        return value


class APIResponseModel(BaseModel):
    url: HttpUrl
    status_code: int
    headers: dict = None
    response: dict = None

    # 接口所需
    msg: str = None
    content: str = None
    cookies: dict = None


def api_request_test():
    json_data = {
        'url': 'https://ip.sb/',
        'ignore_resource': ['image']
    }
    api_data = APIRequestModel(**json_data)

    print(api_data)


if __name__ == '__main__':
    api_request_test()
