# -*- coding:utf-8 -*-

# @Time   : 2023/10/30 17:34
# @Author : huangkewei

import multiprocessing


class ParentPipe:
    def __init__(self, p_send, p_recv):
        self.p_send = p_send
        self.p_recv = p_recv

    def send(self, data):
        self.p_send.send(data)

    def recv(self, timeout=1):
        if self.p_recv.poll(timeout=timeout):
            return self.p_recv.recv()


class ChildPipe:
    def __init__(self, c_send, c_recv):
        self.c_send = c_send
        self.c_recv = c_recv

    def send(self, data):
        self.c_send.send(data)

    def recv(self, timeout=1):
        if self.c_recv.poll(timeout=timeout):
            return self.c_recv.recv()


def create_process_pipe():
    # 父进程发，子进程收
    p_send, c_recv = multiprocessing.Pipe()

    # 父进程收，子进程发
    p_recv, c_send = multiprocessing.Pipe()

    p_pipe = ParentPipe(p_send, p_recv)

    c_pipe = ChildPipe(c_send, c_recv)

    return p_pipe, c_pipe


def child_test(c_pipe: ChildPipe):
    data = c_pipe.recv()
    print(f'child run: {data}')
    c_pipe.send('哈哈')


def parent_test():
    p_pipe, c_pipe = create_process_pipe()

    task = multiprocessing.Process(target=child_test, args=(c_pipe, ))
    task.start()

    p_pipe.send('你好')
    data = p_pipe.recv()
    print(data)


if __name__ == '__main__':
    parent_test()

