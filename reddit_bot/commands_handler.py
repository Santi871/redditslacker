import requests
import json
import reddit_bot.bot as bot
import reddit_bot.bot_threading as bot_threading
import reddit_bot.utils as utils


class CommandsHandler:

    def __init__(self):
        self.reddit_bot = bot.RedditBot(load_side_threads=False)

    def thread_command_request(self, request):
        # Refactor into a decorator

        thread = bot_threading.CreateThread(1, str(self.handle_command_request) + " thread",
                                            self.handle_command_request, request)
        thread.start()

    def handle_command_request(self, request):

        response_url = request.get('response_url')
        try:
            if str(type(request)) == "<class 'werkzeug.datastructures.ImmutableMultiDict'>":
                command = request.get('command')[1:]
                payload = getattr(self.reddit_bot, command)(split_text=request.get('text').split(),
                                                            author=request.get('user_name'))
            else:
                command = request.get('command')
                username = request.get('target_user')
                limit = int(request.get('limit'))
                payload = getattr(self.reddit_bot, command)(limit=limit, username=username)

            response = requests.post(response_url, data=json.dumps(payload),
                                     headers={'content-type': 'application/json'})

            return response
        except Exception as e:
            print("-----------------------\nUnexpected exception\n-----------------------")
            print(e)

    @staticmethod
    def define_command_response(request):
        response = None

        if request.get('command') == '/summary':

            button_a = utils.SlackButton("500")
            button_b = utils.SlackButton("1000")
            response = utils.SlackResponse(text='How many comments to load?')
            response.add_attachment(fallback="You are unable to choose a number of comments to load.",
                                    callback_id="summary_" + request['text'], color="#3AA3E3",
                                    text="Have in mind loading 1000 comments takes a little longer.",
                                    buttons=[button_a, button_b])

            response = response.response_dict

        return response

    @staticmethod
    def find_button_request_args(request):

        ret_dict = dict()
        payload_dict = json.loads(request['payload'][0])
        command = payload_dict['callback_id'].split('_')[0]
        if command == "summary":
            ret_dict['limit'] = payload_dict['actions'][0]['value']
            ret_dict['command'] = 'summary'
            ret_dict['target_user'] = payload_dict['callback_id'].split('_')[1]
            ret_dict['response_url'] = payload_dict['response_url']
        return ret_dict
























