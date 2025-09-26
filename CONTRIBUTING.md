---
description: Contributing your changes to qtbotbase
---

# Contributing

Thank you for your interest in contributing to qtbotbase!

This document explains the contributing process in full. If your question isn't
answered here, please
[open an issue](https://github.com/onerandomusername/qtbotbase/issues)

## Issue Tracker

### Reporting a bug

If you find a bug, please report it to
[the issue tracker](https://github.com/onerandomusername/qtbotbase/issues/new/choose)
with the details of what command you ran, whether or not the bot is in the
server or if you have the bot installed to your user, and the guild ID. This
will help us find the bug so we can fix it.

### Requesting a new feature

If you're looking to submit a new feature, please create an issue on
[the issue tracker](https://github.com/onerandomusername/qtbotbase/issues/new/choose)
first, so the details can be discussed before submitting. If you have an idea
for a new feature, but don't want to implement it yourself, PLEASE also create
an issue! We love suggestions and new ideas, and want to ensure we're adding
features that the community would actually use! Thank you!

## Submitting a fix

### Overview

The general workflow can be summarized as follows:

1. Fork + clone the repository.
1. Initialize the development environment:
    `uv sync --all-groups && uv run pre-commit install`.
1. Create a new branch.
1. Commit your changes, update documentation if required.
1. Push the branch to your fork, and
    [submit a pull request!](https://github.com/onerandomusername/qtbotbase/pull/new)

### But wait!

Before contributing, **please**
[make an issue](https://github.com/onerandomusername/qtbotbase/issues/new/choose)
for the specific fix or feature you are attempting to work on: we don't want you
to work on a feature that someone else is already working on, so please check
before you do! Small fixes, such as typos or logic bugs can be fixed without an
issue, but this is best done on a case-by-case basis. If you're wondering, you
can join the [Discord Server](https://discord.gg/mPscM4FjWB) to speak to the
developer at any time.

## Setting up a developer environment

### Requirements

- git
- docker
    - docker compose
- python 3.10
- uv

Additionally, an SQL database is required to develop qtbotbase, but this supports sqlite and installs the necessary drivers automatically. Sure, you can use PostgreSQL, but why would you want to?

### Clone the repo

First step to getting started is to clone the repository:

```sh
git clone https://github.com/onerandomusername/qtbotbase
cd qtbotbase
```

Next, create a file named `.env` within the cloned repository. This will be used
later regardless of how you run Monty.

A minimum viable contents (if using Docker) are as follows:

```sh
# contents of .env
BOT_TOKEN=...

# to change the default prefix from `-`
PREFIX=...

# optional, used to increase GitHub ratelimits from
# 60 to 5000/h and enable the graphql API
GITHUB_TOKEN=...
```

### Installing dependencies

TLDR:

```sh
uv sync --all-groups
uv run prek install
```

If you don't already have uv installed, check the
[uv documentation](https://docs.astral.sh/uv/), or use a tool like pipx or
uvx.

Make sure you install prek, as it will lint every commit before its
created, limiting the amount of fixes needing to be made in the review process.

### Create a Discord Bot

Go to
[the Discord Developer Portal](https://discord.com/developers/applications) and
click on the "Create Application" button.

Follow the steps through and save the developer token. It needs to go in the
`.env` created earlier.

You'll also need to connect this bot to at least one server you have access to.

> [!WARNING]
> qtbotbase requires the message content intent and **won't start** if that
> intent is disabled. Be sure to enable it when configuring the bot.

### Running the bot

```sh
# within .env
BOT_TOKEN=... # token from earlier
# to run database migrations/set up the bot for the first time
DB_RUN_MIGRATIONS=true
```
