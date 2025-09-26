import asyncio
import collections
import functools
import socket
from types import SimpleNamespace
from typing import Any, Optional, Union

import aiohttp
import arrow
import disnake
from disnake.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from monty import constants
from monty.log import get_logger
from monty.utils import scheduling
from monty.utils.extensions import EXTENSIONS, walk_extensions


log = get_logger(__name__)

try:
    import dotenv
except ModuleNotFoundError:
    TEST_GUILDS = None
else:
    TEST_GUILDS = dotenv.get_key(".env", "TEST_GUILDS")
    if TEST_GUILDS:
        TEST_GUILDS = [int(x.strip()) for x in TEST_GUILDS.split(",")]
        log.info("TEST_GUILDS FOUND")


__all__ = ("Monty",)


class Monty(commands.Bot):
    """
    Base bot instance.

    While in debug mode, the asset upload methods (avatar, banner, ...) will not
    perform the upload, and will instead only log the passed download urls and pretend
    that the upload was successful. See the `mock_in_debug` decorator for further details.
    """

    name = constants.Client.name

    def __init__(self, proxy: str = None, **kwargs) -> None:
        if TEST_GUILDS:
            kwargs["test_guilds"] = TEST_GUILDS
            log.warning("registering as test_guilds")
        super().__init__(**kwargs)

        self.create_http_session(proxy=proxy)

        self.db_engine = engine = create_async_engine(constants.Database.postgres_bind)
        self.db_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        self.socket_events = collections.Counter()
        self.start_time: arrow.Arrow
        self.command_prefix: str
        self.invite_permissions: disnake.Permissions = constants.Client.default_invite_permissions
        scheduling.create_task(self.get_self_invite_perms())

        self._autoreload_task: asyncio.Task | None = None
        self._autoreload_log_channel: disnake.abc.Messageable | None = None

    @property
    def db(self) -> async_sessionmaker[AsyncSession]:
        """Alias of `bot.db_session`."""
        return self.db_session

    def create_http_session(self, proxy: str = None) -> None:
        """Create the aiohttp session and set the trace logger, if desired."""
        trace_configs = []

        aiohttp_log = get_logger(__package__ + ".http")

        async def on_request_end(
            session: aiohttp.ClientSession,
            ctx: SimpleNamespace,
            end: aiohttp.TraceRequestEndParams,
        ) -> None:
            """Log all aiohttp requests on request end."""
            resp = end.response
            aiohttp_log.info(
                "[{status!s} {reason!s}] {method!s} {url!s} ({content_type!s})".format(
                    status=resp.status,
                    reason=resp.reason,
                    method=end.method.upper(),
                    url=end.url,
                    content_type=resp.content_type,
                )
            )

        trace_config = aiohttp.TraceConfig()
        trace_config.on_request_end.append(on_request_end)
        trace_configs.append(trace_config)

        self.http_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                resolver=aiohttp.AsyncResolver(),
                family=socket.AF_INET,
                verify_ssl=not bool(proxy and proxy.startswith("http://")),
            ),
            trace_configs=trace_configs,
        )
        if proxy:
            self.http_session._request = functools.partial(self.http_session._request, proxy=proxy)

    async def get_self_invite_perms(self) -> disnake.Permissions:
        """Sets the internal invite_permissions and fetches them."""
        await self.wait_until_first_connect()
        app_info = await self.application_info()
        if app_info.install_params:
            self.invite_permissions = app_info.install_params.permissions
        else:
            self.invite_permissions = constants.Client.default_invite_permissions
        return self.invite_permissions

    async def get_prefix(self, message: disnake.Message) -> Optional[Union[list[str], str]]:
        """Get the bot prefix."""
        prefixes = commands.when_mentioned(self, message)
        prefixes.insert(0, self.command_prefix)

        return prefixes

    async def login(self, token: str) -> None:
        """Login to Discord and set the bot's start time."""
        self.start_time = arrow.utcnow()
        return await super().login(token)

    async def close(self) -> None:
        """Close sessions when bot is shutting down."""
        await super().close()

        if self.http_session:
            await self.http_session.close()
        if self.db_engine:
            await self.db_engine.dispose()

        await asyncio.sleep(0.6)

    def load_extensions(self) -> None:
        """Load all extensions as released by walk_extensions()."""
        if constants.Client.extensions:
            log.warning("Not loading all extensions as per environment settings.")
        EXTENSIONS.update(walk_extensions())
        for ext, ext_metadata in walk_extensions():
            if not constants.Client.extensions:
                self.load_extension(ext)
                continue

            if ext_metadata.core or ext in constants.Client.extensions:
                self.load_extension(ext)
                continue
            log.debug(f"SKIPPING loading {ext} as per environment variables.")
        log.info("Completed loading extensions.")

    def add_cog(self, cog: commands.Cog, **kwargs: Any) -> None:
        """
        Delegate to super to register `cog`.

        This only serves to make the info log, so that extensions don't have to.
        """
        super().add_cog(cog, **kwargs)
        log.info(f"Cog loaded: {cog.qualified_name}")
        self.dispatch("cog_load", cog)

    def remove_cog(self, name: str) -> Optional[commands.Cog]:
        """Remove the cog from the bot and dispatch a cog_remove event."""
        cog = super().remove_cog(name)
        if cog is None:
            return None
        self.dispatch("cog_remove", cog)
        return cog

    def add_command(self, command: commands.Command) -> None:
        """Add `command` as normal and then add its root aliases to the bot."""
        super().add_command(command)
        self.dispatch("command_add", command)

    def remove_command(self, name: str) -> Optional[commands.Command]:
        """
        Remove a command/alias as normal and then remove its root aliases from the bot.

        This also dispatches the command_remove event.

        Individual root aliases cannot be removed by this function.
        To remove them, either remove the entire command or manually edit `bot.all_commands`.
        """
        command = super().remove_command(name)
        if command is None:
            # Even if it's a root alias, there's no way to get the Bot instance to remove the alias.
            return

        self.dispatch("command_remove", command)
        return command

    def add_slash_command(self, slash_command: commands.InvokableSlashCommand) -> None:
        """Add the slash command to the bot and dispatch a slash_command_add event."""
        super().add_slash_command(slash_command)
        self.dispatch("slash_command_add", slash_command)

    def remove_slash_command(self, name: str) -> Optional[commands.InvokableSlashCommand]:
        """Remove the slash command from the bot and dispatch a slash_command_remove event."""
        slash_command = super().remove_slash_command(name)
        if slash_command is None:
            return None
        self.dispatch("slash_command_remove", slash_command)
        return slash_command

    async def on_command_error(self, context: commands.Context, exception: disnake.DiscordException) -> None:
        """Check command errors for UserInputError and reset the cooldown if thrown."""
        if isinstance(exception, commands.UserInputError) and context.command:
            context.command.reset_cooldown(context)
        else:
            await super().on_command_error(context, exception)  # type:ignore
