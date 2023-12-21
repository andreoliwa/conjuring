"""AWS: ECR login."""
from __future__ import annotations

import os
from urllib.parse import urlparse

import typer
from invoke import Context, Result, task

from conjuring.constants import AWS_CONFIG
from conjuring.grimoire import run_command, run_lines, run_with_fzf

LIST_AWS_PROFILES_COMMAND = rf"rg -o '^\[profile[^\]]+' {AWS_CONFIG} | cut -d ' ' -f 2"

SHOULD_PREFIX = True


def list_aws_profiles(c: Context) -> list[str]:
    """List AWS profiles from the config file."""
    return run_lines(c, LIST_AWS_PROFILES_COMMAND)


def fzf_aws_profile(c: Context, partial_name: str | None = None) -> str:
    """Select an AWS profile from a partial profile name using fzf."""
    if not partial_name and (aws_profile := os.environ.get("AWS_PROFILE")) and aws_profile:
        typer.echo(f"Using env variable AWS_PROFILE (set to '{aws_profile}')")
        return aws_profile

    return run_with_fzf(c, LIST_AWS_PROFILES_COMMAND, query=partial_name or "")


def fzf_aws_account(c: Context) -> str:
    """Select an AWS account from the config file."""
    return run_with_fzf(c, f"rg -o 'aws:iam::[^:]+' {AWS_CONFIG} | cut -d ':' -f 4 | sort -u")


def fzf_aws_region(c: Context) -> str:
    """Select an AWS region from the config file."""
    return run_with_fzf(c, f"rg -o '^region.+' {AWS_CONFIG} | tr -d ' ' | cut -d'=' -f 2 | sort -u")


def run_aws_vault(c: Context, *pieces: str, profile: str | None = None) -> Result:
    """Run AWS vault commands in a subshell, or open a subshell if no commands were provided."""
    return run_command(c, "aws-vault exec", fzf_aws_profile(c, profile), "--", *pieces, pty=False)


def clean_ecr_url(c: Context, url: str | None = None) -> str:
    """Clean an AWS ECR URL."""
    if not url:
        account = fzf_aws_account(c)
        region = fzf_aws_region(c)
        return f"{account}.dkr.ecr.{region}.amazonaws.com"
    return urlparse(url).netloc


@task
def ecr_login(c: Context, url: str = "") -> None:
    """Log in to AWS ECR.

    [Using Amazon ECR with the AWS CLI - Amazon ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/getting-started-cli.html#cli-authenticate-registry)
    """
    profile = fzf_aws_profile(c)
    url = clean_ecr_url(c, url)
    run_command(
        c,
        "aws ecr get-login-password --profile",
        profile,
        "| docker login --username AWS --password-stdin",
        url,
    )
