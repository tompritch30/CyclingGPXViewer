import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.routes.cc"
OUTPUT_DIR = "gpx_downloads"

os.makedirs(OUTPUT_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/116.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}


def get_route_links(list_url):
    r = requests.get(list_url, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("/routes/"):
            full_url = urljoin(BASE_URL, a["href"])
            links.append(full_url)
    return list(set(links))  # deduplicate

def get_gpx_link(route_url):
    r = requests.get(route_url, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    # Look for anchor/button with "Download GPX"
    gpx_link = None
    for a in soup.find_all("a", href=True):
        if a["href"].endswith(".gpx"):
            gpx_link = urljoin(BASE_URL, a["href"])
            break
    return gpx_link

def download_gpx(gpx_url, route_name):
    filename = route_name.replace(" ", "_") + ".gpx"
    path = os.path.join(OUTPUT_DIR, filename)
    r = requests.get(gpx_url, headers=headers)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)
    print(f"Downloaded: {path}")

def scrape_routes(start_url):
    route_links = get_route_links(start_url)
    print(f"Found {len(route_links)} routes")

    for link in route_links:
        print(f"Processing {link}")
        gpx_link = get_gpx_link(link)
        if gpx_link:
            route_name = link.rstrip("/").split("/")[-1]
            download_gpx(gpx_link, route_name)
            time.sleep(1)  # polite delay
        else:
            print("No GPX link found")

if __name__ == "__main__":
    # start page (main routes list)
    scrape_routes("https://www.routes.cc/")
