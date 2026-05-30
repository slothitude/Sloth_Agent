"""Telegram update handlers — text and commands only."""
import re

from telegram import Update
from telegram.ext import ContextTypes

import config
import openwebui_client
import sessions


def _split_message(text: str, max_len: int = config.MAX_RESPONSE_CHARS) -> list[str]:
    """Split long text at paragraph or sentence boundaries."""
    if len(text) <= max_len:
        return [text]
    parts = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break
        cut = remaining.rfind("\n\n", 0, max_len)
        if cut < max_len // 2:
            cut = remaining.rfind(". ", 0, max_len)
            if cut < max_len // 2:
                cut = remaining.rfind(" ", 0, max_len)
            else:
                cut += 1
        else:
            cut += 2
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return parts


def _strip_markdown(text: str) -> str:
    """Strip HTML/markdown for Telegram plain text."""
    text = re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think[^>]*>.*?</think\s*>", "", text, flags=re.DOTALL)
    text = re.sub(r"</?details[^>]*>", "", text)
    text = re.sub(r"</?summary[^>]*>", "", text)
    text = re.sub(r"[*_]", "", text)
    text = re.sub(r"`[^`]+`", lambda m: m.group(1), text, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    return text.strip()


async def _send_agent_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    """Send message to sloth-agent with full conversation history, reply with text."""
    user_id = update.effective_user.id
    session = sessions.get_session(user_id)

    # Append user message to history
    session["messages"].append({"role": "user", "content": message})

    await update.effective_chat.send_chat_action("typing")

    try:
        reply_text, chat_id = openwebui_client.send_chat(
            message_history=session["messages"],
            chat_id=session["chat_id"],
        )
        session["chat_id"] = chat_id

        # Append assistant response to history for next turn
        session["messages"].append({"role": "assistant", "content": reply_text})

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    reply_text = _strip_markdown(reply_text)

    if not reply_text:
        await update.message.reply_text("(empty response)")
        return

    parts = _split_message(reply_text)
    for part in parts:
        try:
            await update.message.reply_text(part)
        except Exception as e:
            print(f"SEND FAILED: {e}", flush=True)
            try:
                await update.message.reply_text(part[:4000])
            except Exception:
                await update.message.reply_text("Error sending response.")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Sloth Agent Bridge active.\n\n"
        "Send me a message and I'll pass it to the agent.\n"
        "/reset — clear conversation\n"
        "/help — show this help"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start — start the bot\n"
        "/reset — clear conversation history\n"
        "/help — show this help"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sessions.clear(update.effective_user.id)
    await update.message.reply_text("Conversation reset.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_agent_reply(update, context, update.message.text)
