# Changelog

## v0.2.1 (2023-05-20)

### Fix

- version number and project metadata

## v0.2.0 (2023-05-19)

### Fix

- read pyproject.toml with UTF-8 encoding

## 0.1.0 (2023-05-19)

### Feat

- **media**: transcribe using whisper
- **mkdocs**: tasks to work with documentation
- **k8s**: select multiple apps at once
- **k8s**: get pods, replica sets, config maps + validate score
- **mr**: add mr support, grep repos for a search text
- **pre-commit**: specify hooks without --hook
- **python**: test, watch, coverage, debug tools
- **git**: option to rebase master branch
- **python**: install/reinstall specific version
- **fzf**: accept options as arguments
- **aws**: list profiles
- allowed keys in ask_user_prompt()
- **onedrive**: display files with conflicts
- **media**: --force flag to delete files
- **python**: install a Poetry virtual environment
- **paperless**: delete failed duplicates
- remove hidden files and empty dirs
- **paperless**: move files instead of copying
- **paperless**: skip years and .DS_Store
- **paperless**: copy matched/unmatched files to ~/Downloads
- **paperless**: display orphan files, matched and unmatched
- **paperless**: show matched/unmatched files
- **paperless**: show thumbnails
- **paperless**: wrapper tasks for paperless
- ask user prompt
- **git**: prepare commit body with bullets
- **git**: task to tidy up repo
- **pre-commit**: install prepare-commit-msg
- **pre-commit**: uninstall all hooks
- slideshow command (first version)
- **git**: watch build then open PR or repo
- use AWS_PROFILE if it exists
- **git**: display changes since the chosen tag
- **pre-commit**: commit-msg hook is now optional
- **shell**: list and uninstall shell completions
- **shell**: click completion for Bash
- **git**: choose files with fzf, allow multiple subdirs
- download video URLs with youtube-dl
- **git**: merge the default branch of the repo
- **git**: options to rewrite commits with GPG and author
- **docker**: remove Docker containers and volumes
- **todo**: sort by type+description, option to show only FIXME
- list TODOs and FIXMEs in code
- **pre-commit**: accept comma-separated list of hooks to run
- **git**: extract files from a subtree + history + rebase/sign
- support PEP 660 hooks (editable packages)
- empty module for those who don't want the default tasks
- **AWS**: select account, region, ECR, aws-vault
- **pre-commit**: command to uninstall hooks
- **poetry**: choose pipx repo to inject with fzf
- display individual tasks conditionally
- visibility.py module with reusable functions
- prefix task names of a module
- display tasks conditionally
- merge any tasks.py with Conjuring tasks
- **pre-commit**: autoupdate one or all hooks
- use **CONJURING_PREFIX** to namespace tasks
- install a Poetry package as editable
- default module with all conjuring tasks
- fork tasks in a separate module
- optionally check empty dirs
- display dirs that should be emptied
- **duplicity**: choose a directory when restoring
- backup/restore with Duplicity
- **onedrive**: current year first, then others
- list dirs with \_Copy files
- unhide Picasa originals dir
- merge original dirs
- merge copy dirs
- move picture dirs by year
- backup files from the m3 hard drive
- list more dirs on OneDrive
- add warn param to run_command()
- option to choose journal on tags task
- remove empty files before OneDrive dir
- open the latest N OneDrive photo dirs
- function to run with fzf
- run_command function
- ignore modules with an env var
- **jrnl**: journal name
- more Git helpers
- query jrnl entries and tags
- configure a generic remote
- don't add home tasks twice
- auto update nitpick
- set SSH/HTTPS URL for remote
- pre-commit install and run
- fork remote and sync
- invoke tasks for home/current dirs
- change invoke collection name

### Fix

- **pre-commit**: don't stop on the first failed hook
- **deps**: update dependency requests to v2.30.0
- **deps**: update dependency invoke to v2.1.2
- **py**: check lock before installing, ignore comment on version
- **py**: don't fail if pyenv local is not set
- **git**: rebase with force push, from origin
- rename to py, use venv after pyenv set local
- **media**: use -f as short for --force
- return user input on ask_user_prompt()
- **paperless**: ignore all .DS_Store, fix --together
- **paperless**: don't display red files that can't be checked
- **git**: regex to parse Jira tickets
- **git**: body cleanup: Jira ticket and other stuff
- **duplicity**: max depth when running fd in OneDrive dirs
- **duplicity**: uppercase $HOME
- **git**: shorten names for commit body command
- **git**: prune after deleting branches, push by default
- **media**: open the last file (order was random before)
- **git**: prune remotes before updating the repo
- **git**: open PR in same branch that was watched
- improved Poetry detection (#1)
- **organize**: call invoke task and not the tool directly
- fd flags (hidden only)
- display Conjuring tasks only on home dir
- duplicated name in main collection
- check prefix before duplicated tasks
- dry-run mode on run_command()
- remote name defaults to username
- **duplicity**: restore on computer subdir
- check both Telegram dirs
- move Telegram dir under Samsung Gallery
- rename organize to categorize
- convert Path to str when joining
- show Telegram dir after current year dir
- don't limit jrnl entries by default
- jrnl improvements
- allow invoke\*.py files
- pty=False to remove colors

### Refactor

- constants for common directories
- prefer qualified imports (#3)
- preparing for multiple spell books
- gita_super is a better name
- a more appropriate name
- move tasks to their spell modules
- move color constants to conjuring
- create package structure
