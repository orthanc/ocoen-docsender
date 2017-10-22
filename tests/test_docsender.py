from botocore.response import StreamingBody
from ocoen.docsender import DocSender
from unittest.mock import create_autospec
from yaml.error import YAMLError

import boto3
import jinja2
import ocoen.docsender
import pytest
import yaml


@pytest.fixture
def session():
    return boto3.Session(aws_access_key_id='fake', aws_secret_access_key='fake')


@pytest.fixture
def s3_buckets(session):
    s3 = session.resource('s3')
    bucket_class = s3.Bucket('test').__class__
    object_class = s3.Object('test', 'test').__class__

    class MockS3:
        def __init__(self):
            self.buckets = {}
            self.object_data = {}
            pass

        def Bucket(self, bucket_name):
            if bucket_name in self.buckets:
                return self.buckets[bucket_name]

            object_data = {}
            mock_objects = {}

            def mock_object(object_name):
                if object_name in mock_objects:
                    return mock_objects[object_name]

                body = create_autospec(StreamingBody, instance=True)
                body.read.return_value = object_data[object_name]
                mock = create_autospec(object_class, instance=True)
                mock.get.return_value = {
                    'Body': body
                }

                mock_objects[object_name] = mock
                return mock

            bucket = create_autospec(bucket_class, instance=True)
            bucket.Object.side_effect = mock_object
            self.buckets[bucket_name] = bucket
            self.object_data[bucket_name] = object_data
            return bucket

    mock_s3 = MockS3()
    return mock_s3


@pytest.fixture
def docsender(session, s3_buckets):
    ses = create_autospec(session.client('ses').__class__, instance=True)
    profile_bucket = s3_buckets.Bucket('profile')
    attachment_bucket = s3_buckets.Bucket('attachment')

    return DocSender(ses, profile_bucket, attachment_bucket)


def test_load_profile(docsender, s3_buckets):
    expected_profile = {
        'subject_template': 'test_subject',
        'body_template': 'test_body',
    }
    s3_buckets.object_data['profile']['test_profile.yaml'] = yaml.dump({'email': expected_profile})

    profile = docsender._load_profile('test_profile.yaml')

    assert expected_profile == profile


def test_load_profile_invalid_yaml(docsender, s3_buckets):
    s3_buckets.object_data['profile']['test_profile.yaml'] = '"'

    with pytest.raises(YAMLError):
        docsender._load_profile('test_profile.yaml')


def test_format_message_parts_attachment_name(docsender):
    profile = {
        'attachment_name_template': 'test {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['attachment_name'] == 'test bob'


def test_format_message_parts_attachment_name_is_not_escaped(docsender):
    profile = {
        'attachment_name_template': '<test> {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': '<bob>'})

    assert message_parts['attachment_name'] == '<test> <bob>'


def test_format_message_parts_subject(docsender):
    profile = {
        'subject_template': 'test {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['subject'] == 'test bob'


def test_format_message_parts_subject_is_not_escaped(docsender):
    profile = {
        'subject_template': '<test> {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': '<bob>'})

    assert message_parts['subject'] == '<test> <bob>'


def test_format_message_parts_subject_references_attachment(docsender):
    profile = {
        'subject_template': 'subject {{ attachment_name }}',
        'attachment_name_template': 'attachment {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['subject'] == 'subject attachment bob'


def test_format_message_parts_body_html(docsender):
    profile = {
        'body_html_template': 'test {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['body']['html'] == 'test bob'


def test_format_message_parts_body_html_is_escaped(docsender):
    profile = {
        'body_html_template': '<test> {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': '<bob>'})

    assert message_parts['body']['html'] == '<test> &lt;bob&gt;'


def test_format_message_parts_body_html_references_attachment_and_subject(docsender):
    profile = {
        'body_html_template': 'body_html {{ subject }} {{ attachment_name }}',
        'attachment_name_template': 'attachment {{ event.name }}',
        'subject_template': 'subject {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['body']['html'] == 'body_html subject bob attachment bob'


def test_format_message_parts_body_text(docsender):
    profile = {
        'body_text_template': 'test {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['body']['text'] == 'test bob'


def test_format_message_parts_body_text_is_not_escaped(docsender):
    profile = {
        'body_text_template': '<test> {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': '<bob>'})

    assert message_parts['body']['text'] == '<test> <bob>'


def test_format_message_parts_body_text_references_attachment_and_subject(docsender):
    profile = {
        'body_text_template': 'body_text {{ subject }} {{ attachment_name }}',
        'attachment_name_template': 'attachment {{ event.name }}',
        'subject_template': 'subject {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['body']['text'] == 'body_text subject bob attachment bob'


def test_format_message_parts_body_text_defaults_from_body_html(docsender):
    profile = {
        'body_html_template': '<p>{{ event.name }} and <b>bold</b></pre>',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['body']['text'] == 'bob and **bold**\n\n'


def test_format_message_parts_explicit_body_text_preferred_to_html_defaulting(docsender):
    profile = {
        'body_html_template': '<p>{{ event.name }} and <b>bold</b></pre>',
        'body_text_template': 'body_text {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['body']['text'] == 'body_text bob'


def test_format_message_parts_all(docsender):
    profile = {
        'attachment_name_template': 'attach {{ event.name }}',
        'subject_template': 'subject {{ event.name }}',
        'body_html_template': 'body_html {{ event.name }}',
        'body_text_template': 'body_text {{ event.name }}',
    }

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['attachment_name'] == 'attach bob'
    assert message_parts['subject'] == 'subject bob'
    assert message_parts['body']['html'] == 'body_html bob'
    assert message_parts['body']['text'] == 'body_text bob'


def test_format_message_parts_none(docsender):
    profile = {}

    message_parts = docsender._format_message_parts(profile, {'name': 'bob'})

    assert message_parts['attachment_name'] is None
    assert message_parts['subject'] is None
    assert message_parts['body'] == {}


def test_format_message_parts_undefined_variable(docsender):
    profile = {
        'attachment_name_template': 'test {{ event.name }}',
    }

    with pytest.raises(jinja2.exceptions.UndefinedError):
        docsender._format_message_parts(profile, {})


def test_load_attachment(docsender, s3_buckets):
    expected_data = 'test data'
    s3_buckets.object_data['attachment']['results/attachment.pdf'] = expected_data

    attachment = docsender._load_attachment('results/attachment.pdf')

    assert expected_data == attachment


def test_send_email(docsender, mocker):
    event = {'event_data': 'id'}
    profile_key = 'profile_key'
    from_ = 'from'
    to = 'to'
    attachment_name = 'attachment name'
    subject = 'subject'
    message_body = 'message body'
    profile = {
        'from': from_,
        'to': to,
        'attachment_name_template': attachment_name,
        'subject_template': subject,
        'body_text_template': message_body
    }
    attachment_key = 'attachment_key'
    attachment_data = 'test data'
    mime_message = 'test message'
    mocker.patch('ocoen.docsender.DocSender._load_profile', autospec=True, return_value=profile)
    mocker.patch('ocoen.docsender.DocSender._load_attachment', autospec=True, return_value=attachment_data)
    mocker.patch('ocoen.docsender._create_mime_message', autospec=True, return_value=mime_message)

    docsender.send_email(profile_key, attachment_key, event)

    docsender._load_profile.assert_called_once_with(docsender, profile_key)
    docsender._load_attachment.assert_called_once_with(docsender, attachment_key)
    ocoen.docsender._create_mime_message.assert_called_once_with(
        from_=from_,
        to=to,
        subject=subject,
        message_formats={
            'text': message_body,
        },
        attachment={
            'name': attachment_name,
            'data': attachment_data,
        }
    )
    docsender._ses.send_raw_email.assert_called_once_with(RawMessage={'Data': mime_message})
