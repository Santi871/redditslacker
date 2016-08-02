import threading
import traceback
from time import sleep
import requests.exceptions


class CreateThread(threading.Thread):
    def __init__(self, thread_id, name, obj, method, kwargs=None):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.name = name
        self.obj = obj
        self.method = method
        self.kwargs = kwargs

    def run(self):

        # This loop will run when the thread raises an exception
        while True:
            try:
                if self.kwargs is not None:
                    methodToRun = self.method(self.obj, self.kwargs)
                else:
                    methodToRun = self.method(self.obj)
                break
            except AssertionError:
                print("------------\nRan into an assertion error\nTrying again\n------------")
                sleep(1)
                print(traceback.format_exc())
                continue
            except requests.exceptions.HTTPError:
                sleep(2)
                continue
            except:
                print("*Unhandled exception"
                      " in thread* '%s'." % self.name)
                print(traceback.format_exc())
                sleep(60)


def own_thread(func):
    def wrapped_f(*args, **kwargs):
        # Create a thread with the method we called
        if not kwargs:
            kwargs = None

        thread = CreateThread(1, str(func) + " thread", args[0], func, kwargs)
        thread.start()

    return wrapped_f


