import sqlite3


class RedditSlackerDatabse:

    def __init__(self, create_tables=True):

        self.db = sqlite3.connect('redditslacker_main.db', check_same_thread=False, isolation_level=None)
        self.cur = self.db.cursor()

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
