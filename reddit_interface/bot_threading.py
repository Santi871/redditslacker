import threading
import traceback
from time import sleep


class CreateThread(threading.Thread):
    def __init__(self, thread_id, name, obj, method):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.name = name
        self.obj = obj
        self.method = method

    def run(self):

        # This loop will run when the thread raises an exception
        while True:
            try:
                methodToRun = self.method(self.obj)
                break
            except AssertionError:
                print("------------\nRan into an assertion error\nTrying again\n------------")
                print(traceback.format_exc())
                sleep(1)
                continue
            except:
                print("*Unhandled exception"
                      " in thread* '%s'." % self.name)
                print(traceback.format_exc())


def own_thread(func):
    def wrapped_f(*args):
        # Create a thread with the method we called
        thread = CreateThread(1, str(func) + " thread", args[0], func)
        thread.start()

    return wrapped_f


