from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import argparse
import os
import subprocess


# Env variable init to reference the credentials file
DEFAULT_CREDS_LOCATION = os.path.join(os.path.expanduser('~'), '.aws', 'credentials')
if 'AWS_CREDS_FILE' not in os.environ\
        or not os.path.isdir(os.path.dirname(os.environ['AWS_CREDS_FILE'])):
    # Replace the variable value in the contex of the current process
    os.environ['AWS_CREDS_FILE'] = DEFAULT_CREDS_LOCATION


class ProfileError(Exception):
    """Exception raised when profile is not found or malformed"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


@dataclass
class AWSProfile:
    """
    Represents a single aws profile comprised of several tokens.
    Supported methods:
        dump(): to easily save the profile in a text file.
        copy(): yields new profile with similar tokens, used to avoid
                multiple variables binding to a single profile
    All fields except name are optional since profile might be built gradually,
    i.e. not all the values determinet at the init time
    """
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


class AWSCredentials():
    """
    A class that stores all currently registered AWS profiles
    and allows basic manipulations on them.
    Supported methods:
        __init__: builds a dict of current profiles from a file referenced by
                  the AWS_CREDS_FILE environment variable (if not set beforehand,
                  initialized with the default value during the module init)

        setdefault: copy specified profile under 'default' name

        inject_profile: adds new AWSProfile to the self.profiles

        inject_profile_from: adds profile from the clipboard or from a set of
                             environment variables

        delete_profile: remove given profile from self.profiles

        list: lists all registered profiles

        show: shows detailed representation of a given profile

        save: saves profiles to AWS_CREDS_FILE location, replacing its contents

        backup: create a beckup copy of current AWS_CREDS_FILE in the specified location
    """

    def __init__(self) -> None:
        self.profiles = self._get_profiles_from_creds()

    def _build_profile(self, profile_txt: list[str]) -> AWSProfile:
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

    def _get_profiles_from_creds(self, creds_file: str = os.environ['AWS_CREDS_FILE']) -> dict[str, AWSProfile]:

        existing_profiles: dict[str, AWSProfile] = {}
        current_profile: Optional[AWSProfile] = None

        with open(creds_file, 'r', encoding='utf-8') as f:
            collected_lines: list[str] = []
            for raw in f:
                line = raw.strip()
                if len(line) > 0:
                    if line.startswith('[') and line.endswith(']'):
                        if len(collected_lines) > 0:
                            current_profile = self._build_profile(collected_lines)
                            existing_profiles[current_profile.profile_name] = current_profile
                            collected_lines.clear()
                        collected_lines.append(line)
                    else:
                        collected_lines.append(line)
            # Last profile
            current_profile = self._build_profile(collected_lines)
            existing_profiles[current_profile.profile_name] = current_profile
            return existing_profiles

    def _get_profile_from_clipboard(self) -> AWSProfile:
        clipboard_text = subprocess.check_output(['pbpaste',]).decode('utf-8')
        if 'aws_access_key_id' not in clipboard_text:
            raise ValueError('AWS Access Key is not in the clipboard')
        lines = clipboard_text.split('\n')
        prof = self._build_profile(lines)
        return prof

    def _get_profile_from_env(self) -> AWSProfile:
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

    def setdefault(self, profile_name: str) -> None:
        try:
            new_default = self.profiles[profile_name].copy()
            new_default.profile_name = 'default'
            self.profiles['default'] = new_default
        except KeyError:
            raise ProfileError(f'Profile {profile_name} does not exist')

    def inject_profile(self, profile: AWSProfile, setdefault: bool = False, strict: bool = False) -> None:
        if strict and profile.profile_name in self.profiles:
            raise ProfileError(f'Profile {profile} already exists and strict mode specified')
        else:
            self.profiles[profile.profile_name] = profile
        if setdefault:
            self.setdefault(profile.profile_name)

    def inject_profile_from(self, source: str, setdefault: bool = False, strict: bool = False) -> None:
        if source.lower() in ('cb', 'clipboard'):
            new_profile = self._get_profile_from_clipboard()
        elif source.lower() in ('env', 'environment'):
            new_profile = self._get_profile_from_env()
        if strict and new_profile.profile_name in self.profiles:
            raise ProfileError(f'Profile {new_profile} already exists and strict mode specified')
        self.profiles[new_profile.profile_name] = new_profile
        if setdefault:
            self.setdefault(new_profile.profile_name)

    def delete_profile(self, profile_name: str) -> None:
        try:
            del (self.profiles[profile_name])
        except KeyError:
            raise ProfileError(f'Profile {profile_name} does not exist')

    def list(self) -> str:
        """List all profiles in the credentials file"""
        return '- ' + '\n- '.join(list(self.profiles.keys()))

    def show(self, profile_name: str) -> str:
        """Show details of particular profile from the credentials file"""
        try:
            return self.profiles[profile_name].dump()
        except KeyError:
            raise ProfileError(f'Profile {profile_name} does not exist')

    def save(self, target_path: str = os.environ['AWS_CREDS_FILE']) -> None:
        with open(target_path, 'w', encoding='utf-8') as f:
            for p in self.profiles.values():
                f.writelines(p.dump())
                f.write('\n')
            f.write('\n')

    def backup(self, location: Optional[str] = None) -> None:
        if not location:
            cur_path = os.environ['AWS_CREDS_FILE']
            dt = datetime.now().strftime('%Y-%m-%d-%H%M%S')
            location = f'{cur_path}-{dt}.bkp'
        self.save(target_path=location)

    def __repr__(self) -> str:
        cred_file = os.environ['AWS_CREDS_FILE']
        return f'<AWSCredentials>, file: {cred_file}\n' + self.list()


def main() -> int:
    # Create the parser
    parser = argparse.ArgumentParser(
        description='Manage profiles in AWS credentials file')
    parser.add_argument('--creds_location', type=str,
                        required=False, default=os.environ['AWS_CREDS_FILE'],
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
    backup_parser.add_argument('--dest', type=str, default=None)

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

    # Add "show" command
    show_parser = subparsers.add_parser(
        'show', help='Show full profile info')
    show_parser.add_argument('profile', type=str,
                             help='Profile name to show')

    # Parse the arguments and call the appropriate methods
    args = parser.parse_args()
    local_profiles = AWSCredentials()
    try:
        if args.command == 'add':
            default = args.setdefault.lower() in ['y', 'yes']
            if args.source.lower() in ['cb', 'clipboard']:
                local_profiles.inject_profile_from(source='cb', setdefault=default)
            elif args.source.lower() in ['env', 'environment']:
                local_profiles.inject_profile_from(source='cb', setdefault=default)
            else:
                raise ValueError('Unknown profile source')
            local_profiles.save()

        elif args.command in ('list', 'ls'):
            print(f'AWS profiles in {args.creds_location}')
            print(local_profiles.list())

        elif args.command in ('backup', 'bckp'):
            local_profiles.backup(args.dest)

        elif args.command in ('delete', 'del'):
            local_profiles.delete_profile(args.profile)
            local_profiles.save()

        elif args.command in ('setdefault', 'setdef'):
            local_profiles.setdefault(args.profile)
            local_profiles.save()

        elif args.command in ('show'):
            print(local_profiles.show(args.profile))

    except ProfileError as e:
        print(e.message)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
