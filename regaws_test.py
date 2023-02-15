import pytest
from regaws import AWSProfile, build_aws_profile

@pytest.fixture()
def sample_aws_profile():
    with open('regaws_test_sample_prof.txt', 'r', encoding='utf-8') as f:
        data = f.read()
    prof = build_aws_profile(data)
    return prof


def test_AWSProfile():
    prof = AWSProfile(
        profile_name='testprof',
        aws_access_key_id='DEADBEEFDEADBEEF',
        aws_secret_access_key='huuhbabuba',
        aws_session_token='imagonnaexplode===='
    )
    assert prof.profile_name == 'testprof'
    assert 'aws_secret_access_key' not in prof.__repr__()
    assert 'aws_secret_access_key' in prof.dump()
