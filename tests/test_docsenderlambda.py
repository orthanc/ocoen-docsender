import ocoen.docsender
import ocoen.docsenderlambda
import json


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
