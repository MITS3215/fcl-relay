# scan_and_relay.py
import os, re, asyncio, datetime as dt
import discord

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
INBOX_CHANNEL_ID = int(os.getenv("INBOX_CHANNEL_ID"))

ROUTES = {
    "news":    int(os.getenv("CH_NEWS_ID", "0")),
    "event":   int(os.getenv("CH_EVENT_ID", "0")),
    "seminar": int(os.getenv("CH_SEMINAR_ID", "0")),
    "tips":    int(os.getenv("CH_TIPS_ID", "0")),
}

CATEGORY_RE = re.compile(r"^\s*#category:\s*([a-z_]+)\s*$", re.I)

# 走査ウィンドウ（時間）
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "12"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

async def relay_once():
    guild = client.get_guild(GUILD_ID)
    inbox = guild.get_channel(INBOX_CHANNEL_ID)
    if not inbox:
        print("INBOX not found"); return

    after = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=LOOKBACK_HOURS)
    count_scanned = 0
    count_posted = 0

    async for msg in inbox.history(limit=500, after=after, oldest_first=True):
        count_scanned += 1
        if msg.author.bot:
            continue
        # 既に処理済み（✅リアクション）ならスキップ
        if any(r.emoji == "✅" for r in msg.reactions):
            continue

        lines = msg.content.splitlines()
        if not lines: 
            continue

        m = CATEGORY_RE.match(lines[0])
        if not m:
            continue

        cat = m.group(1).lower().strip()
        target_id = ROUTES.get(cat, 0)
        if not target_id:
            # カテゴリ不明は❗で印だけ付ける
            try: await msg.add_reaction("❗")
            except: pass
            continue

        body = "\n".join(lines[1:]).strip()
        if not body:
            body = "(本文なし)"

        target = guild.get_channel(target_id)
        if not target:
            try: await msg.add_reaction("❗")
            except: pass
            continue

        embed = discord.Embed(description=body)
        embed.set_author(name="FCL｜公式通知")
        # 元メッセージURLをフッターに入れて出所を残す
        embed.set_footer(text=f"from #{inbox.name} / {msg.jump_url}")

        await target.send(embed=embed)
        try:
            await msg.add_reaction("✅")
        except:
            pass
        count_posted += 1

    print(f"scanned={count_scanned}, posted={count_posted}")

@client.event
async def on_ready():
    try:
        await relay_once()
    finally:
        await client.close()  # 終了（無料枠にやさしい）

client.run(TOKEN)
