import os
from typing import Optional
from urllib.parse import urlparse

from invoke import Context, task

from conjuring.grimoire import run_command, run_lines, run_with_fzf

AWS_CONFIG = "~/.aws/config"

LIST_AWS_PROFILES_COMMAND = rf"rg -o '\[profile[^\]]+' {AWS_CONFIG} | cut -d ' ' -f 2"

SHOULD_PREFIX = True


def list_aws_profiles(c: Context) -> list[str]:
    """List AWS profiles from the config file."""
    return run_lines(c, LIST_AWS_PROFILES_COMMAND)


def fzf_aws_profile(c, partial_name: Optional[str] = None) -> str:
    """Select an AWS profile from a partial profile name using fzf."""
    if not partial_name and (aws_profile := os.environ.get("AWS_PROFILE")):
        if aws_profile:
            print(f"Using env variable AWS_PROFILE (set to '{aws_profile}')")
            return aws_profile

    return run_with_fzf(c, LIST_AWS_PROFILES_COMMAND, query=partial_name)


def fzf_aws_account(c) -> str:
    """Select an AWS account from the config file."""
    return run_with_fzf(c, f"rg -o 'aws:iam::[^:]+' {AWS_CONFIG} | cut -d ':' -f 4 | sort -u")


def fzf_aws_region(c) -> str:
    """Select an AWS region from the config file."""
    return run_with_fzf(c, f"rg -o '^region.+' {AWS_CONFIG} | tr -d ' ' | cut -d'=' -f 2 | sort -u")


def run_aws_vault(c, *pieces, profile: Optional[str] = None):
    """Run AWS vault commands in a subshell, or open a subshell if no commands were provided."""
    run_command(c, "aws-vault exec", fzf_aws_profile(c, profile), "--", *pieces, pty=False)


def clean_aws_url(c, url: Optional[str] = None):
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
