# -*- coding:utf-8 -*-

# @Time   : 2023/11/1 10:11
# @Author : huangkewei

import uvicorn

from libs.logs import logger
from libs.env import PORT, HOST
from libs.master import master_start
from libs.app import app


def main():
    master_start()

    # 启动参数
    uvicorn.run(app, host=HOST, port=PORT)
    logger.info('主进程已启动')


if __name__ == '__main__':
    main()
