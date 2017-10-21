from botocore.response import StreamingBody
from ocoen.docsender import DocSender
from unittest.mock import create_autospec

import boto3
import pytest


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
def docsender(mocker, session, s3_buckets):
    ses = create_autospec(session.client('ses').__class__, instance=True)
    profile_bucket = s3_buckets.Bucket('profile')
    attachment_bucket = s3_buckets.Bucket('attachment')

    return DocSender(ses, profile_bucket, attachment_bucket)
