from google import genai
import dotenv
import os
dotenv.load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


while True:
    client = genai.Client(api_key=GEMINI_API_KEY)

    text = input("input:")

    interaction = client.interactions.create(
        model = "gemini-3.6-flash",
        input = text
    )
    print(interaction.output_text)
