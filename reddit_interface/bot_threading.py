import threading
import traceback
from time import sleep
import requests.exceptions
import praw
import OAuth2Util


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
            except (requests.exceptions.HTTPError, praw.errors.HTTPException):
                sleep(2)
                continue
            except:
                print("*Unhandled exception"
                      " in thread* '%s'." % self.name)
                print(traceback.format_exc())
                sleep(10)


def own_thread(dedicated=False):

    def inner_f(func):
        def wrapped_f(*args, **kwargs):
            # Create a thread with the method we called
            if not kwargs:
                kwargs = None

            if not dedicated:
                thread = CreateThread(1, str(func) + " thread", args[0], func, kwargs)
                thread.start()
            else:
                handler = praw.handlers.MultiprocessHandler()
                r = praw.Reddit(user_agent="windows:RedditSlacker 0.3 by /u/santi871", handler=handler)
                o = OAuth2Util.OAuth2Util(r)
                o.refresh(force=True)
                r.config.api_request_delay = 1

                if kwargs is not None:
                    kwargs['r'] = r
                else:
                    kwargs = {'r': r}

                thread = CreateThread(1, str(func) + " thread", args[0], func, kwargs)
                thread.start()

        return wrapped_f
    return inner_f


