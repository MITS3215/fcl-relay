# scan_and_relay.py
import os
import re
import datetime as dt
import discord

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
INBOX_CHANNEL_ID = int(os.getenv("INBOX_CHANNEL_ID"))
CH_TIKTOK_INFO_ID = int(os.getenv("CH_TIKTOK_INFO_ID", "0"))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "12"))

# 旧運用の category 行が残っていた場合は、再投稿時に削除する
CATEGORY_LINE_RE = re.compile(r"^\s*#category:\s*[a-z_]+\s*$", re.I)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def is_image(att: discord.Attachment) -> bool:
    ct = (att.content_type or "").lower()
    if ct.startswith("image/"):
        return True

    name = (att.filename or "").lower()
    return name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))


def clean_body(content: str) -> str:
    """
    告知メモ本文を再投稿用に整える。
    旧運用の #category: xxx 行が残っていれば削除。
    """
    lines = content.splitlines()
    cleaned = [line for line in lines if not CATEGORY_LINE_RE.match(line)]
    body = "\n".join(cleaned).strip()
    return body or "(本文なし)"


async def relay_once():
    guild = client.get_guild(GUILD_ID)
    if not guild:
        print("GUILD not found")
        return

    inbox = guild.get_channel(INBOX_CHANNEL_ID)
    if not inbox:
        print("INBOX not found")
        return

    target = guild.get_channel(CH_TIKTOK_INFO_ID)
    if not target:
        print("TIKTOK INFO channel not found")
        return

    after = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=LOOKBACK_HOURS)
    count_scanned = 0
    count_posted = 0

    async for msg in inbox.history(limit=500, after=after, oldest_first=True):
        count_scanned += 1

        # Bot投稿は処理しない
        if msg.author.bot:
            continue

        # 既に処理済み（✅リアクション）ならスキップ
        if any(r.emoji == "✅" for r in msg.reactions):
            continue

        body = clean_body(msg.content)

        # 本文も添付もない場合はスキップ
        if body == "(本文なし)" and not msg.attachments:
            continue

        # ---- 添付（画像/非画像）を拾う ----
        image_urls = []
        other_urls = []

        for att in msg.attachments:
            if is_image(att):
                image_urls.append(att.url)
            else:
                other_urls.append(att.url)

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
            extra = "\n\n" + "\n".join(tail_lines)
            new_desc = (embeds[0].description or "") + extra
            embeds[0].description = new_desc[:3800]

        # 送信
        await target.send(embeds=embeds)

        # 処理済みマーク
        try:
            await msg.add_reaction("✅")
        except Exception as e:
            print(f"failed to add reaction: {e}")

        count_posted += 1

    print(f"scanned={count_scanned}, posted={count_posted}")


@client.event
async def on_ready():
    try:
        await relay_once()
    finally:
        await client.close()


client.run(TOKEN)
