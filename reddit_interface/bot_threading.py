import threading


class CreateThread(threading.Thread):
    def __init__(self, thread_id, name, method, request):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.name = name
        self.method = method
        self.request = request

    def run(self):

        print("Starting " + self.name)
        methodToRun = self.method(self.request)
        print("Exiting " + self.name)


