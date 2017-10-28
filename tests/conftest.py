from botocore.response import StreamingBody
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
            self.object_meta = {}
            pass

        def Bucket(self, bucket_name):
            if bucket_name in self.buckets:
                return self.buckets[bucket_name]

            object_data = {}
            object_meta = {}
            mock_objects = {}

            def mock_object(object_name):
                if object_name in mock_objects:
                    return mock_objects[object_name]

                body = create_autospec(StreamingBody, instance=True)
                body.read.return_value = object_data[object_name]

                def mock_get():
                    if object_name in object_meta:
                        resp = object_meta[object_name].copy()
                    else:
                        resp = {}
                    resp['Body'] = body
                    return resp

                mock = create_autospec(object_class, instance=True)
                mock.get.side_effect = mock_get

                mock_objects[object_name] = mock
                return mock

            bucket = create_autospec(bucket_class, instance=True)
            bucket.Object.side_effect = mock_object
            self.buckets[bucket_name] = bucket
            self.object_data[bucket_name] = object_data
            self.object_meta[bucket_name] = object_meta
            return bucket

    mock_s3 = MockS3()
    return mock_s3
