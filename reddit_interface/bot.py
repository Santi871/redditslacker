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
        try:
            print("Starting " + self.name)
            methodToRun = self.method(self.obj)
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

    def __init__(self, db, load_side_threads=True):
        handler = MultiprocessHandler()
        self.db = db
        self.r = praw.Reddit(user_agent="windows:RedditSlacker 0.1 by /u/santi871", handler=handler)
        self.imgur = ImgurClient(utils.get_token('IMGUR_CLIENT_ID'), utils.get_token('IMGUR_CLIENT_SECRET'))

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

        # self.hello()
        if load_side_threads:
            self.new_comments_stream()
            self.track_users()

    def _authenticate(self):
        o = OAuth2Util.OAuth2Util(self.r)
        o.refresh(force=True)
        self.r.config.api_request_delay = 1

    @staticmethod
    def hello():
        data = {'token': SLACK_BOT_TOKEN, 'channel': '#random', 'text': 'waw', 'as_user': 'false'}
        requests.post('https://slack.com/api/chat.postMessage', params=data)

    @own_thread
    def new_comments_stream(self):

        self.r._use_oauth = False
        for comment in praw.helpers.comment_stream(self.r, self.subreddit_name, limit=2, verbosity=0):
            if comment.is_root and comment.author.name != "ELI5_BotMod":
                field_a = utils.SlackField("Author", comment.author.name)
                field_b = utils.SlackField("Question", comment.submission.title)
                remove_button = utils.SlackButton("Remove", "remove_" + comment.id, style="danger")
                response = utils.SlackResponse(token=SLACK_BOT_TOKEN, channel="#tlc-feed")
                response.add_attachment(text=comment.body, fields=[field_b, field_a], buttons=[remove_button],
                                        color="#0073a3", title_link=comment.permalink)

                request_response = requests.post('https://slack.com/api/chat.postMessage',
                                                 params=response.response_dict)

                print(str(request_response))

    @own_thread
    def track_users(self):
        subreddit = self.r.get_subreddit(self.subreddit_name)
        with open("modlog_alreadydone.txt", "r") as text_file:
            already_done = text_file.read().split(",")

        while True:
            self.r._use_oauth = False
            modlog = subreddit.get_mod_log(limit=100)

            for item in modlog:
                if item.id not in already_done:
                    user_dict = self.db.handle_mod_log(item)
                    already_done.append(item.id)

                    with open("modlog_alreadydone.txt", "a") as text_file:
                        print(item.id + ",", end="", file=text_file)
            sleep(120)

    def get_combined_karma(self, username):
        redditor = self.r.get_redditor(username)
        return redditor.link_karma + redditor.comment_karma

    def get_created_datetime(self, username):
        redditor = self.r.get_redditor(username)
        date = str(datetime.datetime.fromtimestamp(redditor.created_utc))
        return date

    def summary(self, split_text=None, limit=500, username=None):

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
        blacklisted_subreddits = ('theredpill', 'rage', 'atheism', 'conspiracy', 'subredditdrama', 'subredditcancer',
                                  'SRSsucks', 'drama', 'undelete', 'blackout2015', 'oppression0', 'kotakuinaction',
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
            response.add_attachment(fallback="Summary for /u/" + username, text="Error: user has no comments.",
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

        print(troll_index)
        print(total_negative_karma)

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

        # build a response dict that will be encoded to json
        field_a = utils.SlackField("Troll likelihood", troll_likelihood)
        field_b = utils.SlackField("Total comments read", total_comments_read)
        response = utils.SlackResponse()
        response.add_attachment(fallback="Summary for /u/" + username, title="Summary for /u/" + username,
                                title_link="https://www.reddit.com/user/" + username, image_url=link['link'],
                                color=color, fields=[field_a, field_b])

        return response.response_dict

    def shadowban(self, split_text, author, debug=False):

        """*!shadowban [user] [reason]:* Shadowbans [user] and adds usernote [reason] - USERNAME IS CASE SENSITIVE!"""

        r = self.r
        response = utils.SlackResponse(text='Usage: !shadowban [username] [reason]')

        if author in self.usergroup_mod:

            if len(split_text) >= 2:

                wiki_page = r.get_wiki_page(self.subreddit_name, "config/automoderator")
                wiki_page_content = wiki_page.content_md

                beg_ind = wiki_page_content.find("shadowbans")
                end_ind = wiki_page_content.find("#end shadowbans", beg_ind)
                username = split_text[0]
                reason = ' '.join(split_text[1:])

                try:
                    n = puni.Note(username, "Shadowbanned, reason: %s" % reason, username, '', 'botban')

                    replacement = ', "%s"]' % username

                    newstr = wiki_page_content[:beg_ind] + \
                             wiki_page_content[beg_ind:end_ind].replace("]", replacement) + \
                             wiki_page_content[end_ind:]

                    if not debug:

                        r.edit_wiki_page(self.subreddit_name, "config/automoderator", newstr,
                                         reason='ELI5_ModBot shadowban user "/u/%s" executed by Slack user "%s"'
                                                % (username, author))

                        self.un.add_note(n)

                    response = utils.SlackResponse(text="User */u/%s* has been shadowbanned." % username)
                    field_a = utils.SlackField("Reason", reason)
                    field_b = utils.SlackField("Author", author)
                    response.add_attachment(fallback="Shadowbanned /u/" + username,
                                            title="User profile",
                                            title_link="https://www.reddit.com/user/" + username,
                                            color='good',
                                            fields=[field_a, field_b])

                except:
                    response = utils.SlackResponse(text="Failed to shadowban user.")
                    response.add_attachment(fallback="Shadowban fail",
                                            title="Exception",
                                            text=traceback.format_exc(),
                                            color='danger')

        return response.response_dict

