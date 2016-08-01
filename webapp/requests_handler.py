import reddit_interface.bot as bot
import reddit_interface.utils as utils
import reddit_interface.database as db


class RequestsHandler:

    def __init__(self):
        self.db = db.RedditSlackerDatabase('redditslacker_main.db')
        self.reddit_bot = bot.RedditBot(self.db)

    def command_response(self, request):
        response = utils.SlackResponse(text="Processing your request... please allow a few seconds.")

        if request.command == '/summary':

            response = utils.SlackResponse(text='How many comments to load?')
            response.add_attachment(fallback="You are unable to choose a number of comments to load.",
                                    callback_id="summary_" + request.text, color="#3AA3E3",
                                    text="Have in mind loading 1000 comments takes a little longer.")
            response.attachments[0].add_button("500")
            response.attachments[0].add_button('1000')

        elif request.command == '/user':

            if len(request.text.split()) > 1:
                username = request.text.split()[0]
                no_summary = None
                if len(request.text.split()) == 2:
                    no_summary = request.text.split()[1]
                self.reddit_bot.summary(username=username, request=request, no_summary=no_summary)

            else:
                response = utils.SlackResponse("Usage: /user [username].")

        return response

    def button_response(self, request):

        response = utils.SlackResponse(text="Processing your request... please allow a few seconds.")
        callback_id = request.callback_id
        button_pressed = request.actions[0]['value'].split('_')[0]
        target_user = '_'.join(request.actions[0]['value'].split('_')[1:]).lower()
        status_type = request.actions[0]['value'].split('_')[0]
        author = request.user

        special_buttons = ["shadowban", "unshadowban", "track", "untrack", 'verify']

        if callback_id.startswith("user") and button_pressed not in special_buttons:
            response = utils.SlackResponse(text="Updated user status.")
            self.reddit_bot.db.update_user_status(target_user, status_type)

        elif button_pressed == "track":
            response = utils.SlackResponse(text="Updated user status.")
            self.reddit_bot.db.update_user_status(target_user, status_type)

            with open("tracked_users.txt", "a+") as text_file:
                print(target_user + ",", file=text_file, end='')
        elif button_pressed == "untrack":
            response = utils.SlackResponse(text="Updated user status.")
            self.reddit_bot.db.update_user_status(target_user, status_type)

        elif button_pressed == "shadowban":
            response = self.reddit_bot.shadowban(target_user, author)
            self.reddit_bot.db.update_user_status(target_user, status_type)

        elif button_pressed == "unshadowban":
            response = self.reddit_bot.unshadowban(target_user, author)
            self.reddit_bot.db.update_user_status(target_user, status_type)

        elif button_pressed == "verify":
            attachment_text = request.original_message['attachments'][0]['text']
            attachment_title = request.original_message['attachments'][0]['title']
            attachment_title_link = request.original_message['attachments'][0]['title_link']

            response = utils.SlackResponse()
            response.add_attachment(text=attachment_text, title=attachment_title, title_link=attachment_title_link,
                                    color='danger', footer="Verified by @%s" % author)

        return response


























