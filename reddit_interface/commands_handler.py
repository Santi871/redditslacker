import requests
import json
import reddit_interface.bot as bot
import reddit_interface.bot_threading as bot_threading
import reddit_interface.utils as utils
import reddit_interface.database as db


class CommandsHandler:

    def __init__(self, debug=False):
        self.db = db.RedditSlackerDatabase()
        self.reddit_bot = bot.RedditBot(self.db, load_side_threads=True)
        self.debug = debug

    def thread_command_execution(self, request):
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
                                                            author=request.get('user_name'), debug=self.debug)
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

    def define_command_response(self, request):
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
        elif request.get('command') == '/user':

            if len(request.get('text').split()) == 1:
                username = request.get('text')
                combined_karma = self.reddit_bot.get_combined_karma(username)
                account_creation = self.reddit_bot.get_created_datetime(username)

                summary_button = utils.SlackButton("Summary", "summary_" + username, style='primary')
                ban_button = utils.SlackButton("Ban", "ban_" + username, style='danger')
                shadowban_button = utils.SlackButton("Shadowban", "shadowban_" + username, style='danger')
                field_a = utils.SlackField("Combined karma", combined_karma)
                field_b = utils.SlackField("Redditor since", account_creation)
                response = utils.SlackResponse()
                response.add_attachment(title='/u/' + username, title_link="https://www.reddit.com/user/" + username,
                                        color='#3AA3E3', callback_id='user_' + request.get('text'),
                                        fields=[field_a, field_b], buttons=[summary_button, ban_button,
                                                                            shadowban_button])

                response = response.response_dict

            else:
                response = "Usage: /user [username]."

        return response

    def handle_button_request(self, payload_dict):

        response = "Processing your request... please allow a few seconds."
        callback_id = payload_dict.get('callback_id')

        if callback_id.startswith("user"):
            if payload_dict.get('actions')[0]['value'].startswith("summary"):
                username = payload_dict.get('actions')[0]['value'].split('_')[1]

                summary_args_dict = dict()
                summary_args_dict['command'] = "summary"
                summary_args_dict['limit'] = 500
                summary_args_dict['target_user'] = username
                summary_args_dict['response_url'] = payload_dict['response_url']

                self.thread_command_execution(summary_args_dict)

        return response

    @staticmethod
    def find_button_request_args(payload_dict):

        ret_dict = dict()
        command = payload_dict['callback_id'].split('_')[0]
        if command == "summary":
            ret_dict['limit'] = payload_dict['actions'][0]['value']
            ret_dict['command'] = 'summary'
            ret_dict['target_user'] = payload_dict['callback_id'].split('_')[1]
            ret_dict['response_url'] = payload_dict['response_url']
        return ret_dict
























