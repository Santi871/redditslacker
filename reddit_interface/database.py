import sqlite3


class RedditSlackerDatabase:

    def __init__(self, name, create_tables=True):

        self.db = sqlite3.connect(name, check_same_thread=False, isolation_level=None)

        if create_tables:
            self.db.execute('''CREATE TABLE IF NOT EXISTS COMMANDS_LOG
                (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                USER_NAME TEXT NOT NULL,
                USER_ID TEXT NOT NULL,
                TEAM_NAME TEXT NOT NULL,
                TEAM_ID TEXT NOT NULL,
                CHANNEL_NAME TEXT NOT NULL,
                CHANNEL_ID TEXT NOT NULL,
                COMMAND TEXT NOT NULL,
                ARGS TEXT NOT NULL,
                DATETIME TEXT NOT NULL)''')

            self.db.execute('''CREATE TABLE IF NOT EXISTS USER_TRACKS
                            (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                            USER_NAME TEXT UNIQUE NOT NULL,
                            REMOVED_COMMENTS INTEGER NOT NULL DEFAULT 0,
                            REMOVED_SUBMISSIONS INTEGER NOT NULL DEFAULT 0,
                            BANS INTEGER NOT NULL DEFAULT 0,
                            PERMAMUTED INTEGER NOT NULL DEFAULT 0,
                            TRACKED INTEGER NOT NULL DEFAULT 0,
                            SHADOWBANNED INTEGER NOT NULL DEFAULT 0)''')

    def log_command(self, form):

        cur = self.db.cursor()
        user_name = form.get('user_name')
        user_id = form.get('user_id')
        team_name = form.get('team_domain')
        team_id = form.get('team_id')
        channel_name = form.get('channel_name')
        channel_id = form.get('channel_id')
        command = form.get('command')
        args = form.get('text')

        cur.execute('''INSERT INTO COMMANDS_LOG(USER_NAME, USER_ID, TEAM_NAME, TEAM_ID, CHANNEL_NAME, CHANNEL_ID,
                          COMMAND, ARGS, DATETIME) VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''', (user_name, user_id,
                                                                                                  team_name,
                                                                                                  team_id, channel_name,
                                                                                                  channel_id,
                                                                                                  command, args))

    def handle_mod_log(self, log):

        cur = self.db.cursor()
        username = log.target_author
        log_type = log.action

        user_comment_removals = 0
        user_link_removals = 0
        user_bans = 0

        cur.execute('''SELECT * FROM USER_TRACKS WHERE USER_NAME = ?''', (username,))
        user_track = cur.fetchone()

        if user_track is not None:
            user_comment_removals = user_track[2]
            user_link_removals = user_track[3]
            user_bans = user_track[4]

        if log_type == "removelink":
            user_link_removals += 1
        elif log_type == "banuser":
            user_bans += 1
        elif log_type == "removecomment":
            user_comment_removals += 1

        if user_track is not None:

            cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                                REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                                VALUES(?,?,?,?,?,?,?,?)''', (user_track[0], username,
                                                             user_comment_removals,
                                                             user_link_removals,
                                                             user_bans, user_track[5], user_track[6], user_track[7]))
        else:
            cur.execute('''INSERT INTO USER_TRACKS(USER_NAME, REMOVED_COMMENTS, REMOVED_SUBMISSIONS, BANS)
                                VALUES(?,?,?,?)''', (username, user_comment_removals, user_link_removals, user_bans))

        return_dict = {"username": username, "comment_removals": user_comment_removals,
                       "link_removals": user_link_removals,
                       "bans": user_bans}

        return return_dict

    def fetch_user_log(self, username):

        print(username)
        cur = self.db.cursor()
        cur.execute('''SELECT * FROM USER_TRACKS WHERE USER_NAME = ?''', (username,))
        user_track = cur.fetchone()

        if user_track is None:
            track_info = ("No record", "No record", "No record", "No", "No", "No")
        else:
            if user_track[5]:
                is_permamuted = "Yes"
            else:
                is_permamuted = "No"
            if user_track[6]:
                is_tracked = "Yes"
            else:
                is_tracked = "No"
            if user_track[7]:
                is_shadowbanned = "Yes"
            else:
                is_shadowbanned = "No"
            track_info = (user_track[2], user_track[3], user_track[4], is_permamuted, is_tracked, is_shadowbanned)

        return track_info

    def fetch_tracks(self, option_type):

        cur = self.db.cursor()

        if option_type == "permamuted":
            cur.execute('''SELECT * FROM USER_TRACKS WHERE PERMAMUTED = 1''')
        elif option_type == "shadowbanned":
            cur.execute('''SELECT * FROM USER_TRACKS WHERE SHADOWBANNED = 1''')
        elif option_type == "tracked":
            cur.execute('''SELECT * FROM USER_TRACKS WHERE TRACKED = 1''')

        return cur.fetchall()

    def update_user_status(self, username, status_name):
        cur = self.db.cursor()
        print(username)

        cur.execute('''SELECT * FROM USER_TRACKS WHERE USER_NAME = ?''', (username,))
        user_track = cur.fetchone()

        if user_track is not None:

            if status_name == "shadowban":
                cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                    REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                    VALUES(?,?,?,?,?,?,?,?)''', (user_track[0], username,
                                                 user_track[2],
                                                 user_track[3],
                                                 user_track[4], user_track[5], user_track[6], 1))
            elif status_name == "permamute":
                cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                    REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                    VALUES(?,?,?,?,?,?,?,?)''', (user_track[0], username,
                                                 user_track[2],
                                                 user_track[3],
                                                 user_track[4], 1, user_track[6], user_track[7]))
            elif status_name == "track":
                cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                    REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                    VALUES(?,?,?,?,?,?,?,?)''', (user_track[0], username,
                                                 user_track[2],
                                                 user_track[3],
                                                 user_track[4], user_track[5], 1, user_track[7]))
            elif status_name == "untrack":
                cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                    REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                    VALUES(?,?,?,?,?,?,?,?)''', (user_track[0], username,
                                                 user_track[2],
                                                 user_track[3],
                                                 user_track[4], user_track[5], 0, user_track[7]))
            elif status_name == "unpermamute":
                cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                    REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                    VALUES(?,?,?,?,?,?,?,?)''', (user_track[0], username,
                                                 user_track[2],
                                                 user_track[3],
                                                 user_track[4], 0, user_track[6], user_track[7]))
            elif status_name == "unshadowban":
                cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                    REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                    VALUES(?,?,?,?,?,?,?,?)''', (user_track[0], username,
                                                 user_track[2],
                                                 user_track[3],
                                                 user_track[4], user_track[5], user_track[6], 0))

        else:
            if status_name == "shadowban":
                cur.execute('''INSERT INTO USER_TRACKS(USER_NAME, SHADOWBANNED)
                    VALUES(?,?)''', (username, 1))
            elif status_name == "permamute":
                cur.execute('''INSERT INTO USER_TRACKS(USER_NAME, PERMAMUTED)
                    VALUES(?,?)''', (username, 1))
            elif status_name == "track":
                cur.execute('''INSERT INTO USER_TRACKS(USER_NAME, TRACKED)
                    VALUES(?,?)''', (username, 1))
            elif status_name == "untrack":
                cur.execute('''INSERT INTO USER_TRACKS(USER_NAME, TRACKED)
                    VALUES(?,?)''', (username, 0))
            elif status_name == "unpermamute":
                cur.execute('''INSERT INTO USER_TRACKS(USER_NAME, PERMAMUTED)
                    VALUES(?,?)''', (username, 0))
            elif status_name == "unshadowban":
                cur.execute('''INSERT INTO USER_TRACKS(USER_NAME, SHADOWBANNED)
                    VALUES(?,?)''', (username, 0))


