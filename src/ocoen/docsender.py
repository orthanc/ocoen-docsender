from copy import deepcopy
from email.message import EmailMessage
from email.policy import SMTPUTF8
from html2text import html2text
from jinja2 import select_autoescape, DictLoader, StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment
from jwcrypto import jwe
from jwcrypto.common import json_encode

import logging
import time
import yaml


logger = logging.getLogger(__name__)


class DocSender:

    MESSAGE_PARTS = ['attachment_name', 'subject']
    BODY_TYPES = ['html', 'text']

    def __init__(self, ses_client, profile_bucket, attachment_bucket, token_key_provider=None):
        self._ses = ses_client
        self._profile_bucket = profile_bucket
        self._attachment_bucket = attachment_bucket
        self._token_key_provider = token_key_provider

    def _load_profile(self, profile_key):
        profile_object = self._profile_bucket.Object(profile_key)
        profile_body = profile_object.get()['Body']
        return yaml.load(profile_body.read())['email']

    def _create_tracking_token(self, **kwargs):
        if self._token_key_provider is None:
            return None
        token_key = self._token_key_provider()
        token = jwe.JWE(
            protected={
                'alg': 'dir',
                'enc': 'A256GCM',
                'kid': token_key.key_id,
                'zip': 'DEF',
            },
            plaintext=json_encode(kwargs),
            recipient=token_key
        )
        return token.serialize(compact=True)

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
        attachment_response = attachment_object.get()
        attachment_body = attachment_response['Body']
        return attachment_body.read(), attachment_response['ContentType'].split('/')

    def send_email(self, profile_key, attachment_key, event):
        time_start = time.time()
        profile = self._load_profile(profile_key)
        time_load_profile = time.time()
        attachment_data, attachment_type = self._load_attachment(attachment_key)
        time_load_attachment = time.time()
        tracking_token = self._create_tracking_token(
            profile_key=profile_key,
            profile=profile,
            event=event
        )
        time_create_tracking_token = time.time()
        message_parts = self._format_message_parts(profile, event)
        time_format_message = time.time()
        email = _create_mime_message(
            from_=profile['from'],
            to=profile['to'],
            subject=message_parts['subject'],
            message_formats=message_parts['body'],
            tracking_token=tracking_token,
            attachment={
                'name': message_parts['attachment_name'],
                'data': attachment_data,
                'type': attachment_type,
            },
        )
        time_create_mime_message = time.time()
        self._ses.send_raw_email(
            RawMessage={'Data': email},
        )
        time_send_email = time.time()
        logger.debug('\n'.join([
            'send_email timings:',
            'load_profile: ' + str(time_load_profile - time_start),
            'load_attachment: ' + str(time_load_attachment - time_load_profile),
            'create_tracking_token: ' + str(time_create_tracking_token - time_load_attachment),
            'format_message: ' + str(time_format_message - time_create_tracking_token),
            'create_mime_message: ' + str(time_create_mime_message - time_format_message),
            'send_raw_email: ' + str(time_send_email - time_create_mime_message),
            'email size: ' + str(len(email)),
            'attachment size: ' + str(len(attachment_data)),
        ]))


def _create_mime_message(from_, to, subject, message_formats, attachment=None, tracking_token=None):
    if message_formats is None:
        raise ValueError('Message_formats must be a dict but was ' + str(message_formats))
    email = _create_mime_body(message_formats)
    email.make_mixed()
    email['From'] = from_
    email['To'] = to
    email['Subject'] = subject
    if tracking_token is not None:
        email['x-ocoen-tracking-token'] = tracking_token

    if attachment is not None:
        email.add_attachment(attachment['data'], filename=attachment['name'],
                             maintype=attachment['type'][0], subtype=attachment['type'][1])

    return email.as_bytes()


def _create_mime_body(message_formats):
    message = EmailMessage(policy=SMTPUTF8)
    has_content = False
    if 'text' in message_formats:
        message.set_content(message_formats['text'])
        has_content = True
    if 'html' in message_formats:
        if has_content:
            message.add_alternative(message_formats['html'], subtype='html')
        else:
            message.set_content(message_formats['html'], subtype='html')
        has_content = True
    if not message:
        raise ValueError('Message_formats must have at least one of html or text but was ' + str(message_formats))
    return message
