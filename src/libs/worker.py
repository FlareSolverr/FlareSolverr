
import os
import threading
import multiprocessing
from uuid import uuid1

from utils import start_xvfb_display
from libs.logs import logger
from libs.client import browser_request, APIRequestModel, APIResponseModel, SESSIONS_STORAGE
from libs.pipe import ChildPipe, create_process_pipe


class Worker:
    def __init__(self,
                 c_pipe: ChildPipe,
                 proxy=None
                 ):
        self.c_pipe = c_pipe
        self.session_id = None
        self.session = None
        self.xvfb_pid = None
        self.browser_pid = None

        self.proxy = proxy

        self._init_session()

    def _init_session(self):
        """
        初始化session
        """
        self.create()

        logger.info('子进程初始化浏览器完成。')

    def create(self):
        """
        创建一个新的浏览器
        """
        self.session_id = str(uuid1())
        XVFB_DISPLAY = start_xvfb_display()
        self.xvfb_pid = XVFB_DISPLAY.proc.pid if XVFB_DISPLAY and XVFB_DISPLAY.proc else None
        self.session, _ = SESSIONS_STORAGE.create(self.session_id, proxy=self.proxy)
        self.browser_pid = self.session.driver.browser_pid

        logger.info(f'子进程创建浏览器。session_id: {self.session_id}, browser_pid: {self.browser_pid}, xvfb_pid: {self.xvfb_pid}')

        return self.session_id

    def destroy(self):
        """
        删除一个浏览器
        """

        destroy_status = SESSIONS_STORAGE.destroy(self.session_id)

        try:
            if self.xvfb_pid:
                os.kill(self.xvfb_pid, 9)

            # kill browser
            os.kill(self.browser_pid, 9)
        except ProcessLookupError:
            logger.info('进程已经不存在。')

        logger.info(f'子进程删除浏览器。 session_id: {self.session_id}')

        return destroy_status

    def send_message(self, res_msg: APIResponseModel):
        """
        往管道中发送信息
        """
        self.c_pipe.send(res_msg)

    def execute(self, req: APIRequestModel) -> APIResponseModel:
        """
        执行接收过来的信息
        """

        logger.info('子进程开始执行请求任务。')
        res = browser_request(req, self.session_id)
        logger.info('子进程执行请求任务完成。')

        return res

    def worker_watch_dog(self):
        """
        检测conn管道信息
        """
        while True:
            data: APIRequestModel = self.c_pipe.recv(0.5)
            if data is None:
                continue

            if data == 'kill':
                self.destroy()
                break

            logger.info('子进程获取到请求任务。')
            res_data = self.execute(data)
            self.send_message(res_data)

    def watch_dog(self):
        t = threading.Thread(target=self.worker_watch_dog)
        t.start()
        logger.info('子进程开始监测管道信息。')


def create_worker(c_pipe: ChildPipe, proxy=None):
    # create one worker

    worker = Worker(c_pipe=c_pipe, proxy=proxy)
    # worker.watch_dog()
    worker.worker_watch_dog()

    return worker


def worker_test():
    json_data = {
        'url': 'https://sdbhgj.youzhicai.com/index/Notice.html?id=2ed513c0-bc27-45ed-8d82-a200d52f54f7&n=1'
    }
    api_res = APIRequestModel(**json_data)

    p_pipe, c_pipe = create_process_pipe()

    task = multiprocessing.Process(target=create_worker, args=(c_pipe,))
    task.start()

    p_pipe.send(api_res)
    while True:
        data = p_pipe.recv()
        if data is not None:
            print(1111)
            break
    print(data)


def worker_test_2():
    json_data = {
        'url': 'https://sdbhgj.youzhicai.com/index/Notice.html?id=2ed513c0-bc27-45ed-8d82-a200d52f54f7&n=1'
    }
    api_res = APIRequestModel(**json_data)

    task = multiprocessing.Process(target=browser_request, args=(api_res, '132'))
    task.start()
    task.join()


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
    worker_test_3()
