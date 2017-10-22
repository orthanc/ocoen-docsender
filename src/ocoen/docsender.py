from copy import deepcopy
from email.message import Message
from email.policy import SMTPUTF8
from html2text import html2text
from jinja2 import select_autoescape, DictLoader, StrictUndefined
# from jinja2 import , DictLoader
from jinja2.sandbox import ImmutableSandboxedEnvironment

import yaml


class DocSender:

    MESSAGE_PARTS = ['attachment_name', 'subject']
    BODY_TYPES = ['html', 'text']

    def __init__(self, ses_client, profile_bucket, attachment_bucket):
        self._ses = ses_client
        self._profile_bucket = profile_bucket
        self._attachment_bucket = attachment_bucket

    def _load_profile(self, profile_key):
        profile_object = self._profile_bucket.Object(profile_key)
        profile_body = profile_object.get()['Body']
        return yaml.load(profile_body.read())['email']

    def _build_templates_dict(self, profile):
        templates = {}
        template_names = {}
        for part in DocSender.MESSAGE_PARTS:
            template_key = part + '_template'
            if template_key in profile:
                template_name = part + '.txt'
                templates[template_name] = profile[template_key]
                template_names[part] = template_name
        for type_ in DocSender.BODY_TYPES:
            template_key = 'body_{}_template'.format(type_)
            if template_key in profile:
                template_name = 'body.{}'.format(type_)
                templates[template_name] = profile[template_key]
        return templates, template_names

    def _format_message_parts(self, profile, event_in):
        event = deepcopy(event_in)
        templates, template_names = self._build_templates_dict(profile)
        envionment = ImmutableSandboxedEnvironment(
            autoescape=select_autoescape(['html']),
            auto_reload=False,
            loader=DictLoader(templates),
            undefined=StrictUndefined,
        )

        message_parts = {}
        for part in DocSender.MESSAGE_PARTS:
            if part in template_names:
                template_name = template_names[part]
                template = envionment.get_template(template_name)
                message_parts[part] = template.render(event=event, **message_parts)
            else:
                message_parts[part] = None
        body = {}
        for type_ in DocSender.BODY_TYPES:
            template_name = 'body.{}'.format(type_)
            if template_name in templates:
                template = envionment.get_template(template_name)
                body[type_] = template.render(event=event, **message_parts)
        if 'html' in body and 'text' not in body:
            body['text'] = html2text(body['html'])

        message_parts['body'] = body
        return message_parts

    def _load_attachment(self, attachment_key):
        attachment_object = self._attachment_bucket.Object(attachment_key)
        attachment_body = attachment_object.get()['Body']
        return attachment_body.read()

    def send_email(self, profile_key, event):
        # profile = self._load_profile(profile_key)
        # email = _create_mime_message(profile['from'], profile['to'], profile['subject'],
        #                              {"text": profile['message']}, None)
        # self._ses.send_raw_email(
        #     RawMessage={'Data': email},
        # )
        pass


def _create_mime_message(from_, to, subject, message_formats, attachment):
    if message_formats is None:
        raise ValueError('Message_formats must be a dict but was ' + str(message_formats))
    email = Message(policy=SMTPUTF8)
    email.set_type('multipart/mixed')
    email['From'] = from_
    email['To'] = to
    email['Subject'] = subject
    email.attach(_create_mime_body(message_formats))

    return email.as_bytes()


def _create_mime_body(message_formats):
    parts = []
    if 'text' in message_formats:
        message_part = Message(policy=SMTPUTF8)
        message_part.set_type('text/plain')
        message_part.set_payload(message_formats['text'])
        parts.append(message_part)
    if 'html' in message_formats:
        message_part = Message(policy=SMTPUTF8)
        message_part.set_type('text/html')
        message_part.set_payload(message_formats['html'])
        parts.append(message_part)
    if not parts:
        raise ValueError('Message_formats must have at least one of html or text but was ' + str(message_formats))
    if len(parts) == 1:
        return parts[0]
    else:
        alternative_part = Message(policy=SMTPUTF8)
        alternative_part.set_type('multipart/alternative')
        for part in parts:
            alternative_part.attach(part)
        return alternative_part
