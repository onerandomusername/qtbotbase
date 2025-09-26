try:
    import dotenv
except ModuleNotFoundError:
    pass
else:
    if dotenv.find_dotenv():
        print("Found .env file, loading environment variables from it.")  # noqa: T201
        dotenv.load_dotenv(override=True)


import asyncio
import os
from functools import partial, partialmethod

import disnake
from disnake.ext import commands


try:
    import rich.traceback
except ModuleNotFoundError:
    pass
else:
    rich.traceback.install(show_locals=True, word_wrap=True, suppress=[disnake])

####################
# NOTE: do not import any other modules from monty before the `log.setup()` call
####################
from monty import log


log.setup()


from monty import monkey_patches  # noqa: E402  # we need to set up logging before importing anything else


# On Windows, the selector event loop is required for aiodns.
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Monkey-patch discord.py decorators to use the both the Command and Group subclasses which supports root aliases.
# Must be patched before any cogs are added.
commands.command = partial(commands.command, cls=monkey_patches.Command)
commands.GroupMixin.command = partialmethod(commands.GroupMixin.command, cls=monkey_patches.Command)  # type: ignore

commands.group = partial(commands.group, cls=monkey_patches.Group)
commands.GroupMixin.group = partialmethod(commands.GroupMixin.group, cls=monkey_patches.Group)  # type: ignore
