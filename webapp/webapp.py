from flask import Flask, request, Response
from reddit_bot import commands_handler
from tokens import tokens
import json

SLACK_SLASHCMDS_SECRET = tokens.get_token("SLACK_SLASHCMDS_SECRET")
commands_handler_obj = commands_handler.CommandsHandler()
app = Flask(__name__)


@app.route('/slackcommands', methods=['POST'])
def command():
    if request.form.get('token') == SLACK_SLASHCMDS_SECRET:
        response = commands_handler_obj.thread_command_request(request.form)
        print(response)
        return "Processing your request..."

    else:
        return Response(), 200

if __name__ == '__main__':
    app.run()
