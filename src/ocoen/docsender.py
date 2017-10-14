from email.message import Message
from email.policy import SMTPUTF8


def send_email(ses, from_, to, subject, msg):
    email = _create_mime_message(from_, to, subject, {"text": msg}, None)
    ses.send_raw_email(
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
