from botocore.response import StreamingBody
from ocoen.docsender import DocSender
from unittest.mock import create_autospec
from yaml.error import YAMLError

import boto3
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


def test_load_attachment(docsender, s3_buckets):
    expected_data = 'test data'
    s3_buckets.object_data['attachment']['results/attachment.pdf'] = expected_data

    attachment = docsender._load_attachment('results/attachment.pdf')

    assert expected_data == attachment
