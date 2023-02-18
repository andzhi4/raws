import pytest
import os
import shutil
from raws import AWSProfile, AWSCredentials


@pytest.fixture
def sample_creds_file(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("data")
    test_creds_path = os.path.join(os.getcwd(), 'tests', 'raws_test_sample_prof.txt')
    shutil.copy(test_creds_path, temp_dir)
    return temp_dir / os.path.basename(test_creds_path)


@pytest.fixture(scope='function')
def sample_creds(sample_creds_file):
    prof = AWSCredentials(sample_creds_file)
    return prof


def test_AWSProfile_profile_name(sample_creds):
    assert sample_creds.profiles['some-funny-guy'].profile_name == 'some-funny-guy'


def test_AWSCredentials_inject_profile(sample_creds):
    new_profile = AWSProfile(
        profile_name='test_prof',
        aws_access_key_id='deadbeef',
        aws_secret_access_key='hababuba===2342',
    )
    sample_creds.inject_profile(new_profile)
    assert 'test_prof' in sample_creds


def test_AWSCredentials_setdefautl(sample_creds):
    new_default = sample_creds.setdefault('some-funny-guy')
    assert 'default' in sample_creds
    assert sample_creds.profiles['default'].aws_access_key_id == 'ASIAT733AJAOEMDAGJHK'


def test_AWSCredentials_inject_profile_from_env(sample_creds):
    os.environ['AWS_ACCESS_KEY_ID'] = "DEADBEEF"
    os.environ['AWS_SECRET_ACCESS_KEY'] = "VERYSECRET"
    os.environ['AWS_SESSION_TOKEN'] = "SPOKENTOKEN"
    _ = sample_creds.inject_profile_from(source='env')
    assert 'env_profile' in sample_creds
    assert sample_creds.profiles['env_profile'].aws_secret_access_key == 'VERYSECRET'


def test_AWSCredentials_delete_profile(sample_creds):
    sample_creds.delete_profile('some-funny-guy')
    assert 'some-funny-guy' not in sample_creds
    assert len(sample_creds) == 0


def test_AWSCredentials_list(sample_creds):
    result = sample_creds.list()
    assert 'some-funny-guy' in result


def test_AWSCredentials_show(sample_creds):
    result = sample_creds.show('some-funny-guy')
    assert 'ASIAT733AJAOEMDAGJHK' in result


def test_AWSCredentials_save(sample_creds, tmp_path):
    save_path = tmp_path / 'creds.txt'
    sample_creds.save(save_path)
    data = save_path.read_text()
    assert save_path.exists()
    assert '[some-funny-guy]' in data


def test_AWSCredentials_backup(sample_creds, tmp_path):
    save_path = tmp_path / 'creds.bkp'
    sample_creds.backup(save_path)
    data = save_path.read_text()
    assert save_path.exists()
    assert '[some-funny-guy]' in data


def test_AWSCredentials_restore(sample_creds, sample_creds_file):
    sample_creds.backup()
    os.remove(sample_creds_file)
    sample_creds.restore()
    assert sample_creds_file.exists()


def test_AWSCredentials_rename(sample_creds):
    result = sample_creds.rename('some-funny-guy', 'renamed_profile')
    assert 'renamed_profile' in sample_creds
