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

def test_AWSCredentials_setdefautl(sample_creds):
    new_default = sample_creds.setdefault('274516845231_some-funny-guy')
    assert 'default' in sample_creds
    assert sample_creds.profiles['default'].aws_access_key_id == 'ASIAT733AJAOEMDAGJHK'


def test_AWSCredentials_inject_profile_from_env(sample_creds):
    os.environ['AWS_ACCESS_KEY_ID'] = "DEADBEEF"
    os.environ['AWS_SECRET_ACCESS_KEY'] = "VERYSECRET"
    os.environ['AWS_SESSION_TOKEN'] = "SPOKENTOKEN"
    _ = sample_creds.inject_profile_from(source='env')
    assert 'env_profile' in sample_creds
    assert sample_creds.profiles['env_profile'].aws_secret_access_key == 'VERYSECRET'


