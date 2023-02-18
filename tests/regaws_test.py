import pytest
import os
from raws import AWSProfile, AWSCredentials


@pytest.fixture(scope='session')
def sample_creds():
    tmp_creds_path = os.path.join(os.getcwd(), 'tests', 'raws_test_sample_prof.txt')
    prof = AWSCredentials(tmp_creds_path)
    return prof


def test_AWSProfile_profile_name(sample_creds):
    assert sample_creds.profiles['274516845231_some-funny-guy'].profile_name == '274516845231_some-funny-guy'

def test_AWSCredentials_inject(sample_creds):
    new_profile = AWSProfile(
        profile_name='test_prof',
        aws_access_key_id='deadbeef',
        aws_secret_access_key='hababuba===2342',
    )
    sample_creds.inject_profile(new_profile)
    assert 'test_prof' in sample_creds


