import asyncio
import dotenv
import os
import json
from google import genai
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TELEGRAM_BOT_TOKEN = None
GEMINI_MODEL = None
EMBED_MODEL = None
GENAI_CLIENT = None

# open prompt files
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
        """Save one {section, field, value} update from the extractor."""
        if not isinstance(data, dict):
            return
        section = data.get("section")
        field = data.get("field")
        if section not in {"profile", "preferences"} or not field:
            return

        current_data = self.load_json()
        current_data[section][field] = data.get("value")
        self.write_json(current_data)

    def add_conversation(self, role, content):
        current_data = self.load_json()
        current_data["conversation"].append({"role": role, "parts": [{"text": content}]})
        # Keep only the latest 20 messages so the file and model context stay small.
        current_data["conversation"] = current_data["conversation"][-20:]
        self.write_json(current_data)

    def extract_info(self, txt):
        
        response = GENAI_CLIENT.models.generate_content(
            model=GEMINI_MODEL,
            config= {

                "system_instruction": (
                INFO_PROMPT
                +"\n\nExisting saved user record (JSON):\n" 
                + json.dumps(self.load_json(), ensure_ascii=False)

                )
            },
            contents=[
                {
                    "role": "user",
                    "parts": [{"text": txt}]
                }
            ]    
        )
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return None


# main part
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

        info = user_memory.extract_info(text)
        if info:
            user_memory.save_json(info)

        saved_data = user_memory.load_json()

        system_instructions = (
                SYSTEM_PROMPT #chat_prompt.txt
                    +"\n\nUser profile and preferences (JSON):\n"
                    + json.dumps(
                        {
                            "profile": saved_data["profile"],
                            "preferences": saved_data["preferences"],
                        },
                        ensure_ascii=False,
                    )
                )

        temp_history = [
                
            *saved_data["conversation"],
            {"role": "user", "parts": [{"text": text}]},
        ]

        typing_task = asyncio.create_task(
            keep_typing(context.bot, update.effective_chat.id)
        )
        try:
            response = await asyncio.to_thread(
                GENAI_CLIENT.models.generate_content,
                model=GEMINI_MODEL,
                config={"system_instruction": system_instructions},
                contents=temp_history
            )
            answer = response.text

            user_memory.add_conversation("user", text)
            user_memory.add_conversation("assistant", answer)
            await update.message.reply_text(answer)
        finally:
            typing_task.cancel()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, generate))

    app.run_polling()


if __name__ == "__main__":
    dotenv.load_dotenv()

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    EMBED_MODEL = os.getenv("GOOGLE_EMBED_MODEL")
    GENAI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    
    main()

