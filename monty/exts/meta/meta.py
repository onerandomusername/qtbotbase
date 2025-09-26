import importlib.metadata
import random
from datetime import datetime, timedelta
from typing import Optional

import disnake
import psutil
from disnake.ext import commands

from monty.bot import Monty
from monty.constants import Client, Colours
from monty.utils.helpers import utcnow
from monty.utils.messages import DeleteButton


STATUS = (
    f"""
Version: `{Client.version}`
Disnake version: `{importlib.metadata.version("disnake")}`\n\n"""
    + """Guilds: `{guilds}`
Users: `{users}`
Channels: `{channels}`

CPU Usage: `{cpu_usage}%`
Memory Usage: `{memory_usage:.2f} MiB`

Latency: `{latency}`
Up since: <t:{uptime}:R>
"""
)

PRIVACY = """
Like every piece of software out there, Monty has a privacy policy.
Unlike most pieces of software, this is a very short privacy policy.

The privacy policy in full can be found here: <{privacy_url}>.
"""

COLOURS = (Colours.python_blue, Colours.python_yellow)


class Meta(
    commands.Cog,
    slash_command_attrs={
        "contexts": disnake.InteractionContextTypes.all(),
        "install_types": disnake.ApplicationInstallTypes.all(),
    },
):
    """Get meta information about the bot."""

    def __init__(self, bot: Monty) -> None:
        self.bot = bot
        self.process = psutil.Process()

        self._app_info_last_fetched: Optional[datetime] = None

    @commands.slash_command(name="monty")
    async def monty(self, inter: disnake.CommandInteraction) -> None:
        """Meta commands."""
        pass

    @monty.sub_command()
    async def ping(self, inter: disnake.ApplicationCommandInteraction) -> None:
        """Ping the bot to see its latency and state."""
        embed = disnake.Embed(
            title=":ping_pong: Pong!",
            colour=Colours.bright_green,
            description=f"Gateway Latency: {round(self.bot.latency * 1000)}ms",
        )
        embed.set_footer(text="Up since")
        embed.timestamp = self.bot.start_time.datetime

        components = DeleteButton(inter.author)
        await inter.send(embed=embed, components=components)

    @monty.sub_command(name="status")
    async def status(self, inter: disnake.CommandInteraction) -> None:
        """View the current bot status (uptime, guild count, resource usage, etc)."""
        e = disnake.Embed(
            title="Status",
            colour=random.choice(COLOURS),
        )
        e.set_footer(text=str(self.bot.user), icon_url=self.bot.user.display_avatar.url)
        memory_usage = self.process.memory_info()
        memory_usage = memory_usage.rss / 1024**2

        e.description = STATUS.format(
            disnake_version=importlib.metadata.version("disnake"),
            guilds=len(self.bot.guilds),
            users=sum([guild.member_count for guild in self.bot.guilds]),
            channels=sum(len(guild.channels) for guild in self.bot.guilds),
            memory_usage=memory_usage,
            cpu_usage=self.process.cpu_percent(),
            version=Client.version[:7],
            latency=f"{round(self.bot.latency * 1000)}ms",
            uptime=round(float(self.bot.start_time.format("X"))),
        )

        components = DeleteButton(inter.author)
        await inter.send(embed=e, components=components)

    async def application_info(self) -> disnake.AppInfo:
        """Fetch the application info using a local hour-long cache."""
        if not self._app_info_last_fetched or utcnow() - self._app_info_last_fetched > timedelta(hours=1):
            self._cached_app_info = await self.bot.application_info()
            self._app_info_last_fetched = utcnow()
        return self._cached_app_info

    @monty.sub_command()
    async def privacy(self, inter: disnake.AppCommandInteraction, ephemeral: bool = True) -> None:
        """
        See the privacy policy regarding what information is stored and shared.

        Parameters
        ----------
        ephemeral: Whether to send the privacy information as an ephemeral message.
        """
        appinfo = await self.application_info()
        embed = disnake.Embed(title=f"{self.bot.user.name}'s Privacy Information")
        embed.description = PRIVACY.format(privacy_url=appinfo.privacy_policy_url)
        embed.set_footer(text=str(self.bot.user), icon_url=self.bot.user.display_avatar.url)

        components = DeleteButton(inter.author) if not ephemeral else []
        await inter.response.send_message(embed=embed, ephemeral=ephemeral, components=components)


def setup(bot: Monty) -> None:
    """Load the Meta cog."""
    bot.add_cog(Meta(bot))
