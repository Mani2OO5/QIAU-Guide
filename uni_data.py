import os
import hashlib
import mimetypes
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag


OUTPUT_DIR = "uni_data"
PAGES_DIR = os.path.join(OUTPUT_DIR, "pages")
FILES_DIR = os.path.join(OUTPUT_DIR, "files")

HEADERS = {"user-agent": "Mozilla/5.0 (QIAU-GuideBot/1.0)"}

visited_pages = set()
downloaded_files = set()

RESOURCE_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".mp4", ".mkv", ".mp3", ".wav",
    ".rar", ".txt", ".json", ".xml",
)


def get_filename(url, content_type=None):
    path = urlparse(url).path
    filename = os.path.basename(path)

    if not filename:
        filename = "file"

    if "." not in filename and content_type:
        extension = mimetypes.guess_extension(content_type.split(";")[0])

        if extension:
            filename += extension

    return filename
    
def download_file(url):
    if url in downloaded_files:
        return
    try:
        response = requests.get(url, headers=HEADERS,timeout=30, stream=True)
        if response.status_code != 200:
            return
        content_type = response.headers.get("Content-Type", "")
        filename = get_filename(url, content_type)

        name, ext = os.path.splitext(filename)
        file_id = hashlib.md5(url.encode()).hexdigest()[:8]

        filename = f"{name}_{file_id}{ext}"

        output_path = os.path.join(FILES_DIR, filename)
        os.makedirs(FILES_DIR, exist_ok=True)

        print("FILES:", url)
        print("SAVE:", output_path)

        with open(output_path, "wb") as file:
            for chunk in response.iter_content(chunk_size= 64 * 1024):
                if chunk:
                    file.write(chunk)

        downloaded_files.add(url)

    except Exception as e:
        print("FILE ERROR", url)
        print(e)

def process_resource(url):
    url, _ = urldefrag(url)
    if not url:
        return
    try:
        response = requests.head(url,headers=HEADERS,timeout=10,allow_redirects=True)
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and "text/html" not in content_type:
            download_file(url)

    except requests.RequestException:
        path = urlparse(url).path.lower()

        if path.endswith(RESOURCE_EXTENSIONS):
            download_file(url)

def crawl(url, domain):
    url, _ = urldefrag(url)
    if url in visited_pages:
        return

    visited_pages.add(url)
    print("\nPAGE:", url)

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            print("PAGE_FIELD:", response.status_code)
            return
        
        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" not in content_type:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n", strip=True)

        page_id = hashlib.md5(url.encode()).hexdigest()[:10]
        page_file = os.path.join(PAGES_DIR, f"{page_id}.txt")
        os.makedirs(PAGES_DIR, exist_ok=True)

        with open(page_file, "w", encoding="utf-8") as file:
            file.write(f"URL: {url}\n\n")
            file.write(text)

        links = set()

        for tag in soup.find_all("a", href=True):
            links.add(urljoin(url, tag["href"]))

        for tag in soup.find_all("img", src=True):
            links.add(urljoin(url, tag["src"]))

        for tag in soup.find_all("video", src=True):
            links.add(urljoin(url, tag["src"]))

        for tag in soup.find_all("source", src=True):
            links.add(urljoin(url, tag["src"]))

        for tag in soup.find_all("iframe", src=True):
            links.add(urljoin(url, tag["src"]))

        for link in links:

            link, _ = urldefrag(link)

            parsed = urlparse(link)

            if parsed.scheme not in {"http", "https"} or parsed.netloc != domain:
                continue

            path = parsed.path.lower()

            if path.endswith(RESOURCE_EXTENSIONS):
                process_resource(link)
                continue

            crawl(link, domain)

    except requests.RequestException as e:
        print("PAGE ERROR:", url, e)



def get_uni_data(url):
    visited_pages.clear()
    downloaded_files.clear()
    os.makedirs(PAGES_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)

    domain = urlparse(url).netloc
    crawl(url, domain)

    print("\n=============================")
    print("CRAWLING FINISHED")
    print("=============================")
    print("Pages:", len(visited_pages))
    print("Files:", len(downloaded_files))


if __name__ == "__main__":
    get_uni_data("https://qazvin.iau.ir")
