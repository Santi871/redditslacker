import sqlite3


class RedditSlackerDatabase:

    def __init__(self, create_tables=True):

        self.db = sqlite3.connect('redditslacker_main.db', check_same_thread=False, isolation_level=None)
        self.cur = self.db.cursor()

        if create_tables:
            self.db.execute('''CREATE TABLE IF NOT EXISTS COMMANDS_LOG
                (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                USER_NAME TEXT NOT NULL UNIQUE,
                USER_ID TEXT NOT NULL,
                TEAM_NAME TEXT NOT NULL,
                TEAM_ID TEXT NOT NULL,
                CHANNEL_NAME TEXT NOT NULL,
                CHANNEL_ID TEXT NOT NULL,
                COMMAND TEXT NOT NULL,
                ARGS TEXT NOT NULL,
                DATETIME TEXT NOT NULL)''')

            self.db.execute('''CREATE TABLE IF NOT EXISTS OFFENSE_TRACK
                            (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                            USER_NAME TEXT NOT NULL,
                            REMOVED_COMMENTS INTEGER NOT NULL,
                            REMOVED_SUBMISSIONS INTEGER NOT NULL,
                            BANS INTEGER NOT NULL,
                            PERMAMUTED INTEGER NOT NULL DEFAULT 0,
                            TRACKED INTEGER NOT NULL DEFAULT 0)''')

    def log_command(self, form):

        user_name = form.get('user_name')
        user_id = form.get('user_id')
        team_name = form.get('team_domain')
        team_id = form.get('team_id')
        channel_name = form.get('channel_name')
        channel_id = form.get('channel_id')
        command = form.get('command')
        args = form.get('text')

        self.cur.execute('''INSERT INTO COMMANDS_LOG(USER_NAME, USER_ID, TEAM_NAME, TEAM_ID, CHANNEL_NAME, CHANNEL_ID,
                          COMMAND, ARGS, DATETIME) VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''', (user_name, user_id,
                                                                                                  team_name,
                                                                                                  team_id, channel_name,
                                                                                                  channel_id,
                                                                                                  command, args))

    def handle_mod_log(self, log):

        username = log.target_author
        type = log.action

        user_comment_removals = 0
        user_link_removals = 0
        user_bans = 0

        self.cur.execute('''SELECT * FROM OFFENSE_TRACK WHERE USER_NAME = ?''', (username,))
        user_track = self.cur.fetchone()

        if user_track is not None:
            user_comment_removals = user_track[2]
            user_link_removals = user_track[3]
            user_bans = user_track[4]

        if type == "removelink":
            user_link_removals += 1
        elif type == "banuser":
            user_bans += 1
        elif type == "removecomment":
            user_comment_removals += 1

        if user_track is not None:

            self.cur.execute('''REPLACE INTO OFFENSE_TRACK(ID, USER_NAME, REMOVED_COMMENTS,
                                REMOVED_SUBMISSIONS, BANS) VALUES(?,?,?,?,?)''', (user_track[0], username,
                                                                                  user_comment_removals,
                                                                                  user_link_removals,
                                                                                  user_bans))
        else:
            self.cur.execute('''INSERT INTO OFFENSE_TRACK(USER_NAME, REMOVED_COMMENTS, REMOVED_SUBMISSIONS, BANS)
                                VALUES(?,?,?,?)''', (username, user_comment_removals, user_link_removals, user_bans))

        return_dict = {"username": username, "comment_removals": user_comment_removals,
                       "link_removals": user_link_removals,
                       "bans": user_bans}

        return return_dict