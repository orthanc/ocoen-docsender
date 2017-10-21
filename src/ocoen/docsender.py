from email.message import Message
from email.policy import SMTPUTF8


class DocSender:

    def __init__(self, ses_client, profile_bucket, attachment_bucket):
        self._ses = ses_client
        self._profile_bucket = profile_bucket
        self._attachment_bucket = attachment_bucket

    def _load_profile(self, profile_key):
        # Load profile from s3 bucket
        # parse json
        # return dict
        pass

    def _create_message_body(self, template, event, attachment_name):
        # jinja2 format template to produce html body
        # html2text to produce text fallback
        # return dict matching create_mime_message
        pass

    def _load_attachment(self, name_template, attachment_key, event):
        # retrive attachment from s3 bucket
        # format Jinja2 template name
        # return tuple of name, attachment
        pass

    def send_email(self, profile_key, event):
        profile = self._load_profile(profile_key)
        email = _create_mime_message(profile['from'], profile['to'], profile['subject'],
                                     {"text": profile['message']}, None)
        self._ses.send_raw_email(
            RawMessage={'Data': email},
        )


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
