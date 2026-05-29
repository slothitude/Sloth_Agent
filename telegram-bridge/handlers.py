"""Telegram update handlers — text, voice, photo, commands."""
import re

from telegram import Update
from telegram.ext import ContextTypes

import config
import openwebui_client
import sessions
import voice


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
        # Try paragraph break
        cut = remaining.rfind("\n\n", 0, max_len)
        if cut < max_len // 2:
            # Try sentence break
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
    """Strip HTML tags and markdown formatting for Telegram."""
    # Remove <details>...</details> blocks (reasoning)
    text = re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)
    # Remove <think Think tags
    text = re.sub(r"<think[^>]*>.*?</think Think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think[^>]*>.*?</think \>", "", text, flags=re.DOTALL)
    text = re.sub(r"<think.*?</think \>", "", text, flags=re.DOTALL)
    # Clean up leftover tags
    text = re.sub(r"</?details[^>]*>", "", text)
    text = re.sub(r"</?summary[^>]*>", "", text)
    # Strip markdown bold/italic/formatting
    text = re.sub(r"[*_]", "", text)
    # Strip inline code blocks
    text = re.sub(r"`[^`]+`", lambda m: m.group(1), text, flags=re.DOTALL)
    # Strip [text](url) keeping text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Strip ## headers
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    return text.strip()


async def _send_agent_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str, is_voice_response: bool = False):
    """Core handler: send message to agent, stream response back to Telegram."""
    user_id = update.effective_user.id
    chat_id = sessions.get_chat_id(user_id)

    # Show typing
    await update.effective_chat.send_chat_action("typing")

    try:
        reply_text, real_chat_id = openwebui_client.stream_chat(message, chat_id=chat_id)
        sessions.set_chat_id(user_id, real_chat_id)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    reply_text = _strip_markdown(reply_text)

    if not reply_text:
        await update.message.reply_text("(empty response)")
        return

    parts = _split_message(reply_text)

    for i, part in enumerate(parts):
        if is_voice_response and i == 0:
            # Send voice response for first part
            try:
                audio_bytes = voice.synthesize(part)
                await update.message.reply_voice(audio_bytes, caption=part if len(part) > 200 else None)
                continue
            except Exception:
                # Fall back to text if TTS fails
                pass

        # Send as plain text (no parse_mode — Telegram renders native markdown)
        try:
            await update.message.reply_text(part)
        except Exception as e:
            print(f"SEND FAILED for {len(part)} char message: {e}", flush=True)
            try:
                await update.message.reply_text(part[:4000])
            except Exception as e2:
                print(f"FALLBACK FAILED: {e2}", flush=True)
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
        "/help — show this help\n\n"
        "Send text, voice, or photos directly."
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sessions.clear(user_id)
    await update.message.reply_text("Conversation reset.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_agent_reply(update, context, update.message.text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice_file = await update.message.voice.get_file()
    audio_bytes = await voice_file.download_as_bytearray()

    await update.effective_chat.send_chat_action("typing")

    try:
        text = voice.transcribe(bytes(audio_bytes))
    except Exception as e:
        await update.message.reply_text(f"STT error: {e}")
        return

    if not text:
        await update.message.reply_text("Couldn't understand the audio.")
        return

    await update.message.reply_text(f"_{text}_", parse_mode="Markdown")
    await _send_agent_reply(update, context, text, is_voice_response=True)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or "Describe this image."
    await _send_agent_reply(update, context, f"[User sent a photo] {caption}")
