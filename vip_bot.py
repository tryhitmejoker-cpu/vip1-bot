"""
╔══════════════════════════════════════════════════════════════╗
║              VIP MEMBERSHIP BOT — vip_bot.py                ║
╠══════════════════════════════════════════════════════════════╣
║  SETUP: pip install python-telegram-bot                      ║
║  RUN:   python vip_bot.py                                    ║
╚══════════════════════════════════════════════════════════════╝
"""

import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = "8702889746:AAGr7XiGJmDIKb-dHq9sQ76FkWUp1PiOjLU"
ADMIN_ID  = 8633029909

GROUPS = {
    "Strictly Wales":   "https://t.me/+Vj0NAJSXOl9iZTY0",
    "Strictly Lives":   "https://t.me/+Ew70kKDeuUUzMDBk",
    "Strictly Main":    "https://t.me/+6PoFACYVXiIzODlk",
    "Strickly O.F":     "https://t.me/+oZb7m7Aahjw1MDdk",
    "Strickly Ireland": "https://t.me/+Nt-hPOQTkjVkNjA0",
    "Strickly Chav":    "https://t.me/+O21X3pkDBtIzYTI0",
    "Strictly OGs":     "https://t.me/+ZopIORlgReZmZTNk",
}

WELCOME_MESSAGE = """👋 *Welcome to the VIP Community!*

To get access to all {count} exclusive groups, submit your payment proof below and the admin will approve you shortly.

Once approved you'll receive your private links to all groups instantly."""

APPROVED_MESSAGE = """🎉 *You've been approved! Welcome to the VIP!*

Here are your private group links:

{links}

These links are for you only — do not share them.

If you have any issues use /mylinks to get them again."""

DENIED_MESSAGE = """Your payment proof was not accepted.

Please send a new screenshot and try again, or contact the admin directly."""

DB_FILE = "members.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {"members": {}, "pending": {}, "groups": GROUPS}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, default=str)

def get_groups(db):
    return db.get("groups", GROUPS)

def is_admin(update):
    return update.effective_user.id == ADMIN_ID

def build_links_text(groups):
    return "\n".join(f"• *{name}*\n  {link}" for name, link in groups.items())

async def start(update, ctx):
    user = update.effective_user
    uid  = str(user.id)
    db   = load_db()
    if user.id == ADMIN_ID:
        await show_admin_panel(update, ctx)
        return
    if uid in db["members"]:
        await update.message.reply_text("You are an active VIP member!\n\nUse /mylinks to get your group links.")
        return
    if uid in db["pending"]:
        await update.message.reply_text("Your payment proof is under review. You will be notified once approved!")
        return
    groups = get_groups(db)
    await update.message.reply_text(
        WELCOME_MESSAGE.format(count=len(groups)),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 Submit Payment Proof", callback_data="submit_proof")
        ]])
    )

async def submit_proof_prompt(update, ctx):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    db  = load_db()
    if uid in db["members"]:
        await query.edit_message_text("You are already an approved member!")
        return
    if uid in db["pending"]:
        await query.edit_message_text("Your proof is already being reviewed.")
        return
    ctx.user_data["awaiting_proof"] = True
    await query.edit_message_text("📸 Send your payment screenshot now — just upload the image in this chat.")

async def receive_proof(update, ctx):
    user = update.effective_user
    uid  = str(user.id)
    db   = load_db()
    if not ctx.user_data.get("awaiting_proof"):
        if uid not in db["members"]:
            await update.message.reply_text("Use /start to request access.")
        return
    if not update.message.photo:
        await update.message.reply_text("Please send an image of your payment proof.")
        return
    if uid in db["pending"]:
        await update.message.reply_text("Your proof is already under review.")
        return
    db["pending"][uid] = {
        "name":         user.full_name,
        "username":     f"@{user.username}" if user.username else "no username",
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "photo_id":     update.message.photo[-1].file_id
    }
    save_db(db)
    ctx.user_data["awaiting_proof"] = False
    await update.message.reply_text("Payment proof submitted! The admin is reviewing it now. You will be notified shortly.")
    info = db["pending"][uid]
    await ctx.bot.send_photo(
        ADMIN_ID,
        photo=info["photo_id"],
        caption=(
            f"New Payment Proof\n\n"
            f"Name: {info['name']}\n"
            f"Username: {info['username']}\n"
            f"ID: {uid}\n"
            f"Time: {info['submitted_at']}"
        ),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{uid}"),
            InlineKeyboardButton("❌ Deny",    callback_data=f"deny:{uid}")
        ]])
    )

async def my_links(update, ctx):
    uid = str(update.effective_user.id)
    db  = load_db()
    if uid not in db["members"]:
        await update.message.reply_text("You are not an approved member yet. Use /start.")
        return
    groups = get_groups(db)
    await update.message.reply_text(
        f"*Your VIP Group Links:*\n\n{build_links_text(groups)}",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def handle_approval(update, ctx):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        await query.answer("Not authorized.", show_alert=True)
        return
    action, uid = query.data.split(":", 1)
    db = load_db()
    if uid not in db["pending"]:
        await query.edit_message_caption("Already handled.")
        return
    info = db["pending"].pop(uid)
    if action == "approve":
        db["members"][uid] = {
            "name":     info["name"],
            "username": info["username"],
            "joined":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save_db(db)
        groups = get_groups(db)
        try:
            await ctx.bot.send_message(
                int(uid),
                APPROVED_MESSAGE.format(links=build_links_text(groups)),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logging.warning(f"Could not message {uid}: {e}")
        await query.edit_message_caption(f"✅ Approved: {info['name']} ({info['username']})")
    elif action == "deny":
        save_db(db)
        try:
            await ctx.bot.send_message(int(uid), DENIED_MESSAGE)
        except Exception as e:
            logging.warning(f"Could not message {uid}: {e}")
        await query.edit_message_caption(f"❌ Denied: {info['name']} ({info['username']})")

async def show_admin_panel(update, ctx):
    db = load_db()
    groups = get_groups(db)
    text = (
        f"*Admin Panel*\n\n"
        f"Approved members: {len(db['members'])}\n"
        f"Pending proofs: {len(db['pending'])}\n"
        f"Groups: {len(groups)}\n\n"
        f"*Commands:*\n"
        f"/members — list all approved members\n"
        f"/pending — review pending submissions\n"
        f"/broadcast — message all approved members\n"
        f"/revoke @username — remove a member\n"
        f"/addgroup — add a new group and notify everyone\n"
        f"/groups — list current groups"
    )
    msg = update.message or (update.callback_query and update.callback_query.message)
    await msg.reply_text(text, parse_mode="Markdown")

async def cmd_admin(update, ctx):
    if not is_admin(update): return
    await show_admin_panel(update, ctx)

async def list_members(update, ctx):
    if not is_admin(update): return
    db = load_db()
    if not db["members"]:
        await update.message.reply_text("No approved members yet.")
        return
    lines = ["*Approved Members*\n"]
    for uid, info in db["members"].items():
        lines.append(f"• {info['name']} {info['username']} | joined {info['joined']} | ID: {uid}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def list_pending(update, ctx):
    if not is_admin(update): return
    db = load_db()
    if not db["pending"]:
        await update.message.reply_text("No pending submissions.")
        return
    for uid, info in db["pending"].items():
        await ctx.bot.send_photo(
            ADMIN_ID,
            photo=info["photo_id"],
            caption=(
                f"Pending\n\nName: {info['name']}\n"
                f"Username: {info['username']}\nID: {uid}\n"
                f"Submitted: {info['submitted_at']}"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{uid}"),
                InlineKeyboardButton("❌ Deny",    callback_data=f"deny:{uid}")
            ]])
        )

async def revoke(update, ctx):
    if not is_admin(update): return
    if not ctx.args:
        await update.message.reply_text("Usage: /revoke @username  or  /revoke 123456789")
        return
    query = ctx.args[0].lstrip("@").lower()
    db = load_db()
    found_uid = None
    for uid, info in db["members"].items():
        if uid == query or info["username"].lstrip("@").lower() == query:
            found_uid = uid
            break
    if not found_uid:
        await update.message.reply_text(f"Member '{query}' not found.")
        return
    info = db["members"].pop(found_uid)
    save_db(db)
    try:
        await ctx.bot.send_message(
            int(found_uid),
            "Your VIP membership has been removed by the admin. Contact the admin if you think this is a mistake."
        )
    except Exception:
        pass
    await update.message.reply_text(f"Access revoked for {info['name']} ({info['username']}).")

async def broadcast_start(update, ctx):
    if not is_admin(update): return
    db = load_db()
    if not db["members"]:
        await update.message.reply_text("No approved members to broadcast to.")
        return
    ctx.user_data["broadcasting"] = True
    await update.message.reply_text(
        f"*Broadcast Mode*\n\nSend your message now (text, photo, or video).\n"
        f"It will be sent to all {len(db['members'])} approved members.\n\nSend /cancel to abort.",
        parse_mode="Markdown"
    )

async def broadcast_send(update, ctx):
    if not is_admin(update): return
    if not ctx.user_data.get("broadcasting"): return
    ctx.user_data["broadcasting"] = False
    db = load_db()
    msg = update.message
    sent, failed = 0, 0
    await msg.reply_text(f"Sending to {len(db['members'])} members...")
    for uid in db["members"]:
        try:
            if msg.photo:
                await ctx.bot.send_photo(int(uid), msg.photo[-1].file_id, caption=msg.caption or "")
            elif msg.video:
                await ctx.bot.send_video(int(uid), msg.video.file_id, caption=msg.caption or "")
            elif msg.text:
                await ctx.bot.send_message(int(uid), msg.text)
            sent += 1
        except Exception:
            failed += 1
    await msg.reply_text(f"Broadcast done! Sent: {sent} | Failed: {failed}")

async def cancel_all(update, ctx):
    if not is_admin(update): return
    ctx.user_data["broadcasting"]   = False
    ctx.user_data["awaiting_proof"] = False
    ctx.user_data["adding_group"]   = False
    await update.message.reply_text("Cancelled.")

async def list_groups(update, ctx):
    if not is_admin(update): return
    db = load_db()
    groups = get_groups(db)
    lines = ["*Current Groups*\n"]
    for name, link in groups.items():
        lines.append(f"• *{name}*\n  {link}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

async def addgroup_start(update, ctx):
    if not is_admin(update): return
    ctx.user_data["adding_group"] = True
    await update.message.reply_text(
        "*Add New Group*\n\nSend the details in this format:\n\n"
        "`Group Name | https://t.me/+invitelink`\n\nSend /cancel to abort.",
        parse_mode="Markdown"
    )

async def addgroup_receive(update, ctx):
    if not is_admin(update): return
    if not ctx.user_data.get("adding_group"): return
    text = update.message.text or ""
    if "|" not in text:
        await update.message.reply_text("Wrong format. Use: Group Name | https://t.me/+link")
        return
    parts = text.split("|", 1)
    name  = parts[0].strip()
    link  = parts[1].strip()
    if not name or not link.startswith("https://"):
        await update.message.reply_text("Invalid name or link.")
        return
    ctx.user_data["adding_group"] = False
    db = load_db()
    groups = get_groups(db)
    groups[name] = link
    db["groups"] = groups
    save_db(db)
    await update.message.reply_text(
        f"*{name}* added!\n\nNotifying all {len(db['members'])} approved members...",
        parse_mode="Markdown"
    )
    sent, failed = 0, 0
    for uid in db["members"]:
        try:
            await ctx.bot.send_message(
                int(uid),
                f"*New VIP Group Added!*\n\n• *{name}*\n  {link}\n\nUse /mylinks to see all your group links.",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"Done! Notified {sent} members. Failed: {failed}.")

async def router(update, ctx):
    user = update.effective_user
    if not user: return
    if user.id == ADMIN_ID:
        if ctx.user_data.get("broadcasting"):
            await broadcast_send(update, ctx)
        elif ctx.user_data.get("adding_group"):
            await addgroup_receive(update, ctx)
        return
    uid = str(user.id)
    db  = load_db()
    if ctx.user_data.get("awaiting_proof"):
        await receive_proof(update, ctx)
    elif uid not in db["members"] and uid not in db["pending"]:
        await update.message.reply_text("Use /start to request VIP access.")

async def callback_router(update, ctx):
    data = update.callback_query.data
    if data == "submit_proof":
        await submit_proof_prompt(update, ctx)
    elif data.startswith("approve:") or data.startswith("deny:"):
        await handle_approval(update, ctx)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("mylinks",   my_links))
    app.add_handler(CommandHandler("admin",     cmd_admin))
    app.add_handler(CommandHandler("members",   list_members))
    app.add_handler(CommandHandler("pending",   list_pending))
    app.add_handler(CommandHandler("revoke",    revoke))
    app.add_handler(CommandHandler("broadcast", broadcast_start))
    app.add_handler(CommandHandler("groups",    list_groups))
    app.add_handler(CommandHandler("addgroup",  addgroup_start))
    app.add_handler(CommandHandler("cancel",    cancel_all))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, router))
    print("VIP Bot is running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
