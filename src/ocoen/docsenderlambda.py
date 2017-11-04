from jwcrypto import jwk
from jwcrypto.common import base64url_encode
from ocoen.docsender import DocSender
from ulid import ulid

import boto3
import json
import logging
import os
import threading

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_docsender = None


class TokenKeyProvider:

    def __init__(self, kms_client, kms_key_id, keys_bucket, keys_bucket_prefix, keys_bucket_storage_class):
        self._kms_client = kms_client
        self._kms_key_id = kms_key_id
        self._keys_bucket = keys_bucket
        self._keys_bucket_prefix = keys_bucket_prefix
        self._keys_bucket_storage_class = keys_bucket_storage_class
        self._state = None
        self._stateLock = threading.Lock()

    def get_key(self):
        with self._stateLock:
            if self._state is None or self._state['remaining_uses'] <= 0:
                self._state = self._generate_key()
            self._state['remaining_uses'] -= 1
            return self._state['key']

    def _generate_key(self):
        key_id = ulid()
        response = self._kms_client.generate_data_key(
            KeyId=self._kms_key_id,
            KeySpec='AES_256',
            EncryptionContext={
                'key_id': key_id,
                'key_role': 'docsender_tracking_token',
            }
        )
        self._keys_bucket.put_object(
            Key='{}docsender_tracking_token/{}'.format(
                self._keys_bucket_prefix,
                key_id
            ),
            Body=response['CiphertextBlob'],
            ServerSideEncryption='AES256',
            StorageClass=self._keys_bucket_storage_class,
        )
        return {
            'remaining_uses': 2 ** 24,
            'key': jwk.JWK(kty='oct', kid=key_id, k=base64url_encode(response['Plaintext'])),
        }


def load_docsender():
    ses_region = os.environ['SES_REGION']
    ses = boto3.session.Session(region_name=ses_region).client('ses')

    token_kms_key_info = os.environ['TOKEN_KMS_KEY'].split(':', 1)
    kms_client = boto3.session.Session(region_name=token_kms_key_info[0]).client('kms')

    profiles_bucket_info = os.environ['PROFILES_BUCKET'].split(':', 3)
    profiles_bucket = boto3.session.Session(
                          region_name=profiles_bucket_info[0],
                      ).resource('s3').Bucket(profiles_bucket_info[1])

    results_bucket_info = os.environ['RESULTS_BUCKET'].split(':', 3)
    results_bucket = boto3.session.Session(
                         region_name=results_bucket_info[0]
                     ).resource('s3').Bucket(results_bucket_info[1])

    keys_bucket_info = os.environ['KEYS_BUCKET'].split(':', 3)
    keys_bucket = boto3.session.Session(
                         region_name=keys_bucket_info[0]
                     ).resource('s3').Bucket(keys_bucket_info[1])
    keys_bucket_storage_class = keys_bucket_info[2]
    keys_bucket_prefix, = keys_bucket_info[3:4] or ['']

    token_key_manager = TokenKeyProvider(kms_client, token_kms_key_info[1],
                                         keys_bucket, keys_bucket_prefix, keys_bucket_storage_class)
    return DocSender(ses, profiles_bucket, results_bucket, token_key_manager.get_key)


def handle_event(event, context):
    global _docsender
    if _docsender is None:
        _docsender = load_docsender()

    sns_event = json.loads(event['Records'][0]['Sns']['Message'])
    profile_key = sns_event['profile_key']
    attachment_key = sns_event['result_key']

    _docsender.send_email(profile_key, attachment_key, sns_event)
