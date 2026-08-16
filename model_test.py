from ollama import chat
from data_proccess import embedding_search
import dotenv
import os
import json

dotenv.load_dotenv()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

with open("prompt/chat_prompt.txt", "r", encoding="utf-8") as file:
    SYSTEM_PROMPT = file.read()

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


def response(query):

    saved_data = {
        "profile": {},
        "preferences": {}
    }
    print("start embedding search")
    data = embedding_search(query)
    print("embedding search finished")
    print("start answering the question")
    response = chat(
        model=OLLAMA_MODEL,
        messages=[
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
            {"role": "user", "content": f"data: {data}"},
            {"role": "user", "content": query},
        ],

    )

    return response.message.content



print(response("ایا نیمسال آموزشیار تغییر کرد، اگه آره نیمسال جدید عددش چنده"))
