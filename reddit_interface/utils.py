import json
import configparser
import requests


def get_token(token_name, config_name='tokens.ini'):

    config = configparser.ConfigParser()
    config.read(config_name)
    token = config.get('tokens', token_name)
    return token

SLACK_SLASHCMDS_SECRET = get_token("SLACK_SLASHCMDS_SECRET")


class SlackButton:

    def __init__(self, text, value=None, style="default"):
        self.button_dict = dict()
        self.button_dict['text'] = text
        self.button_dict['name'] = text
        self.button_dict['style'] = style
        if value is None:
            self.button_dict['value'] = text
        else:
            self.button_dict['value'] = value
        self.button_dict['type'] = 'button'


class SlackField:

    def __init__(self, title, value, short="true"):
        self.field_dict = dict()
        self.field_dict['title'] = title
        self.field_dict['value'] = value
        self.field_dict['short'] = short


class SlackAttachment:

    def __init__(self, title=None, text=None, fallback=None, callback_id=None, color=None, title_link=None,
                 image_url=None):

        self.attachment_dict = dict()

        if fallback is not None:
            self.attachment_dict['fallback'] = fallback
        if callback_id is not None:
            self.attachment_dict['callback_id'] = callback_id
        if color is not None:
            self.attachment_dict['color'] = color
        if title_link is not None:
            self.attachment_dict['title_link'] = title_link
        if image_url is not None:
            self.attachment_dict['image_url'] = image_url
        if title is not None:
            self.attachment_dict['title'] = title
        if text is not None:
            self.attachment_dict['text'] = text

    def add_field(self, title, value, short="true"):

        if 'fields' not in self.attachment_dict:
            self.attachment_dict['fields'] = []

        field = SlackField(title, value, short)
        self.attachment_dict['fields'].append(field.field_dict)

    def add_button(self, text, value=None, style="default"):

        if 'actions' not in self.attachment_dict:
            self.attachment_dict['actions'] = []

        button = SlackButton(text, value, style)
        self.attachment_dict['actions'].append(button.button_dict)


class SlackResponse:

    def __init__(self, token=None, channel=None, text=None, response_type="in_channel"):
        self.response_dict = dict()
        self.attachments = []
        self.token = token

        if text is not None:
            self.response_dict['text'] = text

        if token is None:
            self.response_dict['response_type'] = response_type

        if token is not None:
            self.response_dict['token'] = token
            self.response_dict['as_user'] = 'false'
            self.response_dict['channel'] = channel

    def add_attachment(self, title=None, text=None, fallback=None, callback_id=None, color=None,
                       title_link=None,
                       image_url=None):

        if 'attachments' not in self.response_dict:
            self.response_dict['attachments'] = []

        attachment = SlackAttachment(title=title, text=text, fallback=fallback, callback_id=callback_id, color=color,
                                     title_link=title_link, image_url=image_url)

        self.attachments.append(attachment)

    def get_json(self):
        for attachment in self.attachments:
            self.response_dict['attachments'].append(attachment.attachment_dict)

        if self.token is not None:
            self.response_dict['attachments'] = json.dumps(self.response_dict['attachments'])

        return json.dumps(self.response_dict, indent=4)


class SlackRequest:

    def __init__(self, request):

        self.form = request.form
        self.request_type = "command"
        self.response = None
        self.command = None
        self.actions = None
        self.callback_id = None
        self.is_valid = False

        if 'payload' in self.form:
            self.request_type = "button"
            self.form = json.loads(dict(self.form)['payload'][0])
            self.user = self.form['user']['name']
            self.team_domain = self.form['team']['domain']
            self.callback_id = self.form['callback_id']
            self.actions = self.form['actions']
        else:
            self.user = self.form['user_name']
            self.team_domain = self.form['team_domain']
            self.command = self.form['command']
            self.text = self.form['text']

        self.response_url = self.form['response_url']
        self.token = self.form['token']

        if self.token == SLACK_SLASHCMDS_SECRET:
            self.is_valid = True

    def delayed_response(self, response):
        headers = {"content-type": "plain/text"}

        if isinstance(response, SlackResponse):
            headers = {"content-type": "application/json"}
            response = response.get_json()

        slack_response = requests.post(self.response_url, data=response, headers=headers)

        return slack_response





