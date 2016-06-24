import praw
import OAuth2Util
import requests
import json
from time import sleep
from reddit_bot import bot_threading


class CommandsHandler:

    def __init__(self):
        self.r = praw.Reddit(user_agent="windows:RedditSlacker 0.1 by /u/santi871")
        self._authenticate()

    def _authenticate(self):
        o = OAuth2Util.OAuth2Util(self.r)
        o.refresh(force=True)
        self.r.config.api_request_delay = 1

    def thread_command_request(self, request):

        thread = bot_threading.CreateThread(1, str(self.handle_command_request) + " thread",
                                            self.handle_command_request, request)
        thread.start()

    def handle_command_request(self, response_url):

        payload = {
            "text": "This is a line of text.\nAnd this is another one."
        }

        sleep(5)

        headers = {'content-type': 'application/json'}

        response = requests.post(response_url, data=json.dumps(payload), headers=headers)

        return response











