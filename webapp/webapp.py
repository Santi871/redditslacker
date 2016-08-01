import os
import requests
from flask import Flask, request, Response
from flask_sslify import SSLify
import reddit_interface.utils as utils
import webapp.requests_handler as commands_handler

APP_SECRET_KEY = utils.get_token("FLASK_APP_SECRET_KEY")
SLACK_APP_ID = utils.get_token("SLACK_APP_ID")
SLACK_APP_SECRET = utils.get_token("SLACK_APP_SECRET")
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = '1'
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = '1'

app = Flask(__name__, static_url_path='')
sslify = SSLify(app)
app.secret_key = APP_SECRET_KEY
commands_handler_obj = commands_handler.CommandsHandler()


@app.route('/index')
def root():
    return app.send_static_file('index.html')


@app.route("/oauthcallback")
def oauth_callback():
    data = {'client_id': SLACK_APP_ID, 'client_secret': SLACK_APP_SECRET, 'code': request.args.get('code')}
    response = requests.post('https://slack.com/api/oauth.access', params=data)
    print(response.json())
    return "Authorization granted!"


@app.route('/slack/commands', methods=['POST'])
def command():
    slack_request = utils.SlackRequest(request)
    if slack_request.is_valid:

        commands_handler_obj.db.log_command(request.form)
        response = commands_handler_obj.command_response(slack_request)

        return Response(response=response.get_json(), mimetype="application/json")

    else:
        return "Invalid request token."


@app.route('/slack/action-endpoint', methods=['POST'])
def button_response():

    slack_request = utils.SlackRequest(request)
    if slack_request.is_valid:

        response = commands_handler_obj.button_response(slack_request)

        return Response(response=response.get_json(), mimetype="application/json")

    else:
        return "Invalid request token."
