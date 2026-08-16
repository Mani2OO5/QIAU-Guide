import json
import chromadb
from ollama import embed
from datetime import datetime

EMBEDDING_MODEL = "aligh4699/heydariAI-persian-embeddings"


def build_vector_database(data):

    print(f"total messages: {len(data)}")

    # create chromadb

    client = chromadb.PersistentClient(path="uni_data/chroma_db")

    collection = client.get_or_create_collection(name="telegram_messages")

    documents = []
    ids = []

    for item in data:
        text = item.get("text", "").strip()

        # remove "text":""
        if not text:
            continue

        documents.append(text)
        ids.append(str(item["message_id"]))

    BATCH_SIZE = 100

    # Save data in chromadb
    for start in range(0, len(documents), BATCH_SIZE):
        end = start + BATCH_SIZE

        batch_documents = documents[start:end]
        batch_ids = ids[start:end]

        response = embed(model=EMBEDDING_MODEL, input=batch_documents)

        embeddings = response["embeddings"]

        collection.add(ids=batch_ids, documents=batch_documents, embeddings=embeddings)

        print(f"{min(end, len(documents))}/ {len(documents)}")

    print("Vector database created successfully")


def update_vector_database(data):

    client = chromadb.PersistentClient(path="uni_data/chroma_db")
    collection = client.get_or_create_collection(name="telegram_messages")

    print(f"Total message in JSON: {len(data)}")

    existing_ids = set(collection.get()["ids"])

    new_data = []

    for item in data:
        message_id = str(item["message_id"])

        if message_id not in existing_ids:
            new_data.append(item)

    print(f"new messages: {len(new_data)}")

    documents = []
    ids = []

    for item in new_data:
        text = item.get("text", "").strip()

        if not text:
            continue

        documents.append(text)
        ids.append(str(item["message_id"]))

    print(f"Messages to embed: {len(documents)}")

    if not documents:
        print("No messages to embed.")
        return

    BATCH_SIZE = 100

    # Save data in chromadb
    for start in range(0, len(documents), BATCH_SIZE):
        end = start + BATCH_SIZE

        batch_documents = documents[start:end]
        batch_ids = ids[start:end]

        response = embed(model=EMBEDDING_MODEL, input=batch_documents)
        embeddings = response["embeddings"]

        collection.add(ids=batch_ids, documents=batch_documents, embeddings=embeddings)
        print(f"{min(end, len(documents))}/ {len(documents)}")


def weight(date):
    date_obj = datetime.fromisoformat(date)
    time_stamp = date_obj.timestamp()
    weight = int(time_stamp) / 10000000000

    return weight


def clean_json(data):
    messages = data["messages"]

    output = []
    for message in messages:
        message_id = message["id"]
        date = message["date"]

        text = ""
        if isinstance(message["text"], str):
            text = message["text"]

        else:
            for item in message["text"]:
                if isinstance(item, str):
                    text += item
                else:
                    text += item["text"]
        file = False
        file_type = None
        if "media_type" in message:
            file = True
            file_type = message["media_type"]

        elif "photo" in message:
            file = True
            file_type = "photo"

        elif "file" in message:
            file = True
            file_type = message["file"]

        new_message = {
            "message_id": message_id,
            "weight": weight(date),
            "date": date,
            "file": file,
            "file_type": file_type,
            "text": text,
        }

        output.append(new_message)

    output_file = "uni_data/clean_messages.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"{len(output)} messages saved.")


def embedding_search(query, n_results=5):
    client = chromadb.PersistentClient(path="uni_data/chroma_db")
    collection = client.get_collection(name="telegram_messages")

    response = embed(model=EMBEDDING_MODEL, input=query)
    query_embedding = response["embeddings"][0]

    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)

    return results


def keyword_search(query, data):
    results = []

    text = query.split()

    for item in data:
        score = 0

        for word in text:
            if word in item["text"]:
                score += 1

        if score > 0:
            results.append(item)

    return results

def merge_results(embedding_results, keyword_results):

    pass




if __name__ == "__main__":

    with open("uni_data/result.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # clean_json(data)

    with open("uni_data/clean_messages.json", "r", encoding="utf-8") as f:
        cleaned_data = json.load(f)

    print("data cleaned.")

    # just when we have new data
    # build_vector_database(cleaned_data)

    #update_vector_database(cleaned_data)

    print("start")
    print(embedding_search("نمرات درس گرافیک کی ثبت شد؟"))
