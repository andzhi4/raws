from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, NoReturn
import argparse
import os
import subprocess


AWS_DEFAULT_CREDS = '~/.aws/credentials'
if not os.environ['AWS_CRED_FILE']:
    os.environ['AWS_CRED_FILE'] = AWS_DEFAULT_CREDS


class ProfileError(Exception):
    """Exception raised when a profile is not found."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


@dataclass
class AWSProfile:
    profile_name: str
    aws_access_key_id: Optional[str] = field(default=None, repr=False, compare=False)
    aws_secret_access_key: Optional[str] = field(default=None, repr=False, compare=False)
    aws_session_token: Optional[str] = ""

    def dump(self) -> str:
        fields = []
        for f in self.__dataclass_fields__.values():
            name = f.name
            value = getattr(self, name)
            if value:
                if name == 'profile_name':
                    fields.append(f"[{value}]")
                else:
                    fields.append(f"{name}={value}")
        return "\n".join(fields)

    def copy(self) -> AWSProfile:
        return AWSProfile(
            self.profile_name,
            self.aws_access_key_id,
            self.aws_secret_access_key,
            self.aws_session_token
        )


def build_aws_profile(profile_txt: list[str]) -> AWSProfile:
    for line in profile_txt:
        if line.startswith('[') and line.endswith(']'):  # found another profile
            profile_name = line.strip('[]')
            # Build new profile object
            current_profile = AWSProfile(profile_name=profile_name)
        else:
            sep = line.find('=')
            field_name, field_value = line[:sep].strip(), line[sep + 1:].strip()
            if 'current_profile' not in locals():
                raise ValueError(
                    f'Found {field_name} outside of profile definition')
            setattr(current_profile, field_name, field_value)
    return current_profile


def get_existing_aws_profiles(creds_file: str = os.environ['AWS_CRED_FILE']) -> dict[str, AWSProfile]:

    existing_profiles: dict[str, AWSProfile] = {}
    current_profile: Optional[AWSProfile] = None

    with open(creds_file, 'r', encoding='utf-8') as f:
        collected_lines: list[str] = []
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


def list_profiles() -> str:
    profs = get_existing_aws_profiles()
    return '- ' + '\n- '.join(list(profs.keys()))


def get_aws_profile_from_clipboard() -> AWSProfile:
    clipboard_text = subprocess.check_output(['pbpaste',]).decode('utf-8')
    if 'aws_access_key_id' not in clipboard_text:
        raise ValueError('AWS Access Key is not in the clipboard')
    lines = clipboard_text.split('\n')
    prof = build_aws_profile(lines)
    return prof


def get_aws_profile_from_env() -> AWSProfile:
    profile_name = 'env_profile'
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_session_token = os.environ.get('AWS_SESSION_TOKEN')
    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError(
            """AWS credentials env vars not configured properly.
            Make sure both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set.""")
    return AWSProfile(
        profile_name=profile_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token
    )


def dump_profiles(profiles: dict[str, AWSProfile], target_path: str = os.environ['AWS_CRED_FILE']) -> None:
    with open(target_path, 'w', encoding='utf-8') as f:
        for p in profiles.values():
            f.writelines(p.dump())
            f.write('\n')
        f.write('\n')


def main() -> int:
    # Create the parser
    parser = argparse.ArgumentParser(
        description='Manage profiles in AWS credentials file')
    parser.add_argument('--creds_file', type=str,
                        required=False, default=os.environ['AWS_CRED_FILE'],
                        help='Override AWS Credentials file location')

    # Add the subcommands
    subparsers = parser.add_subparsers(dest='command')

    # Add the "add" subcommand
    add_parser = subparsers.add_parser('add', help='Add new profile')
    add_parser.add_argument(
        'source', type=str, help='Where to look for the new profile (cb = clipboard)')
    add_parser.add_argument('--setdefault', type=str,
                            default='n', help='Save the added profile as default')

    # Add "list" command
    list_parser = subparsers.add_parser(  # noqa: F841
        'list', aliases=['ls',], help='Show existing profiles')

    # Add "backup" command
    backup_parser = subparsers.add_parser(
        'backup', aliases=['bckp'], help='Backup existing profiles')
    backup_parser.add_argument('--dest', type=str,
                               default=os.environ['AWS_CRED_FILE'] + '-'
                               + datetime.now().strftime('%Y-%m-%d-%H%M%S')
                               + '.bkp',
                               help='Save the added profile as default')

    # Add "delete" command
    delete_parser = subparsers.add_parser(
        'delete', aliases=['del'], help='Backup existing profiles')
    delete_parser.add_argument('profile', type=str,
                               help='Delete profile by name')

    # Add "setdefault" command
    setdefault_parser = subparsers.add_parser(
        'setdefault', aliases=['setdef',], help='Set given profile as default')
    setdefault_parser.add_argument('profile', type=str,
                                   help='Profile name to make default')

    # Add "setdefault" command
    setdefault_parser = subparsers.add_parser(
        'show', help='Show full profile info')
    setdefault_parser.add_argument('profile', type=str,
                                   help='Profile name to show')

    # Parse the arguments and call the appropriate function
    args = parser.parse_args()

    try:
        if args.command == 'add':
            if args.source.lower() in ['cb', 'clipboard']:
                new_profile = get_aws_profile_from_clipboard()
            elif args.source.lower() in ['env', 'environment']:
                new_profile = get_aws_profile_from_env()
            else:
                raise ValueError('Unknown profile source')

            if args.setdefault.lower() in ['y', 'yes']:
                new_profile.profile_name = 'default'
            existing_profiles = get_existing_aws_profiles()
            existing_profiles[new_profile.profile_name] = new_profile
            dump_profiles(existing_profiles, args.creds_file)

        elif args.command in ('list', 'ls'):
            print(f'AWS profiles in {args.creds_file}')
            print(list_profiles())

        elif args.command in ('backup', 'bckp'):
            existing_profiles = get_existing_aws_profiles()
            dump_profiles(existing_profiles, args.dest)

        elif args.command in ('delete', 'del'):
            existing_profiles = get_existing_aws_profiles()
            if args.profile in existing_profiles:
                del (existing_profiles[args.profile])
            else:
                raise ProfileError(f'Profile {args.profile} does not exist')
            dump_profiles(existing_profiles, args.creds_file)

        elif args.command in ('setdefault', 'setdef'):
            existing_profiles = get_existing_aws_profiles()
            if args.profile in existing_profiles:
                new_default = existing_profiles[args.profile].copy()
                new_default.profile_name = 'default'
                existing_profiles['default'] = new_default
            else:
                raise ProfileError(f'Profile {args.profile} does not exist')
            dump_profiles(existing_profiles, args.creds_file)

        elif args.command in ('show'):
            existing_profiles = get_existing_aws_profiles()
            if args.profile in existing_profiles:
                print(existing_profiles[args.profile].dump())
            else:
                raise ProfileError(f'Profile {args.profile} does not exist')

    except ProfileError as e:
        print(e.message)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
