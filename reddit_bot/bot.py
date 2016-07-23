import praw
import OAuth2Util
from praw.handlers import MultiprocessHandler
from imgurpython import ImgurClient
import matplotlib.pyplot as plt
from tokens import tokens
import math
import numpy as np
import datetime
import os
import requests
from reddit_bot.utils import SlackResponse, SlackField, SlackButton
import threading
import traceback
import time
import json

SLACK_BOT_TOKEN = tokens.get_token('SLACK_BOT_TOKEN')


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

    def __init__(self):
        handler = MultiprocessHandler()
        self.r = praw.Reddit(user_agent="windows:RedditSlacker 0.1 by /u/santi871", handler=handler)
        self.imgur = ImgurClient(tokens.get_token('IMGUR_CLIENT_ID'), tokens.get_token('IMGUR_CLIENT_SECRET'))

        try:
            self._authenticate()
        except AssertionError:
            pass

        # self.hello()
        self.new_comments_stream()

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

        while True:
            try:
                for comment in praw.helpers.comment_stream(self.r, 'explainlikeimfive', limit=2, verbosity=0):
                    if comment.is_root and comment.author.name != "ELI5_BotMod":
                        field_a = SlackField("Author", comment.author.name)
                        field_b = SlackField("Question", comment.submission.title)
                        remove_button = SlackButton("Remove", "remove_" + comment.id, style="danger")
                        response = SlackResponse(token=SLACK_BOT_TOKEN, channel="#tlc-feed")
                        response.add_attachment(text=comment.body, fields=[field_b, field_a], buttons=[remove_button],
                                                color="#0073a3", title_link=comment.permalink)

                        requests.post('https://slack.com/api/chat.postMessage', params=response.response_dict)
            except requests.exceptions.ReadTimeout:
                time.sleep(1)

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
        user = self.r.get_redditor(username)
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
        field_a = SlackField("Troll likelihood", troll_likelihood)
        field_b = SlackField("Total comments read", total_comments_read)
        response = SlackResponse()
        response.add_attachment(fallback="Summary for /u/" + username, title="Summary for /u/" + username,
                                title_link="https://www.reddit.com/user/" + username, image_url=link['link'],
                                color=color, fields=[field_a, field_b])

        return response.response_dict
