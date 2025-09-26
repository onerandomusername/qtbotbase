from __future__ import annotations

import asyncio
import datetime
import re
import ssl
import textwrap
from typing import TYPE_CHECKING, Any, Coroutine, Optional, TypeVar, Union

import dateutil.parser
import disnake

from monty.log import get_logger
from monty.utils import scheduling
from monty.utils.messages import extract_urls


if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    P = ParamSpec("P")
    T = TypeVar("T")
    Coro = Coroutine[Any, Any, T]
UNSET = object()

logger = get_logger(__name__)

ESCAPE_REGEX = re.compile("[`\u202e\u200b]{3,}")
FORMATTED_CODE_REGEX = re.compile(
    r"(?P<delim>(?P<block>```)|``?)"  # code delimiter: 1-3 backticks; (?P=block) only matches if it's a block
    r"(?(block)(?:(?P<lang>[a-z]+)\n)?)"  # if we're in a block, match optional language (only letters plus newline)
    r"(?:[ \t]*\n)*"  # any blank (empty or tabs/spaces only) lines before the code
    r"(?P<code>.*?)"  # extract all code inside the markup
    r"\s*"  # any more whitespace before the end of the code markup
    r"(?P=delim)",  # match the exact same delimiter from the start again
    re.DOTALL | re.IGNORECASE,  # "." also matches newlines, case insensitive
)
RAW_CODE_REGEX = re.compile(
    r"^(?:[ \t]*\n)*"  # any blank (empty or tabs/spaces only) lines before the code
    r"(?P<code>.*?)"  # extract all the rest as code
    r"\s*$",  # any trailing whitespace until the end of the string
    re.DOTALL,  # "." also matches newlines
)


def suppress_links(message: str) -> str:
    """Accepts a message that may contain links, suppresses them, and returns them."""
    for link in extract_urls(message):
        message = message.replace(link, f"<{link}>")
    return message


def find_nth_occurrence(string: str, substring: str, n: int) -> Optional[int]:
    """Return index of `n`th occurrence of `substring` in `string`, or None if not found."""
    index = 0
    for _ in range(n):
        index = string.find(substring, index + 1)
        if index == -1:
            return None
    return index


def get_num_suffix(num: int) -> str:
    """Get the suffix for the provided number. Currently a lazy implementation so this only supports 1-20."""
    if num == 1:
        suffix = "st"
    elif num == 2:
        suffix = "nd"
    elif num == 3:
        suffix = "rd"
    elif 4 <= num < 20:
        suffix = "th"
    else:
        err = "num must be within 1-20. If you receive this error you should refactor the get_num_suffix method."
        raise RuntimeError(err)
    return suffix


def has_lines(string: str, count: int) -> bool:
    """Return True if `string` has at least `count` lines."""
    # Benchmarks show this is significantly faster than using str.count("\n") or a for loop & break.
    split = string.split("\n", count - 1)

    # Make sure the last part isn't empty, which would happen if there was a final newline.
    return bool(split[-1]) and len(split) == count


def pad_base64(data: str) -> str:
    """Return base64 `data` with padding characters to ensure its length is a multiple of 4."""
    return data + "=" * (-len(data) % 4)


def maybe_defer(inter: disnake.Interaction, *, delay: Union[float, int] = 2.0, **options) -> asyncio.Task:
    """Defer an interaction if it has not been responded to after ``delay`` seconds."""
    loop = inter.bot.loop
    if delay <= 0:
        return scheduling.create_task(inter.response.defer(**options))

    async def internal_task() -> None:
        now = loop.time()
        await asyncio.sleep(delay - (start - now))

        if inter.response.is_done():
            return
        try:
            await inter.response.defer(**options)
        except disnake.HTTPException as e:
            if e.code == 40060:  # interaction has already been acked
                logger.warning("interaction was already responded to (race condition)")
                return
            raise e

    start = loop.time()
    return scheduling.create_task(internal_task())


def utcnow() -> datetime.datetime:
    """Return the current time as an aware datetime in UTC."""
    return datetime.datetime.now(datetime.timezone.utc)


def fromisoformat(timestamp: str) -> datetime.datetime:
    """Parse the given ISO-8601 timestamp to an aware datetime object, assuming UTC if timestamp contains no timezone."""  # noqa: E501
    dt = dateutil.parser.isoparse(timestamp)
    if not dt.tzinfo:
        # assume UTC if naive datetime
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def ssl_create_default_context() -> ssl.SSLContext:
    """Return an ssl context that CloudFlare shouldn't flag."""
    ssl_context = ssl.create_default_context()
    ssl_context.post_handshake_auth = True
    return ssl_context


def cleanup_code(code: str, *, require_fenced: bool = False) -> Optional[str]:
    """
    Extract code from the Markdown, format it, and insert it into the code template.

    If there is any code block, ignore text outside the code block.
    Use the first code block, but prefer a fenced code block.
    If there are several fenced code blocks, concatenate only the fenced code blocks.
    """
    if match := list(FORMATTED_CODE_REGEX.finditer(code)):
        blocks = [block for block in match if block.group("block")]

        if len(blocks) > 1:
            code = "\n".join(block.group("code") for block in blocks)
            info = "several code blocks"
        else:
            match = match[0] if len(blocks) == 0 else blocks[0]
            code, block, lang, delim = match.group("code", "block", "lang", "delim")
            if block:
                info = (f"'{lang}' highlighted" if lang else "plain") + " code block"
            else:
                info = f"{delim}-enclosed inline code"
    elif require_fenced:
        return None
    else:
        code = RAW_CODE_REGEX.fullmatch(code).group("code")
        info = "unformatted or badly formatted code"

    code = textwrap.dedent(code)
    logger.trace(f"Extracted {info} for evaluation:\n{code}")
    return code
