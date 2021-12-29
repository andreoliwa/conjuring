from invoke import task
from urllib.parse import urlparse

from conjuring.grimoire import run_with_fzf, run_command

SHOULD_PREFIX = True


def fzf_aws_profile(c, partial_name: str = None) -> str:
    """Select an AWS profile from a partial profile name using fzf."""
    return run_with_fzf(
        c,
        r"rg -o '\[profile[^\]]+' ~/.aws/config | cut -d ' ' -f 2",
        query=partial_name,
    )


def fzf_aws_account(c) -> str:
    """Select an AWS account from the config file."""
    return run_with_fzf(c, "rg -o 'aws:iam::[^:]+' ~/.aws/config | cut -d ':' -f 4 | sort -u")


def fzf_aws_region(c) -> str:
    """Select an AWS region from the config file."""
    return run_with_fzf(c, "rg -o '^region.+' ~/.aws/config | tr -d ' ' | cut -d'=' -f 2 | sort -u")


def run_aws_vault(c, *pieces, profile: str = None):
    """Run AWS vault commands in a subshell, or open a subshell if no commands were provided."""
    run_command(c, "aws-vault exec", fzf_aws_profile(c, profile), "--", *pieces, pty=False)


def clean_aws_url(c, url: str = None):
    if not url:
        account = fzf_aws_account(c)
        region = fzf_aws_region(c)
        return f"{account}.dkr.ecr.{region}.amazonaws.com"
    return urlparse(url).netloc


@task
def ecr_login(c, url=""):
    """Log in to AWS ECR.

    Using Amazon ECR with the AWS CLI - Amazon ECR:
    https://docs.aws.amazon.com/AmazonECR/latest/userguide/getting-started-cli.html#cli-authenticate-registry
    """
    profile = fzf_aws_profile(c)
    url = clean_aws_url(c, url)
    run_command(
        c,
        "aws ecr get-login-password --profile",
        profile,
        "| docker login --username AWS --password-stdin",
        url,
    )
