# -*- coding:utf-8 -*-

# @Time   : 2023/10/30 15:33
# @Author : huangkewei


from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from libs.logs import logger
from libs.master import q_thread
from libs.pipe import create_process_pipe
from libs.models import APIRequestModel
from libs.exception import TimeoutException

app = FastAPI()


@app.exception_handler(HTTPException)
def http_exception_handler(request, exc):
    logger.error(exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


@app.get("/ping")
def ping():
    return "PONG"


@app.post("/get-content")
def get_content(api_req: APIRequestModel):
    # 创建任务
    p_pipe, c_pipe = create_process_pipe()
    q_thread.put(c_pipe)

    # 发送具体任务
    p_pipe.send(api_req)
    logger.info('发送具体任务')

    data = p_pipe.recv(api_req.timeout)
    if data is None:
        raise TimeoutException("请求超时！")
    elif isinstance(data, HTTPException):
        raise data

    logger.info('任务执行成功')

    return data
