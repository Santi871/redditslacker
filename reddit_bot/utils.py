import json


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


class SlackResponse:

    def __init__(self, token=None, channel=None, text=None, response_type="in_channel"):
        self.response_dict = dict()
        self.token = token

        if text is not None:
            self.response_dict['text'] = text

        if token is None:
            self.response_dict['response_type'] = response_type

        if token is not None:
            self.response_dict['token'] = token
            self.response_dict['as_user'] = 'false'
            self.response_dict['channel'] = channel

    def add_attachment(self, title=None, text=None, fallback=None, callback_id=None, color=None, title_link=None,
                       image_url=None, fields=None, buttons=None):

        attachment_dict = dict()

        if fallback is not None:
            attachment_dict['fallback'] = fallback
        if callback_id is not None:
            attachment_dict['callback_id'] = callback_id
        if color is not None:
            attachment_dict['color'] = color
        if title_link is not None:
            attachment_dict['title_link'] = title_link
        if image_url is not None:
            attachment_dict['image_url'] = image_url
        if title is not None:
            attachment_dict['title'] = title
        if text is not None:
            attachment_dict['text'] = text

        if fields is not None:
            fields_list = []

            for field_obj in fields:
                fields_list.append(field_obj.field_dict)

            attachment_dict['fields'] = fields_list

        if buttons is not None:
            buttons_list = []

            for buttons_obj in buttons:
                buttons_list.append(buttons_obj.button_dict)

            attachment_dict['actions'] = buttons_list

        if "attachments" not in self.response_dict and self.token is not None:
            self.response_dict['attachments'] = json.dumps([attachment_dict])
        elif "attachments" in self.response_dict and self.token is not None:
            self.response_dict['attachments'].append(json.dumps(attachment_dict))
        elif "attachments" not in self.response_dict and self.token is None:
            self.response_dict['attachments'] = [attachment_dict]
        elif "attachments" in self.response_dict and self.token is None:
            self.response_dict['attachments'].append(attachment_dict)


