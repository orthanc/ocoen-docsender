from ocoen.docsender import DocSender

import boto3
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_docsender = None


def load_docsender():
    ses_region = os.environ['SES_REGION']
    ses = boto3.session.Session(region_name=ses_region).client('ses')

    profiles_bucket_info = os.environ['PROFILES_BUCKET'].split(':', 2)
    profiles_bucket = boto3.session.Session(
                          region_name=profiles_bucket_info[0],
                      ).resource('s3').Bucket(profiles_bucket_info[1])

    results_bucket_info = os.environ['RESULTS_BUCKET'].split(':', 2)
    results_bucket = boto3.session.Session(
                         region_name=results_bucket_info[0]
                     ).resource('s3').Bucket(results_bucket_info[1])

    return DocSender(ses, profiles_bucket, results_bucket)


def handle_event(event, context):
    global _docsender
    if _docsender is None:
        _docsender = load_docsender()

    sns_event = json.loads(event['Records'][0]['Sns']['Message'])
    profile_key = sns_event['profile_key']
    attachment_key = sns_event['result_key']

    _docsender.send_email(profile_key, attachment_key, sns_event)
