import asyncio
import json
import os

import dotenv
from ollama import chat
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from data_proccess import embedding_search

TELEGRAM_BOT_TOKEN = None
OLLAMA_MODEL = None

# Load prompt files once when the application starts.
with open("prompt/chat_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()
with open("prompt/info_prompt.txt", "r", encoding="utf-8") as f:
    INFO_PROMPT = f.read()


class Memory:
    def __init__(self, user_id):
        self.user_id = str(user_id)
        self.file_path = os.path.join(".Memory", f"{self.user_id}.json")
        os.makedirs(".Memory", exist_ok=True)

    def default_data(self):
        return {
            "user_id": self.user_id,
            "profile": {},
            "preferences": {},
            "conversation": [],
        }

    def load_json(self):
        if not os.path.exists(self.file_path):
            return self.default_data()
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return self.default_data()

        if not isinstance(data, dict):
            return self.default_data()
        data.setdefault("user_id", self.user_id)
        data.setdefault("profile", {})
        data.setdefault("preferences", {})
        data.setdefault("conversation", [])
        return data

    def write_json(self, data):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def save_json(self, data):
        """Save validated profile and preference updates from the extractor."""
        if not isinstance(data, dict):
            return

        current_data = self.load_json()
        updates = data.get("updates", [data])
        if not isinstance(updates, list):
            return

        for update in updates:
            if not isinstance(update, dict):
                continue

            section = update.get("section")
            field = update.get("field")
            if section not in {"profile", "preferences"} or not field:
                continue

            current_data[section][field] = update.get("value")

        self.write_json(current_data)

    def add_conversation(self, role, content):
        current_data = self.load_json()
        current_data["conversation"].append({"role": role, "content": content})
        # Keep only the latest 20 messages so the file and model context stay small.
        current_data["conversation"] = current_data["conversation"][-20:]
        self.write_json(current_data)

    async def extract_info(self, text):
        response = await asyncio.to_thread(
            chat,
            model=OLLAMA_MODEL,
            format="json",
            messages=[
                {"role": "system", "content": INFO_PROMPT},
                {
                    "role": "system",
                    "content": "Existing saved user record (JSON):\n"
                    + json.dumps(self.load_json(), ensure_ascii=False),
                },
                {"role": "user", "content": text},
            ],
        )
        try:
            return json.loads(response.message.content)
        except json.JSONDecodeError:
            return None


def main():
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! I am a helpful assistant.")

    async def keep_typing(bot, chat_id):
        while True:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(5)

    async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_memory = Memory(user_id)
        text = update.message.text

        if not text:
            await update.message.reply_text("Please send a text message.")
            return

        info = await user_memory.extract_info(text)
        if info:
            user_memory.save_json(info)

        saved_data = user_memory.load_json()

        #chat_context = search(text)
        chat_context = embedding_search(text)

        temp_history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": "User profile and preferences (JSON):\n"
                + json.dumps(
                    {
                        "profile": saved_data["profile"],
                        "preferences": saved_data["preferences"],
                    },
                    ensure_ascii=False,
                ),
            },
            {"role": "user", "content": f"data: {chat_context}"},
            *saved_data["conversation"],
            {"role": "user", "content": text},
        ]

        typing_task = asyncio.create_task(
            keep_typing(context.bot, update.effective_chat.id)
        )
        try:
            response = await asyncio.to_thread(
                chat,
                model=OLLAMA_MODEL,
                messages=temp_history,
            )
            answer = response.message.content

            user_memory.add_conversation("user", text)
            user_memory.add_conversation("assistant", answer)
            await update.message.reply_text(answer)
        finally:
            typing_task.cancel()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate))

    app.run_polling()


if __name__ == "__main__":
    dotenv.load_dotenv()

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

    main()
