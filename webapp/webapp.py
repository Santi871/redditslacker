from flask import Flask, request, Response
from reddit_bot import commands_handler, utils
import requests
import os
import json

SLACK_SLASHCMDS_SECRET = utils.get_token("SLACK_SLASHCMDS_SECRET")
APP_SECRET_KEY = utils.get_token("FLASK_APP_SECRET_KEY")
SLACK_APP_ID = utils.get_token("SLACK_APP_ID")
SLACK_APP_SECRET = utils.get_token("SLACK_APP_SECRET")
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = '1'
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = '1'

app = Flask(__name__)
app.secret_key = APP_SECRET_KEY
commands_handler_obj = commands_handler.CommandsHandler()


@app.route("/oauthcallback")
def oauth_callback():
    data = {'client_id': SLACK_APP_ID, 'client_secret': SLACK_APP_SECRET, 'code': request.args.get('code')}
    response = requests.post('https://slack.com/api/oauth.access', params=data)
    print(response.json())
    return "Authorization granted!"


@app.route('/slackcommands', methods=['POST'])
def command():
    if request.form.get('token') == SLACK_SLASHCMDS_SECRET:

        response = commands_handler_obj.define_command_response(request.form)

        if response is not None:
            return Response(response=json.dumps(response), status=200, mimetype="application/json")
        else:
            commands_handler_obj.thread_command_request(request.form)
        return "Processing your request..."

    else:
        return "Invalid request token."


@app.route('/slack/action-endpoint', methods=['POST'])
def button_response():
    # ADD CHECK INTERACTIONS TOKEN
    args_dict = commands_handler_obj.find_button_request_args(dict(request.form))
    commands_handler_obj.thread_command_request(args_dict)

    return "Processing your request... please allow a few seconds."

if __name__ == '__main__':
    app.run(host='0.0.0.0')
