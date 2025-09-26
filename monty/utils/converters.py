from __future__ import annotations

import re
import typing as t
from datetime import timedelta
from ssl import CertificateError

import arrow
import disnake
from aiohttp import ClientConnectorError
from disnake.ext import commands

from monty import exts
from monty.bot import Monty
from monty.log import get_logger
from monty.utils import helpers
from monty.utils.extensions import EXTENSIONS, unqualify


log = get_logger(__name__)

DISCORD_EPOCH_DT = disnake.utils.snowflake_time(0)
RE_USER_MENTION = re.compile(r"<@!?([0-9]+)>$")

AnyContext = t.Union[disnake.ApplicationCommandInteraction, commands.Context[Monty]]

TIMEDELTA_REGEX = re.compile(
    r"^"
    r"((?P<years>-?\d+)(?:Y|y|[Yy]ears?))?"
    r"((?P<months>-?\d+)(?:M|[Mm]onths?))?"
    r"((?P<weeks>-?\d+)(?:W|w|[Ww]eeks?))?"
    r"((?P<days>-?\d+)(?:D|d|[Dd]ays?))?"
    r"((?P<hours>-?\d+)(?:H|h|[Hh]ours?))?"
    r"((?P<minutes>-?\d+)(?:m|[Mm]inutes?))?"
    r"((?P<seconds>-?\d+)(?:S|s|[Ss]econds?))?"
    r"$",
)


def str_timedelta_from_now(human: str, /) -> t.Optional[timedelta]:
    """Convert a string to a timedelta relative to the current time."""
    match = TIMEDELTA_REGEX.fullmatch(human)
    if not match:
        return None

    parts = {k: int(v) for k, v in match.groupdict().items() if v}

    # to support years and months we have to make some assumptions about the current time
    # for that we can use arrow which does this for us.
    if "years" in parts or "months" in parts:
        now = arrow.utcnow()
        then = now.shift(**parts)
        return then - now

    return timedelta(**parts)


class Extension(commands.Converter):
    """
    Fully qualify the name of an extension and ensure it exists.

    The * and ** values bypass this when used with the reload command.
    """

    async def convert(self, ctx: commands.Context, argument: str) -> str:
        """Fully qualify the name of an extension and ensure it exists."""
        # Special values to reload all extensions
        if argument == "*" or argument == "**":
            return argument

        argument = argument.lower()

        if argument in EXTENSIONS:
            return argument
        elif (qualified_arg := f"{exts.__name__}.{argument}") in EXTENSIONS:
            return qualified_arg

        matches = []
        for ext in EXTENSIONS:
            if argument == unqualify(ext):
                matches.append(ext)

        if len(matches) > 1:
            matches.sort()
            names = "\n".join(matches)
            raise commands.BadArgument(
                f":x: `{argument}` is an ambiguous extension name. "
                f"Please use one of the following fully-qualified names.```\n{names}```"
            )
        elif matches:
            return matches[0]
        else:
            raise commands.BadArgument(f":x: Could not find the extension `{argument}`.")


class ValidURL(commands.Converter):
    """
    Represents a valid webpage URL.

    This converter checks whether the given URL can be reached and requesting it returns a status
    code of 200. If not, `commands.BadArgument` is raised.

    Otherwise, it simply passes through the given URL.
    """

    @staticmethod
    async def convert(ctx: commands.Context, url: str) -> str:
        """This converter checks whether the given URL can be reached with a status code of 200."""
        try:
            async with ctx.bot.http_session.get(url, ssl=helpers.ssl_create_default_context()) as resp:
                if resp.status != 200:
                    raise commands.BadArgument(f"HTTP GET on `{url}` returned status `{resp.status}`, expected 200")
        except CertificateError as e:
            if url.startswith("https"):
                raise commands.BadArgument(f"Got a `CertificateError` for URL `{url}`. Does it support HTTPS?") from e
            raise commands.BadArgument(f"Got a `CertificateError` for URL `{url}`.") from e
        except ValueError as e:
            raise commands.BadArgument(f"`{url}` doesn't look like a valid hostname to me.") from e
        except ClientConnectorError as e:
            raise commands.BadArgument(f"Cannot connect to host with URL `{url}`.") from e
        return url


SourceType = t.Union[
    commands.Command,
    commands.Cog,
    commands.InvokableSlashCommand,
    commands.InvokableMessageCommand,
    commands.InvokableUserCommand,
    commands.SubCommand,
    commands.SubCommandGroup,
]


class SourceConverter(commands.Converter):
    """Convert an argument into a command or cog."""

    @staticmethod
    async def convert(ctx: AnyContext, argument: str) -> SourceType:
        """Convert argument into source object."""
        # todo: add support for specifying the type
        cog = ctx.bot.get_cog(argument)
        if cog:
            return cog

        cmd = ctx.bot.get_slash_command(argument)
        if cmd:
            if not cmd.guild_ids:
                return cmd
            elif ctx.guild and ctx.guild.id in cmd.guild_ids:
                return cmd

        cmd = ctx.bot.get_command(argument)
        if cmd:
            return cmd

        # attempt to get the context menu command

        cmd = ctx.bot.get_message_command(argument)
        if cmd:
            if not cmd.guild_ids:
                return cmd
            elif ctx.guild and ctx.guild.id in cmd.guild_ids:
                return cmd

        cmd = ctx.bot.get_user_command(argument)
        if cmd:
            if not cmd.guild_ids:
                return cmd
            elif ctx.guild and ctx.guild.id in cmd.guild_ids:
                return cmd

        raise commands.BadArgument(f"Unable to convert `{argument}` to valid command, application command, or Cog.")
