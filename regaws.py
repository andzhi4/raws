from __future__ import annotations
import argparse
from datetime import datetime
import subprocess
from dataclasses import dataclass, field
from typing import Optional
import os
import argparse


AWS_DEFAULT_CREDS = '~/.aws/credentials'
if not os.environ['AWS_CRED_FILE']:
    os.environ['AWS_CRED_FILE'] = AWS_DEFAULT_CREDS


@dataclass
class AWSProfile:
    profile_name: str
    aws_access_key_id: str = field(default=None, repr=False, compare=False)
    aws_secret_access_key: str = field(default=None, repr=False, compare=False)
    aws_session_token: str = ""

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


def list_profiles() -> str:
    profs = get_existing_aws_profiles()
    return '- '+'\n- '.join(list(profs.keys()))


def get_aws_profile_from_clipboard() -> AWSProfile:
    clipboard_text = subprocess.check_output(['pbpaste',]).decode('utf-8')
    if not 'aws_access_key_id' in clipboard_text:
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
                        required=False, default=os.environ['AWS_CRED_FILE'])

    # Add the subcommands
    subparsers = parser.add_subparsers(dest='command')

    # Add the "add" subcommand
    add_parser = subparsers.add_parser('add', help='Add new profile')
    add_parser.add_argument(
        'source', type=str, help='Where to look for the new profile (cb = clipboard)')
    add_parser.add_argument('--setdefault', type=str,
                            default='n', help='Save the added profile as default')

    # Add "list" command
    list_parser = subparsers.add_parser('list', help='Show existing profiles')

    # Add "backup" command
    backup_parser = subparsers.add_parser(
        'backup', help='Backup existing profiles')
    backup_parser.add_argument('--dest', type=str,
                               default=os.environ['AWS_CRED_FILE'] + '-' + datetime.now().strftime('%Y-%m-%d-%H%M%S') +'.bkp', 
                               help='Save the added profile as default')

    # Add "delete" command
    delete_parser =a subparsers.add_parser(
        'delete', help='Backup existing profiles')
    delete_parser.add_argument('profile', type=str,
                               help='Delete profile by name')

    # Parse the arguments and call the appropriate function
    args = parser.parse_args()
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

    elif args.command == 'list':
        print(f'AWS profiles in {args.creds_file}')
        print(list_profiles())

    elif args.command == 'backup':
        existing_profiles = get_existing_aws_profiles()
        dump_profiles(existing_profiles, args.dest)
    
    elif args.command == 'delete':
        existing_profiles = get_existing_aws_profiles()
        if args.profile in existing_profiles:
            del(existing_profiles[args.profile])
        else:
            raise ValueError(f'Profile {args.profile} does not exist')
        dump_profiles(existing_profiles, args.creds_file)

    
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
