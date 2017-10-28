from jwcrypto.common import base64url_encode
from ocoen.docsenderlambda import TokenKeyProvider
from unittest.mock import create_autospec

import json
import ocoen.docsender
import ocoen.docsenderlambda
import os
import pytest

kms_key_id = 'test key'
key_bytes = os.urandom(256 // 8)
encrypted_key_bytes = os.urandom(64)
keys_bucket_prefix = 'keys/'
s3_storage_class = 'TestClass'


@pytest.fixture
def token_key_provider(session, s3_buckets):
    kms = create_autospec(session.client('kms').__class__, instance=True)

    kms.generate_data_key.return_value = {
        'CiphertextBlob': encrypted_key_bytes,
        'Plaintext': key_bytes,
    }
    keys_bucket = s3_buckets.Bucket('keys')
    return TokenKeyProvider(kms, kms_key_id, keys_bucket, keys_bucket_prefix, s3_storage_class)


def test_handle_event(mocker):
    mocker.patch('ocoen.docsenderlambda._docsender')
    profile_key = 'profile'
    result_key = 'result'
    sns_event = {
        'profile_key': profile_key,
        'result_key': result_key,
    }
    event = {
        'Records': [
            {
                'Sns': {
                    'Message': json.dumps(sns_event),
                },
            },
        ],
    }

    ocoen.docsenderlambda.handle_event(event, None)

    ocoen.docsenderlambda._docsender.send_email.assert_called_once_with(profile_key, result_key, sns_event)


def test_token_key_provider_generates_key(token_key_provider):
    key = token_key_provider.get_key()

    assert key is not None
    assert key.key_id is not None
    assert key.is_symmetric


def test_token_key_provider_returns_same_key(token_key_provider):
    key1 = token_key_provider.get_key()
    key2 = token_key_provider.get_key()

    assert key1 == key2


def test_token_key_provider_decrements_remaining_uses(token_key_provider):
    token_key_provider.get_key()
    remaining_uses_1 = token_key_provider._state['remaining_uses']
    token_key_provider.get_key()
    remaining_uses_2 = token_key_provider._state['remaining_uses']

    assert remaining_uses_2 < remaining_uses_1


def test_token_key_provider_gets_new_key_when_all_uses_used(token_key_provider):
    token_key_provider.get_key()
    token_key_provider._state['remaining_uses'] = 1
    key1 = token_key_provider.get_key()
    key2 = token_key_provider.get_key()
    key3 = token_key_provider.get_key()

    assert key1 != key2
    assert key2 == key3


def test_token_key_provider_generate_key_sets_remaining_uses(token_key_provider):
    state = token_key_provider._generate_key()

    assert state['remaining_uses'] == 2 ** 24


def test_token_key_provider_generate_key_uses_kms(token_key_provider):
    key = token_key_provider._generate_key()['key']

    assert key._key['k'] == base64url_encode(key_bytes)
    token_key_provider._kms_client.generate_data_key.assert_called_once_with(
        KeyId=kms_key_id,
        KeySpec='AES_256',
        EncryptionContext={
            'key_id': key.key_id,
            'key_role': 'docsender_tracking_token',
        },
    )


def test_token_key_provider_generate_key_saves_encrypted_key_to_s3(token_key_provider):
    key = token_key_provider._generate_key()['key']

    key_s3_key = '{}docsender_tracking_token/{}'.format(keys_bucket_prefix, key.key_id)
    token_key_provider._keys_bucket.put_object.assert_called_once_with(
        Key=key_s3_key,
        Body=encrypted_key_bytes,
        ServerSideEncryption='AES256',
        StorageClass=s3_storage_class,
    )


def test_load_docsender(mocker):
    mocker.patch.dict(os.environ, {
        'SES_REGION': 'us-east-1',
        'PROFILES_BUCKET': 'us-east-2:profile_bucket:STANDARD:profiles/',
        'RESULTS_BUCKET': 'us-west-1:result_bucket:STANDARD:results/',
        'KEYS_BUCKET': 'us-west-2:key_bucket:TEST_CLASS:keys/',
        'TOKEN_KMS_KEY': 'ap-southeast-1:my_key',
    })
    used_regions = {}

    def region_tracking_mock(region_name):
        mock = mocker.MagicMock()
        used_regions[region_name] = mock
        return mock

    mock_session = mocker.MagicMock()
    mock_session.side_effect = region_tracking_mock
    mocker.patch('boto3.session.Session', mock_session)

    docsender = ocoen.docsenderlambda.load_docsender()
    token_key_manager = docsender._token_key_provider.__self__

    used_regions['us-east-1'].client.assert_called_once_with('ses')
    assert docsender._ses == used_regions['us-east-1'].client.return_value

    used_regions['us-east-2'].resource.assert_called_once_with('s3')
    used_regions['us-east-2'].resource.return_value.Bucket.assert_called_once_with('profile_bucket')
    assert docsender._profile_bucket == used_regions['us-east-2'].resource.return_value.Bucket.return_value

    used_regions['us-west-1'].resource.assert_called_once_with('s3')
    used_regions['us-west-1'].resource.return_value.Bucket.assert_called_once_with('result_bucket')
    assert docsender._attachment_bucket == used_regions['us-west-1'].resource.return_value.Bucket.return_value

    used_regions['us-west-2'].resource.assert_called_once_with('s3')
    used_regions['us-west-2'].resource.return_value.Bucket.assert_called_once_with('key_bucket')
    assert token_key_manager._keys_bucket == used_regions['us-west-2'].resource.return_value.Bucket.return_value
    assert token_key_manager._keys_bucket_prefix == 'keys/'
    assert token_key_manager._keys_bucket_storage_class == 'TEST_CLASS'

    used_regions['ap-southeast-1'].client.assert_called_once_with('kms')
    assert token_key_manager._kms_client == used_regions['ap-southeast-1'].client.return_value
    assert token_key_manager._kms_key_id == 'my_key'


def test_load_docsender_buckets_without_prefixes(mocker):
    mocker.patch.dict(os.environ, {
        'SES_REGION': 'us-east-1',
        'PROFILES_BUCKET': 'us-east-2:profile_bucket:STANDARD',
        'RESULTS_BUCKET': 'us-west-1:result_bucket:STANDARD',
        'KEYS_BUCKET': 'us-west-2:key_bucket:TEST_CLASS',
        'TOKEN_KMS_KEY': 'ap-southeast-1:my_key',
    })
    used_regions = {}

    def region_tracking_mock(region_name):
        mock = mocker.MagicMock()
        used_regions[region_name] = mock
        return mock

    mock_session = mocker.MagicMock()
    mock_session.side_effect = region_tracking_mock
    mocker.patch('boto3.session.Session', mock_session)

    docsender = ocoen.docsenderlambda.load_docsender()
    token_key_manager = docsender._token_key_provider.__self__

    assert docsender._profile_bucket == used_regions['us-east-2'].resource.return_value.Bucket.return_value
    assert docsender._attachment_bucket == used_regions['us-west-1'].resource.return_value.Bucket.return_value
    assert token_key_manager._keys_bucket == used_regions['us-west-2'].resource.return_value.Bucket.return_value
    assert token_key_manager._keys_bucket_prefix == ''
    assert token_key_manager._keys_bucket_storage_class == 'TEST_CLASS'
