import praw
import OAuth2Util
from praw.handlers import MultiprocessHandler
from imgurpython import ImgurClient
import matplotlib.pyplot as plt
import math
import numpy as np
from time import sleep
import os
import requests
import reddit_interface.utils as utils
import threading
import traceback
import puni
import datetime
import copy

SLACK_BOT_TOKEN = utils.get_token('SLACK_BOT_TOKEN')


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


class RedditBot:
    """Class that implements a Reddit bot to perform moderator actions in a specific subreddit"""

    def __init__(self, db, load_side_threads=True, debug=False):
        handler = MultiprocessHandler()
        self.db = db
        self.r = praw.Reddit(user_agent="windows:RedditSlacker 0.1 by /u/santi871", handler=handler)
        self.imgur = ImgurClient(utils.get_token('IMGUR_CLIENT_ID'), utils.get_token('IMGUR_CLIENT_SECRET'))
        self.debug = debug

        try:
            self._authenticate()
        except AssertionError:
            print("Bot authentication failed.")

        self.subreddit_name = 'explainlikeimfive'
        self.un = puni.UserNotes(self.r, self.r.get_subreddit(self.subreddit_name))

        self.usergroup_owner = 'santi871'
        self.usergroup_mod = ('santi871', 'akuthia', 'mason11987', 'mike_pants', 'mjcapples', 'securethruobscure',
                              'snewzie', 'teaearlgraycold', 'thom.willard', 'yarr', 'cow_co', 'sterlingphoenix',
                              'hugepilchard', 'curmudgy', 'h2g2_researcher', 'jim777ps3', 'letstrythisagain_',
                              'mr_magnus', 'terrorpaw', 'kodack10', 'doc_daneeka')

        self.already_done = self.fetch_already_done("already_done.txt")

        # self.hello()
        if load_side_threads:
            self.new_comments_stream()
            self.track_users()
            self.monitor_modmail()

    def _authenticate(self):
        o = OAuth2Util.OAuth2Util(self.r)
        o.refresh(force=True)
        self.r.config.api_request_delay = 1

    @staticmethod
    def hello():
        data = {'token': SLACK_BOT_TOKEN, 'channel': '#random', 'text': 'waw', 'as_user': 'false'}
        requests.post('https://slack.com/api/chat.postMessage', params=data)

    @staticmethod
    def fetch_already_done(filename):
        try:
            with open(filename, "r") as text_file:
                already_done = text_file.read().split(",")
        except FileNotFoundError:
            with open(filename, "a+"):
                pass
            already_done = []

        return already_done

    def get_last_note(self, username):
        notes = list(self.un.get_notes(username))

        if len(notes) == 0:
            return "No usernotes attached to this user."
        else:
            return str(notes[0].note)

    @own_thread
    def new_comments_stream(self):

        while True:

            self.r._use_oauth = False
            comments = self.r.get_subreddit(self.subreddit_name).get_comments(limit=100, sort='new')

            for comment in comments:
                if comment.is_root and comment.author.name != "ELI5_BotMod" and comment.id not in self.already_done:
                    field_a = utils.SlackField("Author", comment.author.name)
                    self.r._use_oauth = False
                    field_b = utils.SlackField("Question", comment.submission.title)
                    remove_button = utils.SlackButton("Remove", "remove_" + comment.id, style="danger")
                    response = utils.SlackResponse(token=SLACK_BOT_TOKEN, channel="#tlc-feed")
                    response.add_attachment(text=comment.body, fields=[field_b, field_a], buttons=[remove_button],
                                            color="#0073a3", title_link=comment.permalink)

                    request_response = requests.post('https://slack.com/api/chat.postMessage',
                                                     params=response.response_dict)

                    print(str(request_response))

                    self.already_done.append(comment.id)

                    with open("already_done.txt", "a") as text_file:
                        print(comment.id + ",", end="", file=text_file)
            sleep(120)

    @own_thread
    def track_users(self):
        subreddit = self.r.get_subreddit(self.subreddit_name)

        while True:
            self.r._use_oauth = False
            modlog = subreddit.get_mod_log(limit=100)

            for item in modlog:
                if item.id not in self.already_done:
                    user_dict = self.db.handle_mod_log(item)
                    self.already_done.append(item.id)

                    with open("already_done.txt", "a") as text_file:
                        print(item.id + ",", end="", file=text_file)
            sleep(120)

    @own_thread
    def monitor_modmail(self):

        while True:
            self.r._use_oauth = False
            modmail = self.r.get_mod_mail('santi871', limit=100)

            muted_users = [track[1] for track in self.db.fetch_tracks("permamuted")]

            for item in modmail:
                if item.id not in self.already_done and item.author.name in muted_users:

                    if not self.debug:
                        item.mute_modmail_author()

                    self.already_done.append(item.id)

                    with open("already_done.txt", "a") as text_file:
                        print(item.id + ",", end="", file=text_file)
            sleep(120)

    @own_thread
    def handle_unflaired(self):

        r = self.r
        unflaired_submissions_ids = []
        unflaired_submissions = []

        while True:

            highest_timestamp = datetime.datetime.now() - datetime.timedelta(minutes=10)
            try:
                submissions = r.get_subreddit('explainlikeimfive').get_new(limit=100)

                for submission in submissions:

                    if submission.created > highest_timestamp.timestamp() and \
                                    submission.id not in unflaired_submissions_ids and \
                                    submission.link_flair_text is None:
                        submission.remove()

                        s1 = submission.author
                        s2 = 'https://www.reddit.com/message/compose/?to=/r/explainlikeimfive'
                        s3 = submission.permalink
                        comment = ("""Hi /u/%s,

It looks like you haven't assigned a category flair to your question, so it has been automatically removed.
You can assign a category flair to your question by clicking the *flair* button under it.

Shortly after you have assigned a category flair to your question, it will be automatically re-approved and
 this message
will be deleted.

**Mobile users:** some reddit apps don't support flair selection (including the official one). In order to
 flair your
question, open it in your phone's web browser by clicking [this link](%s) and select
flair as you would in a desktop computer.

---

*I am a bot, and this action was performed automatically.
Please [contact the moderators](%s) if you have any questions or concerns*
""") % (s1, s3, s2)
                        comment_obj = submission.add_comment(comment)
                        comment_obj.distinguish(sticky=True)
                        unflaired_submissions_ids.append(submission.id)
                        unflaired_submissions.append((submission.id, comment_obj.fullname))

                unflaired_submissions_duplicate = copy.deepcopy(unflaired_submissions)

                for submission_tuple in unflaired_submissions_duplicate:

                    refreshed_submission = r.get_submission(submission_id=submission_tuple[0])

                    comment_obj = r.get_info(thing_id=submission_tuple[1])

                    if refreshed_submission.link_flair_text is not None:
                        refreshed_submission.approve()

                        comment_obj.remove()

                        unflaired_submissions.remove(submission_tuple)
                        unflaired_submissions_ids.remove(submission_tuple[0])

                    else:

                        submission_time = datetime.datetime.fromtimestamp(refreshed_submission.created_utc)
                        d = datetime.datetime.now() - submission_time
                        delta_time = d.total_seconds()

                        if delta_time >= 10800:
                            unflaired_submissions.remove(submission_tuple)
                            unflaired_submissions_ids.remove(submission_tuple[0])
                            comment_obj.remove()

            except:
                print("--------------\nUnexpected exception.\n--------------")
                print(traceback.format_exc())
                continue

            sleep(120)

    def get_user_details(self, username):
        redditor = self.r.get_redditor(username)
        date = str(datetime.datetime.fromtimestamp(redditor.created_utc))

        return redditor.link_karma + redditor.comment_karma, date

    def summary(self, split_text=None, limit=500, username=None, user_status=None):

        if split_text is not None:
            username = split_text[0]

        i = 0
        total_comments = 0
        color = 'good'
        subreddit_names = []
        subreddit_total = []
        ordered_subreddit_names = []
        comments_in_subreddit = []
        ordered_comments_in_subreddit = []
        comment_lengths = []
        history = {}
        total_karma = 0
        troll_index = 0
        troll_likelihood = "Low"
        blacklisted_subreddits = ('theredpill', 'rage', 'atheism', 'conspiracy', 'the_donald', 'subredditcancer',
                                  'SRSsucks', 'drama', 'undelete', 'blackout2015', 'oppression', 'kotakuinaction',
                                  'tumblrinaction', 'offensivespeech', 'bixnood')
        total_negative_karma = 0

        try:
            user = self.r.get_redditor(username, fetch=True)
        except praw.errors.NotFound:
            response = utils.SlackResponse()
            response.add_attachment(fallback="Summary error.", title="Error: user not found.", color='danger')
            return response.response_dict

        x = []
        y = []
        s = []

        karma_accumulator = 0
        karma_accumulated = []
        karma_accumulated_total = []

        self.r._use_oauth = False
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
            response = utils.SlackResponse()
            response.add_attachment(fallback="Summary for /u/" + username, text="Summary error: user has no comments.",
                                    color='danger')

            return response.response_dict

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

        if troll_index >= 100 or total_negative_karma < (-200 * (total_comments_read / limit)) or average_karma < -10:
            troll_likelihood = 'Extremely high'
            color = 'danger'

        for subreddit in subreddit_names:
            i = subreddit_total.count(subreddit)
            comments_in_subreddit.append(i)
            total_comments += i

        i = 0

        for subreddit in subreddit_names:

            if comments_in_subreddit[i] > (total_comments_read / (20 * (limit / 200)) / (len(subreddit_names) / 30)):
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
        plt.title('User summary for /u/' + username, loc='center', y=1.2)

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

        path = os.getcwd() + "\\" + filename

        link = self.imgur.upload_from_path(path, config=None, anon=True)
        os.remove(path)

        plt.clf()

        comment_removals = user_status[0]
        link_removals = user_status[1]
        bans = user_status[2]
        user_is_permamuted = user_status[3]
        user_is_tracked = user_status[4]
        user_is_shadowbanned = user_status[5]
        combined_karma = user.link_karma + user.comment_karma
        account_creation = str(datetime.datetime.fromtimestamp(user.created_utc))
        last_note = self.get_last_note(username)

        if user_is_permamuted == "Yes":
            permamute_button = utils.SlackButton("Unpermamute", "unpermamute_" + username)
        else:
            permamute_button = utils.SlackButton("Permamute", "permamute_" + username)

        if user_is_tracked == "Yes":
            track_button = utils.SlackButton("Untrack", "untrack_" + username)
        else:
            track_button = utils.SlackButton("Track", "track_" + username)

        if user_is_shadowbanned == "Yes":
            shadowban_button = utils.SlackButton("Unshadowban", "unshadowban_" + username, style='danger')
        else:
            shadowban_button = utils.SlackButton("Shadowban", "shadowban_" + username, style='danger')

        ban_button = utils.SlackButton("Ban", "ban_" + username, style='danger')
        field_a = utils.SlackField("Combined karma", combined_karma)
        field_b = utils.SlackField("Redditor since", account_creation)
        field_c = utils.SlackField("Removed comments", comment_removals)
        field_d = utils.SlackField("Removed submissions", link_removals)
        field_e = utils.SlackField("Bans", bans)
        field_f = utils.SlackField("Shadowbanned", user_is_shadowbanned)
        field_g = utils.SlackField("Permamuted", user_is_permamuted)
        field_h = utils.SlackField("Tracked", user_is_tracked)
        field_i = utils.SlackField("Latest usernote", last_note, short=False)
        response = utils.SlackResponse()
        response.add_attachment(title='Summary for /u/' + username,
                                title_link="https://www.reddit.com/user/" + username,
                                color='#3AA3E3', callback_id='user_' + username,
                                fields=[field_a, field_b, field_c, field_d, field_e, field_f, field_g,
                                        field_h, field_i],
                                buttons=[track_button,
                                         permamute_button, ban_button,
                                         shadowban_button])

        # build a response dict that will be encoded to json
        field_a = utils.SlackField("Troll likelihood", troll_likelihood)
        field_b = utils.SlackField("Total comments read", total_comments_read)
        response.add_attachment(fallback="Summary for /u/" + username, image_url=link['link'],
                                color=color, fields=[field_a, field_b])

        return response.response_dict

    def shadowban(self, username, author):

        """*!shadowban [user] [reason]:* Shadowbans [user] and adds usernote [reason] - USERNAME IS CASE SENSITIVE!"""

        r = self.r
        response = utils.SlackResponse(text='Usage: !shadowban [username] [reason]')

        if author in self.usergroup_mod:

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

                response = utils.SlackResponse(text="User */u/%s* has been shadowbanned." % username)
                field_b = utils.SlackField("Author", author)
                response.add_attachment(fallback="Shadowbanned /u/" + username,
                                        title="User profile",
                                        title_link="https://www.reddit.com/user/" + username,
                                        color='good',
                                        fields=[field_b])

            except:
                response = utils.SlackResponse(text="Failed to shadowban user.")
                response.add_attachment(fallback="Shadowban fail",
                                        title="Exception",
                                        text=traceback.format_exc(),
                                        color='danger')

        return response.response_dict

    def unshadowban(self, username, author):

        response = utils.SlackResponse(text="Failed to unshadowban user.")

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

                    self.un.add_note(n)

                response = utils.SlackResponse(text="User */u/%s* has been unshadowbanned." % username)

            except:
                response.add_attachment(fallback="Unhadowban fail",
                                        title="Exception",
                                        text=traceback.format_exc(),
                                        color='danger')
        return response.response_dict
