# Changelog

## [0.13.0](https://github.com/andreoliwa/conjuring/compare/v0.12.0...v0.13.0) (2026-06-04)


### Features

* **conjuring:** re-export Binary, ConjuringTask, task from package __init__ ([1357268](https://github.com/andreoliwa/conjuring/commit/135726844e8416114bfec3c5da17838106ac6246))
* **git:** add oneline flag to log_since task ([e1619f0](https://github.com/andreoliwa/conjuring/commit/e1619f0573059a0d6148a4a3bf8bf2677d257219))
* **git:** add requires check and rename dir_ to subdir in git.import-repos ([eb3db20](https://github.com/andreoliwa/conjuring/commit/eb3db2002d670f8f3b6e9539197f510a40ff4aea))
* **git:** add two-path next steps to git.extract-subtree ([a49de2d](https://github.com/andreoliwa/conjuring/commit/a49de2deef51e98abd75e741cd80a69c6b5f5fcd))
* **grimoire:** add Binary enum for required external CLI binaries ([c1b3f86](https://github.com/andreoliwa/conjuring/commit/c1b3f86be06cc7667818af17df6dea509497fc1f))
* **grimoire:** add ConjuringTask subclass and task wrapper with requires checking ([d430c50](https://github.com/andreoliwa/conjuring/commit/d430c50689739760b8ca1ffb1b8f7bf7df26d476))
* **grimoire:** add default parameter to ask_yes_no ([d5f6269](https://github.com/andreoliwa/conjuring/commit/d5f62699cba70a163e799610351dd01d1a672149))
* **grimoire:** add GIT_FILTER_REPO to Binary enum ([2baf806](https://github.com/andreoliwa/conjuring/commit/2baf8062834699f521913deeef49ef1486165269))


### Bug Fixes

* **deps:** declare click as explicit dependency ([61833ed](https://github.com/andreoliwa/conjuring/commit/61833edad39cbb91549d90d371279ea38fb78e18))
* **git:** replace git-extras default branch detection with origin/main check ([8ac23fe](https://github.com/andreoliwa/conjuring/commit/8ac23fecf547e02ab596e32dd446ee5a24222e00))
* **git:** use run_command(interactive=True) in git.rewrite ([4657fd3](https://github.com/andreoliwa/conjuring/commit/4657fd384e450aab57bd2a6cee5b02a17d83558b))
* **media:** convert HEIC via sips, fix copy on exFAT, return Path from shrink_and_copy ([5d259d9](https://github.com/andreoliwa/conjuring/commit/5d259d94bcbe6ca8317c76551e37c31593e2c871))


### Documentation

* create LICENSE ([032ab0a](https://github.com/andreoliwa/conjuring/commit/032ab0a32ff374ba4fb8ac8a8ab880a94a3e8da8))

## [0.12.0](https://github.com/andreoliwa/conjuring/compare/v0.11.0...v0.12.0) (2026-05-24)

### Features

- **duplicity:** add --allow-source-mismatch flag to backup task ([788d052](https://github.com/andreoliwa/conjuring/commit/788d052a7100e5d52fb7772ec53084aac107175a))
- **duplicity:** display --archived and --planned files ([8c78d8c](https://github.com/andreoliwa/conjuring/commit/8c78d8cde784c10f2f094f6e70e3f563af64205a))
- **duplicity:** generate work-dir include patterns dynamically from repo_root ([d1354be](https://github.com/andreoliwa/conjuring/commit/d1354bed04b3ec2d707a44f8c8d7df8e32f147bf))
- **duplicity:** rename ls-files to ls, add --host param ([a13bfb6](https://github.com/andreoliwa/conjuring/commit/a13bfb6dfb35a17485a6e192d4f1c91bd12c8cfe))
- **shell:** add hostname-set task with auto-generated opaque name ([2e8ab4f](https://github.com/andreoliwa/conjuring/commit/2e8ab4f7c36f60637024aef1e8d6a00404db72dd))

### Bug Fixes

- **grimoire:** get_hostname strips full domain, not just .local ([69af1e4](https://github.com/andreoliwa/conjuring/commit/69af1e4561571bc3479df7c9fb98c4eccd7845bd))
- **grimoire:** use shell=True in run_command interactive mode to support pipes ([40f7e16](https://github.com/andreoliwa/conjuring/commit/40f7e161144baee19ef67669db5bb88214d3829b))

## 0.11.0 (2026-05-09)

**Full Changelog**: https://github.com/andreoliwa/conjuring/compare/v0.10.0...v0.11.0

## 0.10.0 (2026-05-09)

## What's Changed

- chore(deps): update pre-commit hook commitizen-tools/commitizen to v4.15.0 by @renovate[bot] in https://github.com/andreoliwa/conjuring/pull/68
- chore(deps): update actions/checkout action to v6 by @renovate[bot] in https://github.com/andreoliwa/conjuring/pull/69
- ci(pre-commit): autoupdate by @pre-commit-ci[bot] in https://github.com/andreoliwa/conjuring/pull/67

**Full Changelog**: https://github.com/andreoliwa/conjuring/compare/v0.9.0...v0.10.0

## 0.9.0 (2026-05-02)

## What's Changed

- build(deps): bump urllib3 from 2.3.0 to 2.6.3 by @dependabot[bot] in https://github.com/andreoliwa/conjuring/pull/59
- build(deps): bump pygments from 2.19.1 to 2.20.0 by @dependabot[bot] in https://github.com/andreoliwa/conjuring/pull/62
- build(deps): bump requests from 2.32.3 to 2.32.5 by @dependabot[bot] in https://github.com/andreoliwa/conjuring/pull/61
- [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci[bot] in https://github.com/andreoliwa/conjuring/pull/54

**Full Changelog**: https://github.com/andreoliwa/conjuring/compare/v0.8.0...v0.9.0

## 0.8.0 (2026-05-02)

## What's Changed

- [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci[bot] in <https://github.com/andreoliwa/conjuring/pull/12>
- chore(deps): update pre-commit hook igorshubovych/markdownlint-cli to v0.35.0 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/14>
- chore(deps): update pre-commit hook pre-commit/mirrors-mypy to v1.4.0 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/15>
- fix(deps): update dependency ruamel-yaml to v0.17.32 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/16>
- chore(deps): update pre-commit hook pre-commit/mirrors-prettier to v3.0.1 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/17>
- build(deps): bump urllib3 from 1.26.14 to 1.26.17 by @dependabot[bot] in <https://github.com/andreoliwa/conjuring/pull/18>
- build(deps): bump certifi from 2022.12.7 to 2023.7.22 by @dependabot[bot] in <https://github.com/andreoliwa/conjuring/pull/19>
- chore(deps): update dependency pytest to v7.4.4 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/21>
- chore(deps): update dependency ipython to v8.23.0 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/22>
- ci: upgrade peaceiris/actions-gh-pages@v4 by @andreoliwa in <https://github.com/andreoliwa/conjuring/pull/24>
- [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci[bot] in <https://github.com/andreoliwa/conjuring/pull/13>
- build(deps): bump idna from 3.4 to 3.7 by @dependabot[bot] in <https://github.com/andreoliwa/conjuring/pull/23>
- chore(deps): update dependency pytest-mock to v3.14.0 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/29>
- fix(deps): update dependency ruamel-yaml to v0.18.6 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/26>
- fix(deps): update dependency tomlkit to v0.12.4 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/27>
- chore(deps): update dependency pytest to v8.1.1 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/28>
- chore(deps): update pre-commit hook astral-sh/ruff-pre-commit to v0.6.4 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/35>
- fix(deps): update dependency requests to v2.32.2 [security] by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/36>
- fix(deps): update dependency tqdm to v4.67.1 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/37>
- chore(deps): update softprops/action-gh-release action to v2 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/45>
- chore(deps): update actions/setup-python action to v6 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/49>
- chore(deps): update actions/checkout action to v5 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/47>
- feat(git): display dirty repos on a rich table by @andreoliwa in <https://github.com/andreoliwa/conjuring/pull/55>
- chore(deps): update pre-commit hook psf/black-pre-commit-mirror to v25.12.0 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/56>
- chore(deps): update pre-commit hook pre-commit/mirrors-mypy to v1.19.1 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/57>
- chore(deps): update pre-commit hook astral-sh/ruff-pre-commit to v0.15.6 by @renovate[bot] in <https://github.com/andreoliwa/conjuring/pull/60>

## New Contributors

- @pre-commit-ci[bot] made their first contribution in <https://github.com/andreoliwa/conjuring/pull/12>

**Full Changelog**: <https://github.com/andreoliwa/conjuring/compare/v0.7.0...v0.8.0>
