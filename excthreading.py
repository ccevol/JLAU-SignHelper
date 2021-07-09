# -*- coding: utf-8 -*-
"""
@File                : excthreading.py
@Github              : https://github.com/Jayve
@Last modified by    : Jayve
@Last modified time  : 2021-6-18 18:38:40
"""
import threading


# 对Python的多线程模块threading进行功能扩展，实现多线程抛出异常的功能。
class ExcThread(threading.Thread):

    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, verbose=None):
        threading.Thread.__init__(self, group, target, name, args, kwargs)
        if kwargs is None:
            kwargs = {}
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
        self.exc = None

    def run(self):
        try:
            # 可能抛出异常
            if self.__target:
                self.__target(*self.__args, **self.__kwargs)
        except Exception:
            import sys
            self.exc = sys.exc_info()
            # 保存抛出的异常的详细信息，但不重复抛出。
        finally:
            # 如果线程运行的函数的参数具有指向线程的成员，避免陷入调用循环。
            del self.__target, self.__args, self.__kwargs

    def join(self, timeout=None):
        threading.Thread.join(self, timeout)
        if self.exc:
            msg = "Thread '%s' threw an exception: %s" % (self.getName(), self.exc[1])
            new_exc = Exception(msg)
            raise new_exc.with_traceback(self.exc[2])
            # 在join方法中抛出子线程异常

    @classmethod
    def currentThread(cls):
        return threading.currentThread()
