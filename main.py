import json
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from fetcher import Fetcher
from parser import parse_item
from error_handler import ErrorHandler
import os


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_proxies(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []


def build_url(base_url: str, page: int) -> str:
    """Строим URL для страницы каталога"""
    if page == 1:
        return base_url.replace("/page/{page}/", "") + "/"
    return base_url.format(page=page)


async def run():
    cfg = load_config("configs/brushme.json")
    proxies = load_proxies("proxies.txt") if cfg["technologies"].get("proxy", False) else []

    # разбор rate_limit: "1/3s" или "3s"
    rl = cfg["fetch"]["rate_limit"]
    if "/" in rl:
        _, value = rl.split("/")
        rate_limit = float(value.replace("s", ""))
    else:
        rate_limit = float(rl.replace("s", ""))

    headers = cfg["fetch"].get("headers")
    fetcher = Fetcher(proxies, headers, rate_limit)
    error_handler = ErrorHandler(retries=3, backoff=3)

    list_cfg = cfg["selectors"]["list_page"]
    item_fields = cfg["selectors"]["item_page"]["fields"]
    base_url = cfg.get("base_url") or f"https://{cfg['domain']}"

    out_file_path = "results.txt"
    first_write = not os.path.exists(out_file_path)
    header_fields = list(item_fields.keys()) + ["url", "timestamp"]

    with open(out_file_path, "a", encoding="utf-8") as out_file:
        if first_write:
            out_file.write(";".join(header_fields) + "\n")

        # обходим страницы до пустой
        for page in range(1, 500):
            url = build_url(list_cfg["url"], page)
            print(f"📄 Каталог: {url}")

            html = await error_handler.handle(fetcher.get, url)
            if not html:
                print(f"⛳ Стоп: не удалось загрузить страницу {url}")
                break

            soup = BeautifulSoup(html, "lxml")
            nodes = soup.select("a.woocommerce-LoopProduct-link")
            if not nodes:
                if page == 1:
                    print("❌ На первой странице нет товаров.")
                else:
                    print("⛳ Пустая страница, конец каталога.")
                break

            links = []
            for a in nodes:
                href = a.get("href")
                if href:
                    full = href if href.startswith("http") else urljoin(base_url + "/", href)
                    links.append(full)

            print(f"  найдено {len(links)} ссылок")

            for link in links:
                html_item = await error_handler.handle(fetcher.get, link)
                if not html_item:
                    print(f"    ⚠️ Пропуск карточки {link}")
                    continue
                try:
                    item = parse_item(html_item, item_fields, link)
                    line = ";".join((item.get(field, "") or "").replace("\n", " ").strip() for field in header_fields)
                    out_file.write(line + "\n")
                    out_file.flush()
                    print(f"    ✅ {item.get('title') or link}")
                except Exception as e:
                    print(f"    ❌ Ошибка при парсинге {link}: {e}")


if __name__ == "__main__":
    asyncio.run(run())
