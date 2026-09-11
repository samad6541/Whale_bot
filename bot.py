"""
ربات تلگرامی هشدار نهنگ‌های Hyperliquid
منبع داده: وب‌ساکت رسمی و رایگان Hyperliquid (بدون نیاز به API key)
هر معامله‌ای که ارزش دلاری‌اش از آستانه تعیین‌شده بیشتر باشه، به تلگرام ارسال می‌شه.
"""

import asyncio
import json
import os

import aiohttp
import websockets

# ---------- تنظیمات (از متغیرهای محیطی خونده می‌شه) ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "PUT_YOUR_CHAT_ID_HERE")
WHALE_THRESHOLD_USD = float(os.getenv("WHALE_THRESHOLD_USD", "1000000"))
# اگه بخوای فقط چند ارز خاص رو زیر نظر بگیری: COINS=BTC,ETH,SOL
# اگه خالی بذاری، همه‌ی ارزهای پرپچوال Hyperliquid رصد می‌شن
_coins_env = os.getenv("COINS", "").strip()
COINS_FILTER = [c.strip().upper() for c in _coins_env.split(",")] if _coins_env else None

HL_WS_URL = "wss://api.hyperliquid.xyz/ws"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"


async def get_all_coins(session: aiohttp.ClientSession):
    async with session.post(HL_INFO_URL, json={"type": "meta"}) as resp:
        data = await resp.json()
        return [u["name"] for u in data["universe"]]


async def send_telegram(session: aiohttp.ClientSession, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                print("خطای ارسال تلگرام:", await resp.text())
    except Exception as e:
        print("ارسال تلگرام ناموفق بود:", e)


def fmt(n: float) -> str:
    return f"{n:,.2f}"


async def handle_trade(session: aiohttp.ClientSession, trade: dict):
    try:
        px = float(trade["px"])
        sz = float(trade["sz"])
        coin = trade["coin"]
        side = trade["side"]
        users = trade.get("users", [])
        notional = px * sz

        if notional < WHALE_THRESHOLD_USD:
            return

        direction = "🟢 خرید (Buy)" if side == "B" else "🔴 فروش (Sell)"
        buyer = users[0] if len(users) > 0 else "?"
        seller = users[1] if len(users) > 1 else "?"

        text = (
            f"🐋 <b>معامله نهنگ در {coin}</b>\n\n"
            f"جهت تیکر: {direction}\n"
            f"قیمت: ${fmt(px)}\n"
            f"حجم: {fmt(sz)} {coin}\n"
            f"ارزش معامله: ${fmt(notional)}\n\n"
            f"آدرس خریدار: <code>{buyer}</code>\n"
            f"آدرس فروشنده: <code>{seller}</code>"
        )
        print(text.replace("\n", " | "))
        await send_telegram(session, text)
    except Exception as e:
        print("خطا در پردازش معامله:", e)


async def listen():
    async with aiohttp.ClientSession() as session:
        coins = COINS_FILTER if COINS_FILTER else await get_all_coins(session)
        print(f"در حال رصد {len(coins)} ارز برای معاملات بالای ${WHALE_THRESHOLD_USD:,.0f} ...")

        while True:
            try:
                async with websockets.connect(HL_WS_URL, ping_interval=20, ping_timeout=20) as ws:
                    for coin in coins:
                        sub = {"method": "subscribe", "subscription": {"type": "trades", "coin": coin}}
                        await ws.send(json.dumps(sub))
                        await asyncio.sleep(0.05)  # جلوگیری از rate limit

                    print("عضویت انجام شد. در انتظار معاملات نهنگ...")

                    async for message in ws:
                        data = json.loads(message)
                        if data.get("channel") == "trades":
                            for trade in data.get("data", []):
                                await handle_trade(session, trade)

            except Exception as e:
                print("خطای اتصال وب‌ساکت، تلاش مجدد بعد از ۵ ثانیه:", e)
                await asyncio.sleep(5)


if __name__ == "__main__":
    if "PUT_YOUR" in TELEGRAM_TOKEN or "PUT_YOUR" in TELEGRAM_CHAT_ID:
        print("⚠️  اول TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID رو در فایل .env تنظیم کن.")
    asyncio.run(listen())
