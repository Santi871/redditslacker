import reddit_interface.bot as bot
import reddit_interface.utils as utils
import reddit_interface.database as db
from puni import Note
import os
import sys
from time import sleep


class RequestsHandler:

    def __init__(self):
        sections = utils.get_config_sections()
        self.configs = dict()
        self.databases = dict()
        self.bots = dict()
        for section in sections:
            self.configs[section] = utils.RSConfig(section)
            self.databases[section] = db.RedditSlackerDatabase(section + ".db")

        for sub, config in self.configs.items():
            self.bots[sub] = bot.RedditBot(self.databases[sub], self.configs[sub])
            sleep(5)

        self.temp_team_id = None
        self.temp_bot_token = None

    def handle_new_subreddit(self, oauth_response):
        self.temp_team_id = oauth_response.get('team_id')
        self.temp_bot_token = oauth_response.get('bot').get('bot_access_token')

        return "Hello! To begin, please enter `/rsconfig subreddit [your-subreddit-name]` to bind your Slack " \
               "team to your subreddit.\nHave in mind that /u/RedditSlacker should be a moderator of the subreddit," \
               "with its permissions set according to your desired usage of RedditSlacker. View the documentation for" \
               " information on moderator permissions: https://santi871.github.io/redditslacker"

    def command_response(self, request, form):
        response = utils.SlackResponse(text="Processing your request... please allow a few seconds.")
        sub = utils.get_sub_name(request.team_id)
        self.databases[sub].log_command(form)
        author = request.user
        args = request.text.split()

        if request.command == '/user':

            if len(request.text.split()) >= 1:
                username = request.text.split()[0]
                no_summary = None
                if len(request.text.split()) == 2:
                    no_summary = request.text.split()[1]
                self.bots[sub].summary(username=username, request=request, no_summary=no_summary)

            else:
                response = utils.SlackResponse("Usage: /user [username].")

        elif request.command == '/shadowban':

            if len(args) == 1:
                target_user = args[0]
                self.bots[sub].shadowban(username=target_user, author=author, request=request)
                self.bots[sub].db.update_user_status(target_user, "shadowban")
            else:
                response = utils.SlackResponse(text="Usage: /shadowban [user]")

        elif request.command == '/requestban':

            if len(args) == 1:
                url = args[0]
                if url[-1] == '/':
                    url = url[:-1]

                comment_id = url[-7:]
                self.bots[sub].request_comment_ban(cmt_id=comment_id, request=request)

            else:
                response = utils.SlackResponse(text="Usage: /requestban [comment_id]")

        elif request.command == "/track":

            if len(args) == 1:
                user = args[0]
                self.bots[sub].db.update_user_status(user, "track")
                response = utils.SlackResponse(text="Tracking user.")
            else:
                response = utils.SlackResponse(text="Usage: /track [user]")

        elif request.command == "/inspectban":

            if len(args) == 1:
                ban_note, ban_date = self.bots[sub].db.get_ban_note(args[0])

                if ban_note is not None and ban_note != "":
                    response = utils.SlackResponse(text="Found a ban:")
                    response.add_attachment(color='good')
                    response.attachments[0].add_field("Note", ban_note)
                    response.attachments[0].add_field("Issued", ban_date)
                elif ban_note == "":
                    response = utils.SlackResponse()
                    response.add_attachment(text="Error: found ban issued on *%s*, but it has no note." % ban_date,
                                            color='danger')
                else:
                    response = utils.SlackResponse()
                    response.add_attachment(text="Error: could not find ban in database.", color='danger')

            else:
                response = utils.SlackResponse(text="Usage: /inspectban [username]")

        elif request.command == '/rsconfig':

            if len(args) > 1:
                config_name = args[0]
                value = args[1]

                success = self.configs[sub].set_config(config_name, value)

                if success:
                    response = utils.SlackResponse()
                    response.add_attachment(text="Configuration updated successfully.", color='good')
                else:
                    response = utils.SlackResponse()
                    response.add_attachment(text="Configuration parameter not found.", color='danger')
            else:
                if args[0] == "tracksreset" and request.user == "santi871":
                    self.bots[sub].reset_user_tracks()
                    response = utils.SlackResponse()
                    response.add_attachment(text="User tracks reset successfully.", color='good')
                elif args[0] == "reboot":
                    response = utils.SlackResponse()
                    response.add_attachment(text="Rebooting...", color='good')
                    response.post_to_channel(token=self.configs[sub].bot_user_token, channel=request.channel_name)

                    os.execl(sys.executable, sys.executable, *sys.argv)
                elif args[0] == "list":
                    config_str = self.configs[sub].list_config()
                    response = utils.SlackResponse(text="Showing configuration for RedditSlacker")
                    response.add_attachment(text=config_str, color='good')

                else:
                    response = utils.SlackResponse()
                    response.add_attachment(text="Error: invalid parameter, or insufficient permissions.",
                                            color='danger')

        return response

    def button_response(self, request):

        response = utils.SlackResponse(text="Processing your request... please allow a few seconds.")
        sub = utils.get_sub_name(request.team_id)
        button_pressed = request.actions[0]['value'].split('_')[0]
        arg = '_'.join(request.actions[0]['value'].split('_')[1:])
        status_type = request.actions[0]['value'].split('_')[0]
        author = request.user

        if button_pressed == "permamute" or button_pressed == "unpermamute":
            response = utils.SlackResponse(text="Updated user status.")

            if button_pressed == "permamute":
                n = Note(arg, "Permamuted via RedditSlacker by Slack user '%s'" % author,
                              arg, '', 'botban')
            else:
                n = Note(arg, "Unpermamuted via RedditSlacker by Slack user '%s'" % author,
                         arg, '', 'botban')
            self.bots[sub].un.add_note(n)

            self.bots[sub].db.update_user_status(arg, status_type)

        elif button_pressed == "track":
            response = utils.SlackResponse(text="Tracking user.")
            self.bots[sub].db.update_user_status(arg, status_type)

        elif button_pressed == "untrack":
            response = utils.SlackResponse(text="Ceasing to track user.")
            self.bots[sub].db.update_user_status(arg, status_type)

        elif button_pressed == "shadowban":
            self.bots[sub].shadowban(username=arg, author=author, request=request)
            self.bots[sub].db.update_user_status(arg, status_type)

        elif button_pressed == "unshadowban":
            self.bots[sub].unshadowban(username=arg, author=author, request=request)
            self.bots[sub].db.update_user_status(arg, status_type)

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
            response.attachments[0].add_button("Track user", value="track_" + attachment_args['field']['value'])
            response.post_to_channel(token=self.configs[sub].bot_user_token, channel='#ban-requests')

            self.bots[sub].report_comment(cmt_id=arg, reason="Slack user @%s has requested a ban." % author)

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

            self.bots[sub].approve_comment(cmt_id=arg)

        elif button_pressed == "remove":
            attachment_args = utils.grab_attachment_args(request.original_message)

            response = utils.SlackResponse()
            response.add_attachment(text=attachment_args['text'], title=attachment_args['title'],
                                    title_link=attachment_args['title_link'],
                                    color='good', footer="Removed by @%s" % author)
            response.attachments[0].add_field(title=attachment_args['field']['title'],
                                              value=attachment_args['field']['value'])

            self.bots[sub].remove_comment(cmt_id=arg)

        elif button_pressed == "summary":
            self.bots[sub].summary(request=request, username=arg, replace_original=False)
            response = None

        return response
