import reddit_interface.bot as bot
import reddit_interface.utils as utils
import reddit_interface.database as db


class RequestsHandler:

    def __init__(self):
        self.db = db.RedditSlackerDatabase('redditslacker_main.db')
        self.config = utils.RSConfig("config.ini")
        self.reddit_bot = bot.RedditBot(self.db, self.config)

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

        elif request.command == '/rsconfig':

            args = request.text.split()
            config_name = args[0]
            value = args[1]

            success = self.config.set_config(config_name, 'explainlikeimfive', value)

            if success:
                response = utils.SlackResponse()
                response.add_attachment(text="Configuration updated successfully.", color='good')
            else:
                response = utils.SlackResponse()
                response.add_attachment(text="Configuration parameter not found.", color='danger')

        return response

    def button_response(self, request):

        response = utils.SlackResponse(text="Processing your request... please allow a few seconds.")
        button_pressed = request.actions[0]['value'].split('_')[0]
        arg = '_'.join(request.actions[0]['value'].split('_')[1:]).lower()
        status_type = request.actions[0]['value'].split('_')[0]
        author = request.user

        if button_pressed == "permamute" or button_pressed == "unpermamute":
            response = utils.SlackResponse(text="Updated user status.")
            self.reddit_bot.db.update_user_status(arg, status_type)

        elif button_pressed == "track":
            response = utils.SlackResponse(text="Tracking user.")
            self.reddit_bot.db.update_user_status(arg, status_type)

        elif button_pressed == "untrack":
            response = utils.SlackResponse(text="Ceasing to track user.")
            self.reddit_bot.db.update_user_status(arg, status_type)

        elif button_pressed == "shadowban":
            response = self.reddit_bot.shadowban(arg, author)
            self.reddit_bot.db.update_user_status(arg, status_type)

        elif button_pressed == "unshadowban":
            response = self.reddit_bot.unshadowban(arg, author)
            self.reddit_bot.db.update_user_status(arg, status_type)

        elif button_pressed == "verify":
            attachment_args = utils.grab_attachment_args(request.original_message)

            response = utils.SlackResponse(request.original_message.get('text', ''))
            response.add_attachment(text=attachment_args['text'], title=attachment_args['title'],
                                    title_link=attachment_args['title_link'],
                                    color='good', footer="Verified by @%s" % author)

        elif button_pressed == "banreq":
            attachment_args = utils.grab_attachment_args(request.original_message)

            response = utils.SlackResponse(text="@%s has requested a ban. Comment:" % author)
            response.add_attachment(text=attachment_args['text'], title=attachment_args['title'],
                                    color='good', title_link=attachment_args['title_link'], callback_id='banreq')
            response.attachments[0].add_field(title=attachment_args['field']['title'],
                                              value=attachment_args['field']['value'])
            response.attachments[0].add_button("Verify", value="verify", style='primary')
            response.post_to_channel('#ban-requests')

            self.reddit_bot.remove_comment(cmt_id=arg)

            response = utils.SlackResponse()
            response.add_attachment(text=attachment_args['text'], title=attachment_args['title'],
                                    color='good', footer="Ban requested by @%s" % author,
                                    title_link=attachment_args['title_link'])
            response.attachments[0].add_field(title=attachment_args['field']['title'],
                                              value=attachment_args['field']['value'])

        elif button_pressed == "approve":
            attachment_args = utils.grab_attachment_args(request.original_message)

            response = utils.SlackResponse()
            response.add_attachment(text=attachment_args['text'], title=attachment_args['title'],
                                    title_link=attachment_args['title_link'],
                                    color='good', footer="Approved by @%s" % author)
            response.attachments[0].add_field(title=attachment_args['field']['title'],
                                              value=attachment_args['field']['value'])

            self.reddit_bot.approve_comment(cmt_id=arg)

        elif button_pressed == "remove":
            attachment_args = utils.grab_attachment_args(request.original_message)

            response = utils.SlackResponse()
            response.add_attachment(text=attachment_args['text'], title=attachment_args['title'],
                                    title_link=attachment_args['title_link'],
                                    color='good', footer="Removed by @%s" % author)
            response.attachments[0].add_field(title=attachment_args['field']['title'],
                                              value=attachment_args['field']['value'])

            self.reddit_bot.remove_comment(cmt_id=arg)

        return response


























