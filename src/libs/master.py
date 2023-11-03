
import time
import queue
import random
import threading
import multiprocessing

from uuid import uuid1
from typing import Dict
from dataclasses import dataclass

from libs.logs import logger
from libs.worker import create_worker
from libs.pipe import ChildPipe, create_process_pipe
from libs.env import MAX_TASK_NUMBER, MITMPROXY, MAX_TASK_LIVE_TIME, MAX_TASK_IDLE_TIME
from libs.exception import InternalException, TimeoutException, HTTPException

q_thread = queue.Queue(maxsize=MAX_TASK_NUMBER)


class TaskState:
    busy = 'busy'
    idle = 'idle'
    with_destroyed = 'with-destroyed'
    destroyed = 'destroyed'


@dataclass
class TaskInfo:
    task_id: str
    task: multiprocessing.Process
    pipe: ChildPipe
    task_state: str
    create_time: int = int(time.time())
    update_time: int = int(time.time())


@dataclass
class ThreadTaskInfo:
    task_id: str
    task: threading.Thread
    task_state: str


class Master:
    def __init__(self):
        self.max_task_number = MAX_TASK_NUMBER
        self.max_task_live = MAX_TASK_LIVE_TIME
        self.max_task_idle = MAX_TASK_IDLE_TIME
        self.mitmproxy = MITMPROXY

        self.current_task_number = 0
        self.task_list_info: Dict[str, TaskInfo] = {}  # 保留子线程的任务

        self.thread_lock = threading.Lock()
        self.thread_local_lock = threading.Lock()

        self.manager_thread = None
        self.start_thread = None

        # self.thread_pool = ThreadPoolExecutor(max_workers=self.max_task_number)
        # self.process_pool = ProcessPoolExecutor(max_workers=self.max_task_number)

        self.thread_tasks: Dict[str, ThreadTaskInfo] = {}
        self.current_thread_number = 0

    def recv_queue(self):
        try:
            child_c: ChildPipe = q_thread.get(timeout=0.5)
            return child_c
        except queue.Empty:
            return

    def create_subprocess(self):
        p_pipe, c_pipe = create_process_pipe()
        # _create_worker = partial(create_worker, c_pipe)
        # task = self.process_pool.submit(_create_worker)

        task = multiprocessing.Process(target=create_worker, args=(c_pipe, ),
                                       kwargs={'proxy': self.mitmproxy})
        task.start()

        with self.thread_lock:
            task_id = str(uuid1())
            self.task_list_info[task_id] = TaskInfo(
                task_id=task_id,
                task=task,
                pipe=p_pipe,
                task_state=TaskState.idle,
                create_time=int(time.time()),
                update_time=int(time.time())
            )
            self.current_task_number = len(self.task_list_info)

    def update_task_status(self, task_id, task_state: str):
        if task_id not in self.task_list_info:
            return False
        # 线程锁
        with self.thread_lock:
            self.task_list_info[task_id].task_state = task_state
            self.task_list_info[task_id].update_time = int(time.time())

    def get_one_alive_subprocess(self, timeout=30):
        # 获取一个可用的子进程
        now = time.time()
        while time.time() < now + timeout:
            for task_id, task_info in self.task_list_info.items():
                if task_info.task_state == TaskState.idle:
                    self.update_task_status(task_id, TaskState.busy)

                    return task_info
            time.sleep(random.random() + 0.5)
        return InternalException("获取task id失败")

    def _manager_subprocess(self):
        # 管理子进程
        for task_id, task_info in self.task_list_info.items():
            if not task_info.task.is_alive() and task_info.task_state != TaskState.destroyed:

                logger.info(f'子进程 {task_info.task.pid} 不存活，标记删除。')
                self.update_task_status(task_id, TaskState.destroyed)
                continue

            if ((task_info.create_time < int(time.time()) - self.max_task_live
                    or task_info.update_time < int(time.time()) - self.max_task_idle)
                    and task_info.task_state == TaskState.idle):
                logger.info(f'子进程 {task_info.task.pid} 已过期，标记删除。')
                self.update_task_status(task_id, TaskState.with_destroyed)
                continue

        # kill不存活的子进程
        need_kill_id = [(task_id, task)
                        for task_id, task in self.task_list_info.items()
                        if task.task_state in [TaskState.destroyed, TaskState.with_destroyed]]
        if need_kill_id:
            with self.thread_lock:
                for task_id, task_info in need_kill_id:
                    if task_info.task_state == TaskState.with_destroyed:
                        task_info.pipe.send('kill')
                        continue
                    task_info.task.kill()
                    self.task_list_info.pop(task_id, '')
                self.current_task_number = len(self.task_list_info)

        is_not_usable = (
                len([1 for _, t in self.task_list_info.items()
                     if t.task_state == TaskState.idle]) == 0
                and self.current_task_number < self.max_task_number
        )
        if not self.task_list_info or is_not_usable:
            self.create_subprocess()

        logger.info(f'current_task_number: {self.current_task_number}')  # todo debug?

    def manager_subprocess(self):
        # 管理子进程
        while True:
            self._manager_subprocess()
            time.sleep(1)

    def _execute(self, child_c: ChildPipe, thread_id):
        task_info = self.get_one_alive_subprocess()
        if isinstance(task_info, HTTPException):
            logger.error(f'线程id: {thread_id} 获取子进程失败。 detail: {task_info.detail}')
            child_c.send(task_info)
            return

        logger.info(f'线程id: {thread_id} 获取子进程成功')

        p_pipe = task_info.pipe

        data = child_c.recv(10)
        if not data:
            logger.error(f'线程id: {thread_id} 获取信息失败')
            self.update_thread_task_taste(thread_id, TaskState.destroyed)
            child_c.send(InternalException("获取信息失败"))
            return

        logger.info(f'线程id: {thread_id} 获取任务信息成功')

        p_pipe.send(data)
        res_data = p_pipe.recv(data.timeout)
        if not res_data:
            logger.error(f'线程id: {thread_id} 子进程执行超时')
            self.update_thread_task_taste(thread_id, TaskState.destroyed)
            child_c.send(TimeoutException("子进程执行超时"))
            return

        self.update_task_status(task_info.task_id, TaskState.idle)
        self.update_thread_task_taste(thread_id, TaskState.destroyed)

        child_c.send(res_data)
        logger.info(f'线程id: {thread_id} 获取到子进程执行结果，任务结束。')

    def get_thread_task_id(self, timeout=30):
        # 获取一个可用的子线程任务id，为了保证任务数量不超过max_task_number
        now = time.time()
        while time.time() < now + timeout:
            if self.current_thread_number < self.max_task_number:
                task_id = str(uuid1())
                with self.thread_local_lock:
                    self.thread_tasks[task_id] = None
                    self.current_thread_number = len(self.thread_tasks)
                return task_id
            time.sleep(random.random() + 0.5)

        return InternalException("获取task id失败")

    def execute(self, child_c: ChildPipe, timeout=30):
        task_id = self.get_thread_task_id(timeout)
        if isinstance(task_id, HTTPException):
            logger.error(f'获取线程id失败，任务已经满了。 detail: {task_id.detail}')
            child_c.send(task_id)
            return
        logger.info(f'获取线程id {task_id} 成功，创建子线程执行任务。')

        task = threading.Thread(target=self._execute, args=(child_c, task_id))
        task.start()

        # 线程锁
        with self.thread_local_lock:
            self.thread_tasks[task_id] = ThreadTaskInfo(task=task, task_id=task_id, task_state=TaskState.idle)
        logger.info(f'线程id: {task_id} 任务执行中。')

    def update_thread_task_taste(self, task_id, task_state):
        if task_id not in self.thread_tasks:
            return False

        with self.thread_local_lock:
            self.thread_tasks[task_id].task_state = task_state

    def _thread_task_manager(self):
        for task_id, task_info in self.thread_tasks.items():
            # 加上超时时间
            if task_info and not task_info.task.is_alive() and task_info.task_state != TaskState.destroyed:
                logger.info(f'子线程 {task_info.task.native_id} 不存活，标记删除。')
                self.update_thread_task_taste(task_id, TaskState.destroyed)

        need_kill_id = [(task_id, task_info.task)
                        for task_id, task_info in self.thread_tasks.items()
                        if task_info and task_info.task_state == TaskState.destroyed]
        if need_kill_id:
            with self.thread_lock:
                for task_id, task in need_kill_id:
                    # task.stop()
                    self.thread_tasks.pop(task_id, '')
                self.current_thread_number = len(self.thread_tasks)

        logger.info(f'current_task_number: {self.current_thread_number}')  # todo debug?

    def thread_task_manager(self):
        while True:
            self._thread_task_manager()
            time.sleep(1)

    def watch_dog(self):
        while True:
            child_c: ChildPipe = self.recv_queue()
            if not child_c:
                continue
            logger.info('获取到api接口任务，准备执行任务。')
            self.execute(child_c)

    def start(self):
        # 子进程管理
        manager_subprocess = threading.Thread(target=self.manager_subprocess)
        manager_subprocess.start()
        self.manager_thread = manager_subprocess

        # 子线程任务管理
        thread_task = threading.Thread(target=self.thread_task_manager)
        thread_task.start()

        # 监听队列消息
        main_task = threading.Thread(target=self.watch_dog)
        main_task.start()

        self.start_thread = main_task
        logger.info('master 初始化完成。')


def master_start():
    master = Master()
    master.start()



