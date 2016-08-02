import json
import requests
import praw.helpers
import configparser


def get_token(token_name, config_name='tokens.ini'):

    config = configparser.ConfigParser()
    config.read(config_name)
    token = config.get('tokens', token_name)
    return token

SLACK_SLASHCMDS_SECRET = get_token("SLACK_SLASHCMDS_SECRET")
SLACK_BOT_TOKEN = get_token('SLACK_BOT_TOKEN')


class RSConfig:

    def __init__(self, filename):
        self.config = configparser.ConfigParser()
        self.config.read(filename)

    def get_config(self, name, section, var_type=None):

        if var_type is None:
            return self.config.getint(section, name)

        elif var_type == 'str':
            return str(self.config.get(section, name))

        elif var_type == "bool":
            return self.config.getboolean(section, name)

    def set_config(self, name, section, value):

        try:
            self.get_config(name, section)
        except configparser.NoOptionError:
            return False

        self.config[section][name] = value
        return True


class SlackButton:

    def __init__(self, text, value=None, style="default", confirm=None, yes=None):
        self.button_dict = dict()
        self.button_dict['text'] = text
        self.button_dict['name'] = text
        self.button_dict['style'] = style
        if value is None:
            self.button_dict['value'] = text
        else:
            self.button_dict['value'] = value
        self.button_dict['type'] = 'button'

        if confirm is not None:
            confirm_dict = dict()
            confirm_dict['title'] = "Are you sure?"
            confirm_dict['text'] = confirm
            confirm_dict['ok_text'] = yes
            confirm_dict['dismiss_text'] = 'Cancel'
            self.button_dict['confirm'] = confirm_dict


class SlackField:

    def __init__(self, title, value, short="true"):
        self.field_dict = dict()
        self.field_dict['title'] = title
        self.field_dict['value'] = value
        self.field_dict['short'] = short


class SlackAttachment:

    def __init__(self, title=None, text=None, fallback=None, callback_id=None, color=None, title_link=None,
                 image_url=None, footer=None):

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
        if footer is not None:
            self.attachment_dict['footer'] = footer

        self.attachment_dict['mrkdwn_in'] = ['title', 'text']

    def add_field(self, title, value, short="true"):

        if 'fields' not in self.attachment_dict:
            self.attachment_dict['fields'] = []

        field = SlackField(title, value, short)
        self.attachment_dict['fields'].append(field.field_dict)

    def add_button(self, text, value=None, style="default", confirm=None, yes=None):

        if 'actions' not in self.attachment_dict:
            self.attachment_dict['actions'] = []

        button = SlackButton(text, value, style, confirm, yes)
        self.attachment_dict['actions'].append(button.button_dict)


class SlackResponse:

    def __init__(self, text=None, response_type="in_channel", replace_original=True):
        self.response_dict = dict()
        self.attachments = []
        self._is_prepared = False

        if text is not None:
            self.response_dict['text'] = text

        if not replace_original:
            self.response_dict['replace_original'] = 'false'

        self.response_dict['response_type'] = response_type

    def add_attachment(self, title=None, text=None, fallback=None, callback_id=None, color=None,
                       title_link=None, footer=None,
                       image_url=None):

        if 'attachments' not in self.response_dict:
            self.response_dict['attachments'] = []

        attachment = SlackAttachment(title=title, text=text, fallback=fallback, callback_id=callback_id, color=color,
                                     title_link=title_link, image_url=image_url, footer=footer)

        self.attachments.append(attachment)

    def _prepare(self):
        for attachment in self.attachments:
            self.response_dict['attachments'].append(attachment.attachment_dict)

        self._is_prepared = True

    def get_json(self):
        if not self._is_prepared:
            self._prepare()

        return json.dumps(self.response_dict)

    def get_dict(self):
        if not self._is_prepared:
            self._prepare()

        return self.response_dict

    def post_to_channel(self, channel, as_user=False):

        response_dict = self.get_dict()
        response_dict['attachments'] = json.dumps(self.response_dict['attachments'])
        response_dict['channel'] = channel
        response_dict['token'] = SLACK_BOT_TOKEN

        if as_user:
            response_dict['as_user'] = 'true'

        request_response = requests.post('https://slack.com/api/chat.postMessage',
                                         params=response_dict)

        return request_response

    def update_message(self, timestamp, channel, parse='full'):

        response_dict = self.get_dict()
        response_dict['attachments'] = json.dumps(self.response_dict['attachments'])
        response_dict['channel'] = channel
        response_dict['token'] = SLACK_BOT_TOKEN
        response_dict['ts'] = timestamp
        response_dict['as_user'] = 'true'
        response_dict['parse'] = parse

        request_response = requests.post('https://slack.com/api/chat.update',
                                         params=response_dict)


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
            self.user_id = self.form['user']['id']
            self.team_domain = self.form['team']['domain']
            self.callback_id = self.form['callback_id']
            self.actions = self.form['actions']
            self.message_ts = self.form['message_ts']
            self.original_message = self.form['original_message']
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


def grab_attachment_args(original_message):
    attachment_text = original_message['attachments'][0]['text']
    attachment_title = original_message['attachments'][0]['title']

    attachment_title_link = original_message['attachments'][0].get('title_link', '')

    field = original_message['attachments'][0].get('fields', None)[0]

    return {'text': attachment_text, 'title': attachment_title, 'title_link': attachment_title_link, 'field': field}


class UnflairedSubmission:

    def __init__(self, submission, comment):
        self.submission = submission
        self.comment = comment


def get_unflaired_submissions(r, submission_ids):

    unflaired_submissions = []

    for submission_id in submission_ids:
        r._use_oauth = False
        submission = r.get_submission(submission_id=submission_id)
        flat_comments = praw.helpers.flatten_tree(submission.comments)

        for comment in flat_comments:
            if comment.author.name.lower() == 'eli5_botmod':
                unflaired_submission = UnflairedSubmission(submission, comment)
                unflaired_submissions.append(unflaired_submission)
                break

    return unflaired_submissions


def generate_flair_comment(s1, s2, s3):
    comment = ("""Hi /u/%s,

It looks like you haven't assigned a category flair to your question, so it has been automatically removed.
You can assign a category flair to your question by clicking the *flair* button under it.

Shortly after you have assigned a category flair to your question, it will be automatically re-approved and
 this message
will be deleted.

**Mobile users:** some reddit apps don't support flair selection (including the official one). In order to
 flair your
question, open it in your phone's web browser by clicking [this link](%s) and select
flair as you would in a desktop computer.

---

*I am a bot, and this action was performed automatically.
Please [contact the moderators](%s) if you have any questions or concerns*
""") % (s1, s3, s2)

    return comment






