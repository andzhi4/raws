import subprocess
from dataclasses import dataclass, field
from typing import Optional
import os
import click


AWS_DEFAULT_CREDS = '~/.aws/credentials'
if not os.environ['AWS_CRED_FILE']:
    os.environ['AWS_CRED_FILE'] = AWS_DEFAULT_CREDS

@dataclass
class AWSProfile:
    profile_name: str
    aws_access_key_id: str = field(default=None, repr=False, compare=False)
    aws_secret_access_key: str = field(default=None, repr=False, compare=False)
    aws_session_token: str = ""

    # def __post_init__(self):
    #     if self.aws_access_key_id is None:
    #         raise ValueError("aws_access_key_id is required")
    #     if self.aws_secret_access_key is None:
    #         raise ValueError("aws_secret_access_key is required")

    def dump(self):
        fields = []
        for field in self.__dataclass_fields__.values():
            name = field.name
            value = getattr(self, name)
            if value:
                if name == 'profile_name':
                    fields.append(f"[{value}]")
                else:
                    fields.append(f"{name}={value}")
        return "\n".join(fields)


def build_aws_profile(profile_txt: list[str]) -> AWSProfile:
    for line in profile_txt:
        if line.startswith('[') and line.endswith(']'):  # found another profile
            profile_name = line.strip('[]')
            # Build new profile object
            current_profile = AWSProfile(profile_name=profile_name)
        else:
            sep = line.find('=')
            field_name, field_value = line[:sep].strip(), line[sep+1:].strip()
            if not 'current_profile' in locals():
                raise ValueError(
                    f'Found {field_name} outside of profile definition')
            setattr(current_profile, field_name, field_value)
    return current_profile


def get_existing_aws_profiles(creds_file: str = os.environ['AWS_CRED_FILE']) -> dict[str, AWSProfile]:

    existing_profiles: dict[str, AWSProfile] = {}
    current_profile: Optional[AWSProfile] = None

    with open(creds_file, 'r', encoding='utf-8') as f:
        collected_lines = []
        for raw in f:
            line = raw.strip()
            if len(line) > 0:
                if line.startswith('[') and line.endswith(']'):
                    if len(collected_lines) > 0:
                        current_profile = build_aws_profile(collected_lines)
                        existing_profiles[current_profile.profile_name] = current_profile
                        collected_lines.clear()
                    collected_lines.append(line)
                else:
                    collected_lines.append(line)
        # Last profile
        current_profile = build_aws_profile(collected_lines)
        existing_profiles[current_profile.profile_name] = current_profile
        return existing_profiles


def get_aws_profile_from_clipboard() -> AWSProfile:
    clipboard_text = subprocess.check_output(['pbpaste',]).decode('utf-8')
    if not 'aws_access_key_id' in clipboard_text:
        raise ValueError('AWS Access Key is not in the clipboard')
    lines = clipboard_text.split('\n')
    prof = build_aws_profile(lines)
    return prof


def dump_profiles(profiles: dict[str, AWSProfile], target_path: str = os.environ['AWS_CRED_FILE'], setenv: bool = True) -> None:
    with open(target_path, 'w', encoding='utf-8') as f:
        for p in profiles.values():
            f.writelines(p.dump())
            f.write('\n')
        f.write('\n')


@click.command()
@click.argument('setenv', type=bool, default=True)
@click.argument('creds_file', type=str, default=os.environ['AWS_CRED_FILE'])
def main(setenv: bool, creds_file: str) -> int:
    existing_profiles = get_existing_aws_profiles()
    cb_profile = get_aws_profile_from_clipboard()
    existing_profiles[cb_profile.profile_name] = cb_profile
    dump_profiles(existing_profiles, creds_file)
    if setenv:
        os.environ['AWS_PROFILE'] = cb_profile.profile_name


if __name__ == '__main__':
    raise SystemExit(main())
