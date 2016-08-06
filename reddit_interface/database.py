import sqlite3
import reddit_interface.utils as utils


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

            self.db.execute('''CREATE TABLE IF NOT EXISTS BUTTONS_LOG
                (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                USER_NAME TEXT NOT NULL,
                USER_ID TEXT NOT NULL,
                TEAM_NAME TEXT NOT NULL,
                TEAM_ID TEXT NOT NULL,
                CHANNEL_NAME TEXT NOT NULL,
                CHANNEL_ID TEXT NOT NULL,
                BUTTON_PRESSED TEXT NOT NULL,
                DATETIME TEXT NOT NULL)''')

            self.db.execute('''CREATE TABLE IF NOT EXISTS UNFLAIRED_SUBMISSIONS
                (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                SUBMISSION_ID TEXT NOT NULL,
                COMMENT_ID TEXT NOT NULL)''')

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

    def log_button(self, form):

        cur = self.db.cursor()
        user_name = form.user
        user_id = form.user_id
        team_name = form.team_domain
        team_id = form.get('team_id')
        channel_name = form.get('channel_name')
        channel_id = form.get('channel_id')
        button_pressed = form.actions[0]['value']

        cur.execute('''INSERT INTO BUTTONS_LOG(USER_NAME, USER_ID, TEAM_NAME, TEAM_ID, CHANNEL_NAME, CHANNEL_ID,
            BUTTON_PRESSED, DATETIME) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''', (user_name, user_id,
                                                                                    team_name,
                                                                                    team_id, channel_name,
                                                                                    channel_id, button_pressed))

    def handle_mod_log(self, log):

        if log.mod.lower() == "eli5_botmod":
            return None

        cur = self.db.cursor()
        username = log.target_author
        log_type = log.action

        user_comment_removals = 0
        user_link_removals = 0
        user_bans = 0

        cur.execute('''SELECT * FROM USER_TRACKS WHERE USER_NAME = ? COLLATE NOCASE''', (username,))
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
        else:
            return None

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

    def reset_user_tracks(self):

        cur = self.db.cursor()

        cur.execute('''SELECT * FROM USER_TRACKS''')
        user_tracks = cur.fetchall()

        for track in user_tracks:
            cur.execute('''REPLACE INTO USER_TRACKS(ID, USER_NAME, REMOVED_COMMENTS,
                REMOVED_SUBMISSIONS, BANS, PERMAMUTED, TRACKED, SHADOWBANNED)
                VALUES(?,?,?,?,?,?,?,?)''', (track[0], track[1],
                                             0,
                                             0,
                                             0, track[5], track[6], track[7]))

    def fetch_user_log(self, username):

        print(username)
        cur = self.db.cursor()
        cur.execute('''SELECT * FROM USER_TRACKS WHERE USER_NAME = ? COLLATE NOCASE''', (username,))
        user_track = cur.fetchone()

        if user_track is None:
            track_info = ("No record", "No record", "No record", "No", "No", "No")
            return track_info
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

        comment_removals = user_track[2]
        link_removals = user_track[3]
        bans = user_track[4]

        if not user_track[2]:
            comment_removals = "None recorded"
        if not user_track[3]:
            link_removals = "None recorded"
        if not user_track[4]:
            bans = "None recorded"

        track_info = (comment_removals, link_removals, bans, is_permamuted, is_tracked, is_shadowbanned)

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

        cur.execute('''SELECT * FROM USER_TRACKS WHERE USER_NAME = ? COLLATE NOCASE''', (username,))
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

    def log_unflaired_submission(self, submission_id, comment_id):

        cur = self.db.cursor()
        cur.execute('''INSERT INTO UNFLAIRED_SUBMISSIONS(SUBMISSION_ID, COMMENT_ID) VALUES (?,?)''', (submission_id,
                                                                                                      comment_id))

    def fetch_unflaired_submissions(self, r):

        cur = self.db.cursor()
        cur.execute('''SELECT * FROM UNFLAIRED_SUBMISSIONS''')
        data = cur.fetchall()

        unflaired_submissions = []

        for row in data:
            r._use_oauth = False
            submission = r.get_submission(submission_id=row[1])
            if submission.banned_by is not None:
                r._use_oauth = False
                comment = r.get_info(thing_id="t1_" + row[2])
                unflaired_submission_obj = utils.UnflairedSubmission(submission, comment)
                unflaired_submissions.append(unflaired_submission_obj)

        return unflaired_submissions

    def delete_unflaired_submissions_row(self, submission_id):

        cur = self.db.cursor()
        cur.execute('''DELETE FROM UNFLAIRED_SUBMISSIONS WHERE SUBMISSION_ID = ?''', (submission_id,))



