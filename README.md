# RAWS

RAWS is a simple AWS Profile Manager with a command-line interface that helps you easily manipulate AWS profiles on your local machine.
RAWS will lookup location of your AWS credentials file through environment variable `AWS_CREDS_FILE`. If the variable is not set, it will default to '~/.aws/credentials'. You can also override the file location by specifing --creds_file argument.

## Installation

You can install the raws by cloning the repository and running pip install:
`cd raws && pip install .`
TODO: publish on PyPi

This will display a list of available commands:
`raws -h`

### Available commands

* `add`: Add a new AWS profile.
* `delete`: Delete an existing AWS profile.
* `list`: List all available AWS profiles.
* `show`: Show detailed information on specified profile
* `setdefault`: Make specified profile default
* `rename`: Rename a profile
* `backup`: backup credentials file (optionally provide location)
* `restore`: restore from a location or from latest backup

## Examples

Here are a few examples of how to use the AWS Profile Manager:

Show all available profiles:
`raws list or raws ls`

Show details of `personal` profile:
`raws show personal`

Add a new profile from clipboard (copied from AWS SSO page):
`raws add cb --setdefault --rename_to=personal`

Rename profile `busieness_13123` to `work`:
`raws rename busieness_13123 work`

Set `personal` profile as default:
`raws setdef personal`

Backup current credentials file:
`raws backup`

Restore from the latest backup:
`raws restore --latest`

List all profiles in a backup file located in /home/user/backup/creds.bkp
`raws --creds_file=/home/user/backup/creds.bkp ls`

## Contributing

If you find a bug or have an idea for a new feature, feel free to create an issue or submit a pull request.

## License

RAWS is released under the MIT License.





