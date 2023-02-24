from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import argparse
import fnmatch
import os
import shutil
import subprocess

"""
A simple tool for AWS profiles management
TODO: add .aws/config manipulation:
        raws config <profile> <option> <value>
"""

# Version info
NAME = 'raws'
VERSION = '0.9.5'
DESCRIPTION = 'A simple tool to manage your AWS credentials'


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

        backup: create a backup copy of current AWS_CREDS_FILE in the specified location
    """

    def __init__(self, creds_file: str = os.environ['AWS_CREDS_FILE']) -> None:
        self.creds_file = creds_file
        self.profiles = self._get_profiles_from_creds_file()

    def __contains__(self, item: str) -> bool:
        return item in self.profiles

    def __getitem__(self, item: str) -> AWSProfile:
        return self.profiles[item]

    def __len__(self) -> int:
        return len(self.profiles)

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

    def _get_profiles_from_creds_file(self) -> dict[str, AWSProfile]:

        if not os.path.exists(self.creds_file):
            with open(self.creds_file, 'w', encoding='utf-8'):
                return dict()

        existing_profiles: dict[str, AWSProfile] = {}
        current_profile: Optional[AWSProfile] = None

        with open(self.creds_file, 'r', encoding='utf-8') as f:
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

            if len(collected_lines) == 0:
                return dict()

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

    def setdefault(self, profile_name: str) -> str:
        if profile_name.lower() == 'default':
            raise ProfileError('Specified profile is already a default')
        try:
            new_default = self.profiles[profile_name].copy()
            new_default.profile_name = 'default'
            self.profiles['default'] = new_default
        except KeyError:
            raise ProfileError(f'Profile {profile_name} does not exist')
        return profile_name

    def inject_profile(self, profile: AWSProfile, setdefault: bool = False, strict: bool = False) -> None:
        if strict and profile.profile_name in self.profiles:
            raise ProfileError(f'Profile {profile} already exists and strict mode specified')
        else:
            self.profiles[profile.profile_name] = profile
        if setdefault:
            self.setdefault(profile.profile_name)

    def inject_profile_from(self, source: str,
                            setdefault: bool = False,
                            strict: bool = False,
                            rename_to: Optional[str] = None) -> str:
        if source.lower() in ('cb', 'clipboard'):
            new_profile = self._get_profile_from_clipboard()
        elif source.lower() in ('env', 'environment'):
            new_profile = self._get_profile_from_env()
        if rename_to:
            new_profile.profile_name = rename_to
        self.inject_profile(new_profile, setdefault=setdefault, strict=strict)
        return new_profile.profile_name

    def delete_profile(self, profile_name: str) -> str:
        try:
            del (self.profiles[profile_name])
        except KeyError:
            raise ProfileError(f'Profile {profile_name} does not exist')
        return profile_name

    def list(self) -> str:
        """List all profiles in the credentials file"""
        header = f'AWS profiles in {self.creds_file}\n'
        profs_list = '- ' + '\n- '.join(list(self.profiles.keys()))
        return f'{header}{profs_list}'

    def show(self, profile_name: str) -> str:
        """Show details of particular profile from the credentials file"""
        try:
            return self.profiles[profile_name].dump()
        except KeyError:
            raise ProfileError(f'Profile {profile_name} does not exist')

    def save(self, target_path: Optional[str] = None) -> None:
        if not target_path:
            target_path = self.creds_file
        with open(target_path, 'w', encoding='utf-8') as f:
            for p in self.profiles.values():
                f.writelines(p.dump())
                f.write('\n')
            f.write('\n')

    def backup(self, target_path: Optional[str] = None) -> str:
        if not target_path:
            dt = datetime.now().strftime('%Y-%m-%d-%H%M%S')
            target_path = f'{self.creds_file}-{dt}.bkp'
        self.save(target_path=target_path)
        return target_path

    def restore(self, latest: bool = True, backup_path: Optional[str] = None) -> str:
        """
        Restore the latest backup or a backup from a specific file
        Note: latest will only work correctly if the backup is in the same
              folder your AWS_CREDS_FILE is and the file name was generated by
              the self.beckup() method
        TODO: add backup validation
        """
        if latest:
            creds_dir, creds_fname = os.path.split(self.creds_file)
            pattern = fr'{creds_fname}*.bkp'
            found_backups: list[str] = []
            for file in os.listdir(creds_dir):
                if fnmatch.fnmatch(file, pattern) and os.path.isfile(os.path.join(creds_dir, file)):
                    found_backups.append(file)
            fname = sorted(found_backups, reverse=True)[0]
            backup_file = os.path.join(creds_dir, fname)
        elif backup_path:
            backup_file = backup_path
        else:
            raise ValueError('Neither --latest option, nor backup location specified')
        shutil.copy(backup_file, self.creds_file)
        return backup_file

    def rename(self, from_: str, to_: str) -> str:
        if from_ != to_:
            try:
                tmp_profile = self.profiles[from_]
                tmp_profile.profile_name = to_
                self.inject_profile(tmp_profile, strict=True)
                self.delete_profile(from_)
            except KeyError:
                raise ProfileError(f'Profile {from_} does not exist')
            return f'{from_} -> {to_}'
        else:
            raise ProfileError('Same name provided, nothing to rename')

    def __repr__(self) -> str:
        return self.list()


def main() -> int:
    # Create the parser
    parser = argparse.ArgumentParser(
        description=DESCRIPTION)
    parser.add_argument('--creds_file', type=str,
                        required=False, default=os.environ['AWS_CREDS_FILE'],
                        help='Override credentials file location')

    # Add the subcommands
    subparsers = parser.add_subparsers(dest='command')

    # Add the "add" subcommand
    add_parser = subparsers.add_parser('add', help='Add new profile')
    add_parser.add_argument(
        'source', type=str, help='Where to look for the new profile (cb = clipboard)')
    add_parser.add_argument('--setdefault', action='store_true',
                            help='Save the added profile as default')
    add_parser.add_argument('--rename_to', type=str, default=None,
                            help='Rename new profile')

    # Add "list" command
    list_parser = subparsers.add_parser(  # noqa: F841
        'list', aliases=['ls',], help='Show existing profiles')

    # Add "backup" command
    backup_parser = subparsers.add_parser(
        'backup', aliases=['bckp'], help='Backup existing profiles')
    backup_parser.add_argument('--dest', type=str, default=None)

    # Add "restore" command
    restore_parser = subparsers.add_parser(
        'restore', help='Restore the latest backup of credentials file')
    restore_parser.add_argument(
        '--latest', action='store_true', help='Whether to restore the latest backup')
    restore_parser.add_argument('--dest', type=str, default=None)

    # Add "delete" command
    delete_parser = subparsers.add_parser(
        'delete', aliases=['del'], help='Backup existing profiles')
    delete_parser.add_argument('profile', type=str,
                               help='Delete profile by name')

    # Add "setdefault" command
    setdefault_parser = subparsers.add_parser(
        'setdefault', aliases=['setdef'], help='Set given profile as default')
    setdefault_parser.add_argument('profile', type=str,
                                   help='Profile name to make default')

    # Add "show" command
    show_parser = subparsers.add_parser(
        'show', help='Show full profile info')
    show_parser.add_argument('profile', type=str,
                             help='Profile name to show')

    # Add "showfile" command
    showfile_parser = subparsers.add_parser(  # noqa: F841
        'showfile', aliases=['file',], help='Show current credentials file')

    # Add "rename" command
    rename_parser = subparsers.add_parser('rename', help='rename a profile')
    rename_parser.add_argument('from_', type=str, help='Source profile name')
    rename_parser.add_argument('to_', type=str, help='Target profile name')

    # Add "version" command
    version_parser = subparsers.add_parser('version', aliases=['ver', 'v'],   # noqa: F841
                                           help='Show current version and exit')

    # Parse the arguments and call the appropriate methods
    args = parser.parse_args()
    local_profiles = AWSCredentials(args.creds_file)
    try:
        if args.command == 'add':
            try:
                sources_map = {'cb': 'cb', 'clipboard': 'cb', 'env': 'env', 'environment': 'env'}
                source = sources_map[args.source.lower()]
                new_profile = local_profiles.inject_profile_from(
                    source=source, setdefault=args.setdefault, rename_to=args.rename_to)
            except KeyError:
                raise ProfileError('Unknown profile source')
            local_profiles.save()
            print(f'Added new profile: {new_profile}')

        elif args.command in ('list', 'ls'):
            print(local_profiles.list())

        elif args.command in ('backup', 'bckp'):
            backup_path = local_profiles.backup(args.dest)
            print(f'AWS profiles backed up to: {backup_path}')

        elif args.command in ('restore'):  # not implemented
            restored_from = local_profiles.restore(latest=args.latest, backup_path=args.dest)
            print(f'AWS profiles restored from: {restored_from}')

        elif args.command in ('delete', 'del'):
            deleted_profile = local_profiles.delete_profile(args.profile)
            local_profiles.save()
            print(f'Deleted profile: {deleted_profile}')

        elif args.command in ('setdefault', 'setdef'):
            default_prof = local_profiles.setdefault(args.profile)
            local_profiles.save()
            print(f'{default_prof} is set as default')

        elif args.command in ('show'):
            print(local_profiles.show(args.profile))

        elif args.command in ('showfile', 'file'):
            print(local_profiles.creds_file)

        elif args.command in ('rename'):
            result = local_profiles.rename(args.from_, args.to_)
            local_profiles.save()
            print(f'Renamed: {result}')

        elif args.command in ('version', 'ver', 'v'):
            print(f'{NAME}, version: {VERSION}')

    except ProfileError as e:
        print(e.message)
        return 1

    return 0


# TODO: validate_profile() method to check whether the passed text is valid AWS profile
# TODO: implement __setattr__()
if __name__ == '__main__':
    raise SystemExit(main())
