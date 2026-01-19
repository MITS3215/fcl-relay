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
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "12"))

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def is_image(att: discord.Attachment) -> bool:
    ct = (att.content_type or "").lower()
    if ct.startswith("image/"):
        return True
    name = (att.filename or "").lower()
    return name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))

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

        # ---- 添付（画像/非画像）を拾う ----
        image_urls = []
        other_urls = []
        for att in msg.attachments:
            if is_image(att):
                image_urls.append(att.url)
            else:
                other_urls.append(att.url)

        # 本文末尾に「添付リンク」を付ける（画像も上限超え分はここに落とす）
        tail_lines = []
        if other_urls:
            tail_lines.append("添付: " + " ".join(other_urls))

        # ---- Embed作成 ----
        embeds = []
        base = discord.Embed(description=body)
        base.set_author(name="FCL｜公式通知")

        if image_urls:
            # 1つ目はbaseに表示
            base.set_image(url=image_urls[0])
            embeds.append(base)

            # 2枚目以降は追加embed（最大10件まで：Discord制限を踏まえて）
            for url in image_urls[1:10]:
                e = discord.Embed()
                e.set_image(url=url)
                embeds.append(e)

            # 上限超え分はリンクで残す
            if len(image_urls) > 10:
                overflow = image_urls[10:]
                tail_lines.append("画像(追加): " + " ".join(overflow))
        else:
            embeds.append(base)

        if tail_lines:
            # descriptionの末尾に追記（長すぎる場合は切る）
            extra = "\n\n" + "\n".join(tail_lines)
            # Embed descriptionは上限があるので安全側に
            new_desc = (embeds[0].description or "") + extra
            embeds[0].description = new_desc[:3800]

        # 送信（複数embed対応）
        await target.send(embeds=embeds)

        # 処理済みマーク
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
