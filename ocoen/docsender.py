from email.message import Message
from email.policy import SMTPUTF8


def _format_email(from_, to, message, attachment):
    if message is None:
        raise ValueError('Message must be a dict but was ' + str(message))
    email = Message(policy=SMTPUTF8)
    email.set_type('multipart/mixed')
    email['From'] = from_
    email['To'] = to

    email.attach(_format_message(message))

    return email.as_bytes()


def _format_message(message):
    parts = []
    if 'text' in message:
        message_part = Message(policy=SMTPUTF8)
        message_part.set_payload(message['text'])
        parts.append(message_part)
    if 'html' in message:
        message_part = Message(policy=SMTPUTF8)
        message_part.set_type('text/html')
        message_part.set_payload(message['html'])
        parts.append(message_part)
    if not parts:
        raise ValueError('Message must have at least one of html or text but was ' + str(message))
    if len(parts) == 1:
        return parts[0]
    else:
        alternative_part = Message(policy=SMTPUTF8)
        alternative_part.set_type('multipart/alternative')
        for part in parts:
            alternative_part.attach(part)
        return alternative_part
