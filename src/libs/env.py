# -*- coding:utf-8 -*-

# @Time   : 2023/11/1 14:56
# @Author : huangkewei

import os
from libs.logs import logger


def get_env(env_name, default=None, env_type=None):
    value = os.getenv(env_name, default)

    logger.info(f'{env_name}: {value}')
    if value and env_type is not None:
        value = env_type(value)
        return value


MAX_TASK_NUMBER = get_env('MAX_TASK_NUMBER', 2, int)
MITMPROXY = get_env('MITMPROXY', None)
HOST = get_env('HOST', '0.0.0.0')
PORT = get_env('PORT', 8191, int)
MAX_TASK_LIVE_TIME = get_env('MAX_TASK_LIVE_TIME', 60 * 60, int)
MAX_TASK_IDLE_TIME = get_env('MAX_TASK_IDLE_TIME', 60 * 20, int)
