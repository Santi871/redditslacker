import praw
import OAuth2Util
from praw.handlers import MultiprocessHandler
from imgurpython import ImgurClient
import matplotlib.pyplot as plt
import math
import numpy as np
from time import sleep
import os
import reddit_interface.utils as utils
import reddit_interface.bot_threading as bot_threading
import traceback
import puni
import datetime
import requests.exceptions

SLACK_BOT_TOKEN = utils.get_token('SLACK_BOT_TOKEN')


class RedditBot:
    """Class that implements a Reddit bot to perform moderator actions in a specific subreddit"""

    def __init__(self, db, config, load_side_threads=True, debug=False):
        handler = MultiprocessHandler()
        self.db = db
        self.config = config
        self.r = praw.Reddit(user_agent="windows:RedditSlacker 0.3 by /u/santi871", handler=handler)
        self.imgur = ImgurClient(utils.get_token('IMGUR_CLIENT_ID'), utils.get_token('IMGUR_CLIENT_SECRET'))
        self.debug = debug

        try:
            self._authenticate(self.r)
        except AssertionError:
            print("Bot authentication failed.")

        self.subreddit_name = config.subreddit
        self.un = puni.UserNotes(self.r, self.r.get_subreddit(self.subreddit_name))

        self.usergroup_owner = 'santi871'
        self.usergroup_mod = ('santi871', 'akuthia', 'mason11987', 'mike_pants', 'mjcapples', 'securethruobscure',
                              'snewzie', 'teaearlgraycold', 'thom.willard', 'yarr', 'cow_co', 'sterlingphoenix',
                              'hugepilchard', 'curmudgy', 'h2g2_researcher', 'jim777ps3', 'letstrythisagain_',
                              'mr_magnus', 'terrorpaw', 'kodack10', 'doc_daneeka', 'heliopteryx')

        self.already_done = self.fetch_already_done("already_done.txt")

        if load_side_threads:

            if config.monitor_comments:
                self.comments_feed()
            if config.monitor_modlog:
                self.track_users()
            if config.monitor_modmail:
                self.monitor_modmail()
            if config.remove_unflaired:
                self.handle_unflaired()

            self.log_bans()

    def create_praw_instance(self, authed=True):
        r = praw.Reddit(user_agent="windows:RedditSlacker 0.3 by /u/santi871", handler=MultiprocessHandler())

        if authed:
            self._authenticate(r)
        return r

    @staticmethod
    def _authenticate(r):
        o = OAuth2Util.OAuth2Util(r)
        o.refresh(force=True)
        r.config.api_request_delay = 1

    @staticmethod
    def fetch_already_done(filename):

        already_done = []
        try:
            with open(filename, "r") as text_file:
                already_done = text_file.read().split(",")

                if int(os.stat('already_done.txt').st_size) >= 409600:
                    already_done = already_done[int(len(already_done) * 0.75):]
                try:
                    already_done.remove('')
                except ValueError:
                    pass

        except FileNotFoundError:
            with open(filename, "a+"):
                pass

        with open(filename, 'w+') as text_file:
            text_file.write(','.join(already_done))

        with open(filename, "r") as text_file:
            already_done = text_file.read().split(",")

        return already_done

    def get_last_note(self, username):
        notes = list(self.un.get_notes(username))

        if len(notes) == 0:
            return "No usernotes attached to this user."
        else:
            return str(notes[0].note)

    def add_note(self, username, author, note_type):

        n = puni.Note(username, "Permamuted via RedditSlacker by Slack user '%s'" % author,
                      username, '', note_type)
        self.un.add_note(n)

    def get_user_name(self, username):
        redditor = self.r.get_redditor(username)

        return redditor.name

    @bot_threading.own_thread()
    def request_comment_ban(self, cmt_id, request):

        author = request.user

        try:
            
            comment = self.r.get_info(thing_id='t1_' + cmt_id)
        except praw.errors.NotFound:
            comment = None

        response = utils.SlackResponse()
        if comment is None:
            response.add_attachment(text="Error: comment not found.", color='danger')
            request.delayed_response(response)
        else:
            response = utils.SlackResponse(text="@%s has requested a ban. Comment:" % author)
            response.add_attachment(text=comment.body, title=comment.submission.title,
                                    color='good', title_link=comment.submission.permalink,
                                    callback_id='banreq')
            response.attachments[0].add_field(title="Author",
                                              value=comment.author.name)
            response.attachments[0].add_button("Verify", value="verify", style='primary')
            response.attachments[0].add_button("Track user", value="track_" + comment.author.name)
            response.post_to_channel(token=self.config.bot_user_token, channel='#ban-requests')

            comment.report("Slack user @%s has requested a ban." % author)
            response = utils.SlackResponse(text="Ban requested.")
            request.delayed_response(response)

    @bot_threading.own_thread(dedicated=True)
    def log_bans(self, r, o):
        print("Starting log_bans thread...")

        if not self.config.banlist_populated:
            limit = None
        else:
            limit = 20

        while True:

            o.refresh()
            bans = r.get_subreddit(self.subreddit_name).get_banned(limit=limit, user_only=False, fetch=True)

            for ban in bans:
                self.db.log_ban(ban)

            sleep(600)

    @bot_threading.own_thread(dedicated=True)
    def comments_feed(self, r, o):
        print("Starting comments_feed thread...")

        while True:

            o.refresh()
            tracked_users = [track[1].lower() for track in self.db.fetch_tracks("tracked")]

            comments = r.get_subreddit(self.subreddit_name).get_comments(limit=100, sort='new')

            for comment in comments:

                if comment.id not in self.already_done:

                    try:
                        submission = comment.submission
                    except AttributeError:
                        submission = None

                    if comment.is_root and comment.author.name != "ELI5_BotMod"\
                            and comment.author.name != 'AutoModerator' and comment.banned_by is None:

                        response = utils.SlackResponse()
                        
                        response.add_attachment(text=comment.body,
                                                color="#0073a3", title=submission.title,
                                                title_link=comment.permalink, callback_id="tlcfeed")
                        response.attachments[0].add_field("Author", comment.author.name)
                        response.attachments[0].add_button("Approve", "approve_" + comment.id, style="primary")
                        response.attachments[0].add_button("Remove", "remove_" + comment.id, style="danger")
                        # response.attachments[0].add_button("Summary", "summary_" + comment.author.name)
                        response.attachments[0].add_button("Request ban", "banreq_" + comment.id)

                        slack_response = response.post_to_channel(token=self.config.bot_user_token,
                                                                  channel='#tlc-feed')

                    if comment.author.name.lower() in tracked_users:
                        response = utils.SlackResponse(text="New comment by user /u/" + comment.author.name)
                        
                        response.add_attachment(title=submission.title, title_link=comment.permalink,
                                                text=comment.body, color="#warning")

                        response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')

                    

                    try:
                        if comment.author.name.lower() == submission.author.name.lower()\
                                and len(comment.body) > 500:

                            warning_trigger = self.db.add_submission_op_reply(submission.id)

                            if warning_trigger:
                                response = utils.SlackResponse(text="Detected possible soapboxing attempt.")
                                response.add_attachment(title=submission.title,
                                                        title_link=submission.permalink, color='warning')
                                response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')
                                submission.report("Possible soapbox attempt.")
                    except AttributeError:
                        pass

                    self.already_done.append(comment.id)

                    with open("already_done.txt", "a") as text_file:
                        print(comment.id + ",", end="", file=text_file)
            sleep(120)

    @bot_threading.own_thread()
    def remove_comment(self, cmt_id):
        
        comment = self.r.get_info(thing_id="t1_" + cmt_id)
        comment.remove()

    @bot_threading.own_thread()
    def approve_comment(self, cmt_id):
        
        comment = self.r.get_info(thing_id="t1_" + cmt_id)
        comment.approve()

    @bot_threading.own_thread()
    def report_comment(self, cmt_id, reason):
        
        comment = self.r.get_info(thing_id="t1_" + cmt_id)
        comment.report(reason)

    @bot_threading.own_thread()
    def reset_user_tracks(self):
        self.db.reset_user_tracks()

    @bot_threading.own_thread(dedicated=True)
    def track_users(self, r, o):

        print("Starting track_users thread...")
        subreddit = r.get_subreddit(self.subreddit_name)
        ignored_users = ['ELI5_BotMod', 'AutoModerator']

        while True:
            
            modlog = subreddit.get_mod_log(limit=30)
            already_done_user = []
            o.refresh()

            for item in modlog:
                if item.id not in self.already_done and item.target_fullname not in self.already_done and \
                        item.target_author not in ignored_users:
                    user_dict = self.db.handle_mod_log(item)

                    if item.target_author not in already_done_user and user_dict is not None:

                        done = False

                        comment_warning_threshold = self.config.comment_warning_threshold

                        comment_warning_threshold_high = self.config.comment_warning_threshold_high

                        submission_warning_threshold = self.config.submission_warning_threshold

                        submission_warning_threshold_high = self.config.submission_warning_threshold_high

                        ban_warning_threshold = self.config.ban_warning_threshold

                        ban_warning_threshold_high = self.config.ban_warning_threshold_high

                        if user_dict['comment_removals'] >= comment_warning_threshold:
                            response = utils.SlackResponse()
                            response.add_attachment(title="Warning regarding user /u/" + user_dict['username'],
                                                    title_link="https://www.reddit.com/user/" + user_dict['username'],
                                                    text="User has had %s> comments removed. "
                                                         "Please check profile history." %
                                                    str(comment_warning_threshold),
                                                    color='warning', callback_id="userwarning")
                            response.attachments[0].add_button("Verify", value="verify", style='primary')
                            response.attachments[0].add_button("Track", value="track_" + user_dict['username'])
                            response.attachments[0].add_button("Shadowban", value="shadowban_" + user_dict['username'],
                                                               style='danger')

                            response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')

                            done = True

                        if user_dict['comment_removals'] >= comment_warning_threshold_high:
                            response = utils.SlackResponse()
                            response.add_attachment(title="*Urgent warning* regarding user /u/" + user_dict['username'],
                                                    title_link="https://www.reddit.com/user/" + user_dict['username'],
                                                    text="User has had %s> comments removed. "
                                                         "Please check profile history immediately." %
                                                    str(comment_warning_threshold_high),
                                                    color='danger', callback_id="userwarning")
                            response.attachments[0].add_button("Verify", value="verify", style='primary')
                            response.attachments[0].add_button("Track", value="track_" + user_dict['username'])
                            response.attachments[0].add_button("Shadowban", value="shadowban_" + user_dict['username'],
                                                               style='danger')

                            response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')

                            done = True

                        if user_dict['link_removals'] >= submission_warning_threshold:
                            response = utils.SlackResponse()
                            response.add_attachment(title="Warning regarding user /u/" + user_dict['username'],
                                                    title_link="https://www.reddit.com/user/" + user_dict['username'],
                                                    text="User has had %s> submissions removed. Please check profile"
                                                         " history." % str(submission_warning_threshold),
                                                    color='warning', callback_id="userwarning")
                            response.attachments[0].add_button("Verify", value="verify", style="primary")
                            response.attachments[0].add_button("Track", value="track_" + user_dict['username'])
                            response.attachments[0].add_button("Shadowban", value="shadowban_" + user_dict['username'],
                                                               style='danger')

                            response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')

                            done = True

                        if user_dict['link_removals'] >= submission_warning_threshold_high:
                            response = utils.SlackResponse()
                            response.add_attachment(title="*Urgent warning* regarding user /u/" + user_dict['username'],
                                                    title_link="https://www.reddit.com/user/" + user_dict['username'],
                                                    text="User has had %s> submissions removed. Please check profile"
                                                         " history immediately." %
                                                         str(submission_warning_threshold_high),
                                                    color='danger', callback_id="userwarning")
                            response.attachments[0].add_button("Verify", value="verify", style="primary")
                            response.attachments[0].add_button("Track", value="track_" + user_dict['username'])
                            response.attachments[0].add_button("Shadowban", value="shadowban_" + user_dict['username'],
                                                               style='danger')

                            response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')

                            done = True

                        if user_dict['bans'] >= ban_warning_threshold:

                            response = utils.SlackResponse()
                            response.add_attachment(title="Warning regarding user /u/" + user_dict['username'],
                                                    title_link="https://www.reddit.com/user/" + user_dict['username'],
                                                    text="User has been banned %s> times. Please check profile history."
                                                    % str(ban_warning_threshold),
                                                    color='warning', callback_id="userwarning")
                            response.attachments[0].add_button("Verify", value="verify", style='primary')
                            response.attachments[0].add_button("Track", value="track_" + user_dict['username'])
                            response.attachments[0].add_button("Shadowban", value="shadowban_" + user_dict['username'],
                                                               style='danger')

                            response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')

                            done = True

                        if user_dict['bans'] >= ban_warning_threshold_high:

                            response = utils.SlackResponse()
                            response.add_attachment(title="*Urgent warning* regarding user /u/" + user_dict['username'],
                                                    title_link="https://www.reddit.com/user/" + user_dict['username'],
                                                    text="User has been banned %s> times. "
                                                         "Please check profile history immediately."
                                                         % str(ban_warning_threshold_high),
                                                    color='danger', callback_id="userwarning")
                            response.attachments[0].add_button("Verify", value="verify", style='primary')
                            response.attachments[0].add_button("Track", value="track_" + user_dict['username'])
                            response.attachments[0].add_button("Shadowban", value="shadowban_" + user_dict['username'],
                                                               style='danger')

                            response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')

                            done = True

                        if done:
                            already_done_user.append(user_dict['username'])

                    self.already_done.append(item.id)
                    self.already_done.append(item.target_fullname)

                    with open("already_done.txt", "a") as text_file:
                        print(item.id + ",", end="", file=text_file)

                        try:
                            print(item.target_fullname + ',', end="", file=text_file)
                        except TypeError:
                            pass
            sleep(300)

    @bot_threading.own_thread(dedicated=True)
    def monitor_modmail(self, r, o):
        print("Starting monitor_modmail thread...")

        modmails = dict()

        while True:
            o.refresh()

            try:
                
                modmail = r.get_mod_mail(self.subreddit_name, limit=10)

                muted_users = [track[1] for track in self.db.fetch_tracks("permamuted")]

                for message in modmail:
                    if message.id not in self.already_done:

                        if message.author.name in muted_users:

                            if not self.debug:
                                message.mute_modmail_author()

                        modmails[message.id] = utils.SlackModmail(message, self.config.bot_user_token, "C208X7WR0")

                        for reply in message.replies:
                            modmails[message.id].add_reply(reply)
                            with open("already_done.txt", "a") as text_file:
                                print(reply.id + ",", end="", file=text_file)
                            self.already_done.append(reply.id)

                        self.already_done.append(message.id)

                        with open("already_done.txt", "a") as text_file:
                            print(message.id + ",", end="", file=text_file)

                    else:
                        for reply in message.replies:
                            if reply.id not in self.already_done:
                                try:
                                    modmails[message.id].add_reply(reply)
                                    with open("already_done.txt", "a") as text_file:
                                        print(reply.id + ",", end="", file=text_file)
                                    self.already_done.append(reply.id)
                                except KeyError:
                                    break
            except AttributeError:
                pass

            sleep(5)

    @staticmethod
    def remove_from_file(filename, str_to_remove):

        with open(filename, "r") as text_file:
            file_data = text_file.read().split(',')

        try:
            file_data.remove(str_to_remove)
        except ValueError:
            pass

        with open(filename, "w") as text_file:
            text_file.write(','.join(file_data))

    @bot_threading.own_thread(dedicated=True)
    def handle_unflaired(self, r, o):
        print("Starting handle_unflaired thread...")

        unflaired_submissions = self.db.fetch_unflaired_submissions(r)
        tracked_users = [track[1].lower() for track in self.db.fetch_tracks("tracked")]

        while True:

            o.refresh()
            highest_timestamp = datetime.datetime.now() - datetime.timedelta(minutes=10)
            try:
                
                submissions = r.get_subreddit(self.subreddit_name).get_new(limit=20)

                for submission in submissions:

                    if submission.author.name.lower() in tracked_users and submission.id not in self.already_done:
                        response = utils.SlackResponse(text="New submission by user /u/" + submission.author.name)
                        
                        response.add_attachment(title=submission.title, title_link=submission.permalink,
                                                text=submission.body, color="#warning")

                        response.post_to_channel(token=self.config.bot_user_token, channel='#rs_feed')
                        self.already_done.append(submission.id)

                        with open("already_done.txt", "a") as text_file:
                            print(submission.id + ",", end="", file=text_file)

                    if submission.created > highest_timestamp.timestamp() and \
                                    submission.link_flair_text is None:
                        submission.remove()

                        s1 = submission.author
                        s2 = 'https://www.reddit.com/message/compose/?to=/r/' + self.subreddit_name
                        s3 = submission.permalink

                        comment = utils.generate_flair_comment(s1, s2, s3)

                        comment_obj = submission.add_comment(comment)
                        comment_obj.distinguish(sticky=True)

                        unflaired_submission = utils.UnflairedSubmission(submission, comment_obj)

                        unflaired_submissions.append(unflaired_submission)

                        self.db.log_unflaired_submission(submission.id, comment_obj.id)

                for unflaired_submission_obj in unflaired_submissions:

                    submission = unflaired_submission_obj.submission
                    submission = r.get_submission(submission_id=submission.id)
                    comment = unflaired_submission_obj.comment

                    if submission.link_flair_text is not None:
                        submission.approve()

                        for report in submission.mod_reports:
                            submission.report(report[0])
                            print(str(report))

                        comment.delete()
                        unflaired_submissions.remove(unflaired_submission_obj)
                        self.db.delete_unflaired_submissions_row(submission.id)
                    else:

                        submission_time = datetime.datetime.fromtimestamp(submission.created)
                        d = datetime.datetime.now() - submission_time
                        delta_time = d.total_seconds()

                        if delta_time >= 13600:
                            unflaired_submissions.remove(unflaired_submission_obj)
                            comment.delete()
                            self.db.delete_unflaired_submissions_row(submission.id)

            except (requests.exceptions.HTTPError, praw.errors.HTTPException):
                sleep(2)
                continue

            sleep(120)

    def get_user_details(self, username):
        redditor = self.r.get_redditor(username)
        date = str(datetime.datetime.fromtimestamp(redditor.created_utc))

        return redditor.link_karma + redditor.comment_karma, date

    @bot_threading.own_thread()
    def summary(self, username, request, no_summary=False, replace_original=False):

        if no_summary == "quick":
            no_summary = True
        else:
            no_summary = False

        try:
            user = self.r.get_redditor(username, fetch=True)
        except praw.errors.NotFound:
            response = utils.SlackResponse()
            response.add_attachment(fallback="Summary error.", title="Error: user not found.", color='danger')
            return request.delayed_response(response)

        username = user.name
        user_status = self.db.fetch_user_log(username)
        troll_likelihood = "Low"
        color = 'good'

        comment_removals = user_status[0]
        link_removals = user_status[1]
        bans = user_status[2]
        user_is_permamuted = user_status[3]
        user_is_tracked = user_status[4]
        user_is_shadowbanned = user_status[5]

        try:
            combined_karma = user.link_karma + user.comment_karma
        except AttributeError:
            response = utils.SlackResponse()
            response.add_attachment(fallback="Summary error.", title="Error: user not found.", color='danger')
            return request.delayed_response(response)

        account_creation = str(datetime.datetime.fromtimestamp(user.created_utc))
        
        last_note = self.get_last_note(username)

        response = utils.SlackResponse(replace_original=replace_original)
        response.add_attachment(title='Summary for /u/' + user.name,
                                title_link="https://www.reddit.com/user/" + username,
                                color='#3AA3E3', callback_id='user_' + username)

        response.attachments[0].add_field("Combined karma", combined_karma)
        response.attachments[0].add_field("Redditor since", account_creation)
        response.attachments[0].add_field("Removed comments", comment_removals)
        response.attachments[0].add_field("Removed submissions", link_removals)
        response.attachments[0].add_field("Bans", bans)
        response.attachments[0].add_field("Shadowbanned", user_is_shadowbanned)
        response.attachments[0].add_field("Permamuted", user_is_permamuted)
        response.attachments[0].add_field("Tracked", user_is_tracked)
        response.attachments[0].add_field("Latest usernote", last_note, short=False)

        if user_is_permamuted == "Yes":
            response.attachments[0].add_button("Unpermamute", "unpermamute_" + username)
        else:
            response.attachments[0].add_button("Permamute", "permamute_" + username,
                                               confirm="The user will be permamuted. This action is reversible.",
                                               yes="Permamute")

        if user_is_tracked == "Yes":
            response.attachments[0].add_button("Untrack", "untrack_" + username)
        else:
            response.attachments[0].add_button("Track", "track_" + username)

        if self.config.shadowbans_enabled:
            if user_is_shadowbanned == "Yes":
                response.attachments[0].add_button("Unshadowban", "unshadowban_" + username, style='danger')
            else:
                response.attachments[0].add_button("Shadowban", "shadowban_" + username, style='danger',
                                                   confirm="The user will be shadowbanned. "
                                                           "This action is reversible.",
                                                   yes="Shadowban")

        if not no_summary:
            limit = 500
            i = 0
            total_comments = 0
            subreddit_names = []
            subreddit_total = []
            ordered_subreddit_names = []
            comments_in_subreddit = []
            ordered_comments_in_subreddit = []
            comment_lengths = []
            history = {}
            total_karma = 0
            troll_index = 0
            blacklisted_subreddits = ('theredpill', 'rage', 'atheism', 'conspiracy', 'the_donald', 'subredditcancer',
                                      'SRSsucks', 'drama', 'undelete', 'blackout2015', 'oppression', 'kotakuinaction',
                                      'tumblrinaction', 'offensivespeech', 'bixnood')
            total_negative_karma = 0

            x = []
            y = []
            s = []

            karma_accumulator = 0
            karma_accumulated = []
            karma_accumulated_total = []
            
            for comment in user.get_comments(limit=limit):

                displayname = comment.subreddit.display_name

                if displayname not in subreddit_names:
                    subreddit_names.append(displayname)

                subreddit_total.append(displayname)

                total_karma = total_karma + comment.score

                x.append(datetime.datetime.utcfromtimestamp(float(comment.created_utc)))
                y.append(comment.score)
                comment_lengths.append(len(comment.body.split()))

                if comment.score < 0:
                    total_negative_karma += comment.score

                if len(comment.body) < 200:
                    troll_index += 0.1

                if displayname in blacklisted_subreddits:
                    troll_index += 2.5

                i += 1

            total_comments_read = i

            if not total_comments_read:
                response.add_attachment(fallback="Summary for /u/" + username,
                                        text="Summary error: user has no comments.",
                                        color='danger')

                return request.delayed_response(response)

            troll_index *= limit / total_comments_read

            average_karma = np.mean(y)

            if average_karma >= 5 and total_negative_karma > (-70 * (total_comments_read / limit)) and troll_index < 50:
                troll_likelihood = 'Low'
                color = 'good'

            if troll_index >= 40 or total_negative_karma < (-70 * (total_comments_read / limit)) or average_karma < 1:
                troll_likelihood = 'Moderate'
                color = 'warning'

            if troll_index >= 60 or total_negative_karma < (-130 * (total_comments_read / limit)) or average_karma < -2:
                troll_likelihood = 'High'
                color = 'danger'

            if troll_index >= 80 or total_negative_karma < (-180 * (total_comments_read / limit)) or average_karma < -5:
                troll_likelihood = 'Very high'
                color = 'danger'

            if troll_index >= 100 or total_negative_karma < (-200 * (total_comments_read / limit))\
                    or average_karma < -10:
                troll_likelihood = 'Extremely high'
                color = 'danger'

            for subreddit in subreddit_names:
                i = subreddit_total.count(subreddit)
                comments_in_subreddit.append(i)
                total_comments += i

            i = 0

            for subreddit in subreddit_names:

                if comments_in_subreddit[i] > (total_comments_read / (20 * (limit / 200)) /
                                                   (len(subreddit_names) / 30)):
                    history[subreddit] = comments_in_subreddit[i]

                i += 1

            old_range = 700 - 50
            new_range = 2000 - 50

            for item in comment_lengths:
                n = (((item - 50) * new_range) / old_range) + 50
                s.append(n)

            history_tuples = sorted(history.items(), key=lambda xa: x[1])

            for each_tuple in history_tuples:
                ordered_subreddit_names.append(each_tuple[0])
                ordered_comments_in_subreddit.append(each_tuple[1])

            user_karma_atstart = user.comment_karma - math.fabs((np.mean(y) * total_comments_read))

            for item in list(reversed(y)):
                karma_accumulator += item
                karma_accumulated.append(karma_accumulator)

            for item in karma_accumulated:
                karma_accumulated_total.append(user_karma_atstart + item)

            plt.style.use('ggplot')
            labels = ordered_subreddit_names
            sizes = ordered_comments_in_subreddit
            colors = ['yellowgreen', 'gold', 'lightskyblue', 'lightcoral', 'teal', 'chocolate', 'olivedrab', 'tan']
            plt.subplot(3, 1, 1)
            plt.rcParams['font.size'] = 8
            plt.pie(sizes, labels=labels, colors=colors,
                    autopct=None, startangle=90)
            plt.axis('equal')
            plt.title('User summary for /u/' + user.name, loc='center', y=1.2)

            ax1 = plt.subplot(3, 1, 2)
            x_inv = list(reversed(x))
            plt.rcParams['font.size'] = 10
            plt.scatter(x, y, c=y, vmin=-50, vmax=50, s=s, cmap='RdYlGn')
            ax1.set_xlim(x_inv[0], x_inv[total_comments_read - 1])
            ax1.axhline(y=average_karma, xmin=0, xmax=1, c="lightskyblue", linewidth=2, zorder=4)
            plt.ylabel('Karma of comment')

            ax2 = plt.subplot(3, 1, 3)
            plt.plot_date(x, list(reversed(karma_accumulated_total)), '-r')
            plt.xlabel('Comment date')
            plt.ylabel('Total comment karma')

            filename = username + "_summary.png"

            figure = plt.gcf()
            figure.set_size_inches(11, 12)

            plt.savefig(filename)

            path = os.getcwd() + "/" + filename

            link = self.imgur.upload_from_path(path, config=None, anon=True)
            os.remove(path)

            plt.clf()

            response.add_attachment(fallback="Summary for /u/" + username, image_url=link['link'],
                                    color=color)
            response.attachments[1].add_field("Troll likelihood", troll_likelihood)
            response.attachments[1].add_field("Total comments read", total_comments_read)

        if request is not None:
            response = request.delayed_response(response)

    @bot_threading.own_thread()
    def shadowban(self, username, request, author):

        r = self.r
        response = utils.SlackResponse(text="User */u/%s* has been shadowbanned." % username)

        try:
            user = self.r.get_redditor(username, fetch=True)
            username = user.name
        except praw.errors.NotFound:
            response = utils.SlackResponse()
            response.add_attachment(fallback="Shadowban warning.", title="Warning: user not found.", color='warning')

        if author.lower() in self.usergroup_mod:
            
            wiki_page = r.get_wiki_page(self.subreddit_name, "config/automoderator")
            wiki_page_content = wiki_page.content_md

            beg_ind = wiki_page_content.find("shadowbans")
            end_ind = wiki_page_content.find("#end shadowbans", beg_ind)

            try:
                n = puni.Note(username, "Shadowbanned via RedditSlacker by Slack user '%s'" % author,
                              username, '', 'botban')

                replacement = ', "%s"]' % username

                newstr = wiki_page_content[:beg_ind] + \
                         wiki_page_content[beg_ind:end_ind].replace("]", replacement) + \
                         wiki_page_content[end_ind:]

                if not self.debug:
                    
                    r.edit_wiki_page(self.subreddit_name, "config/automoderator", newstr,
                                     reason='RedditSlacker shadowban user "/u/%s" executed by Slack user "%s"'
                                            % (username, author))

                    self.un.add_note(n)

                response.add_attachment(fallback="Shadowbanned /u/" + username,
                                        title="User profile",
                                        title_link="https://www.reddit.com/user/" + username,
                                        color='good')

                response.attachments[len(response.attachments) - 1].add_field("Author", author)

            except AssertionError:
                raise
            except:
                response = utils.SlackResponse(text="Failed to shadowban user.")
                response.add_attachment(fallback="Shadowban fail",
                                        title="Exception",
                                        text=traceback.format_exc(),
                                        color='danger')
        else:
            response = utils.SlackResponse()
            response.add_attachment(fallback="Shadowban error.",
                                    title="Error: you are not authorized to perform this action.", color='danger')

        request.delayed_response(response)

    @bot_threading.own_thread()
    def unshadowban(self, username, request, author):

        response = utils.SlackResponse(text="Failed to unshadowban user.")

        try:
            user = self.r.get_redditor(username, fetch=True)
        except praw.errors.NotFound:
            response = utils.SlackResponse()
            response.add_attachment(fallback="Shadowban error.", title="Error: user not found.", color='danger')
            return request.delayed_response(response)

        username = user.name

        if author in self.usergroup_mod:
            
            wiki_page = self.r.get_wiki_page(self.subreddit_name, "config/automoderator")
            wiki_page_content = wiki_page.content_md

            wiki_page_content.replace(username, '')

            try:
                n = puni.Note(username, "Unshadowbanned via RedditSlacker by Slack user '%s'" % author,
                              username, '', 'botban')

                if not self.debug:
                    
                    self.r.edit_wiki_page(self.subreddit_name, "config/automoderator", wiki_page_content,
                                          reason='RedditSlacker unshadowban user "/u/%s" executed by Slack user "%s"'
                                                 % (username, author))

                response = utils.SlackResponse(text="User */u/%s* has been unshadowbanned." % username)

            except AssertionError:
                raise
            except:
                response.add_attachment(fallback="Unhadowban fail",
                                        title="Exception",
                                        text=traceback.format_exc(),
                                        color='danger')
        request.delayed_response(response)

    @bot_threading.own_thread()
    def add_usernote(self, user, note, author, request):

        try:
            
            user = self.r.get_redditor(user)
        except praw.errors.NotFound:
            response = utils.SlackResponse()
            response.add_attachment(fallback="Shadowban error.", title="Error: user not found.", color='danger')
            return request.delayed_response(response)

        n = puni.Note(user.name, note + " | Note added by RedditSlacker, executed by user '%s'" % author,
                      user.name, '', 'abusewarn')

        self.un.add_note(n)

        response = utils.SlackResponse()
        response.add_attachment(text="Note added successfully!", color='good')
        request.delayed_response(response)

