import json
import asyncio
import os
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from parser import parse_item
from error_handler import ErrorHandler
from selenium_fetcher import SeleniumFetcher  # <-- используем Selenium

# 🔧 Выбор конфига (раскомментируй нужный)
# CONFIG_PATH = "configs/brushme.json"
CONFIG_PATH = "configs/apteka.json"


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "site").lower()).strip("_")


def parse_selector_and_attr(selector: str):
    if "::attr" in selector:
        css, attr = selector.split("::attr", 1)
        return css.strip(), attr.strip("() ").strip()
    return selector.strip(), None


def build_url(template: str, page: int) -> str:
    if "{page}" not in template:
        return template

    if page == 1:
        url = template
        url = url.replace("/page/{page}/", "/")
        url = url.replace("page-{page}/", "")
        url = url.replace("?page={page}", "")
        url = url.replace("&page={page}", "")
        url = url.replace("{page}", "")
        url = url.replace("://", "§§")
        while "//" in url:
            url = url.replace("//", "/")
        return url.replace("§§", "://")
    else:
        return template.replace("{page}", str(page))


async def run():
    cfg = load_config(CONFIG_PATH)

    # rate_limit (например "1/2s" или "3s")
    rl = cfg["fetch"]["rate_limit"]
    if "/" in rl:
        _, value = rl.split("/")
        rate_limit = float(value.replace("s", ""))
    else:
        rate_limit = float(rl.replace("s", ""))

    headers = cfg["fetch"].get("headers", {})
    user_agent = headers.get("User-Agent")

    # SeleniumFetcher как единая сессия браузера
    fetcher = SeleniumFetcher(
        rate_limit=rate_limit,
        user_agent=user_agent,
        headless=True,  # при необходимости можно выключить
        accept_language=headers.get("Accept-Language", "ru-RU,ru;q=0.9,en;q=0.8"),
        page_load_timeout=60,
    )
    error_handler = ErrorHandler(retries=2, backoff=4)  # retries поменьше: браузер «тяжёлый»

    list_cfg = cfg["selectors"]["list_page"]
    item_fields = cfg["selectors"]["item_page"]["fields"]
    base_url = (cfg.get("base_url") or f"https://{cfg['domain']}").rstrip("/") + "/"

    out_file_path = f"results_{slugify(cfg.get('name', 'site'))}.txt"
    first_write = not os.path.exists(out_file_path)
    header_fields = list(item_fields.keys()) + ["url", "timestamp"]

    css_item_link, attr_item_link = parse_selector_and_attr(list_cfg["item_link"])

    # CSS, который должен появиться на странице каталога (чтобы понять, что товары прогрузились)
    catalog_wait_css = list_cfg.get("wait_css") or css_item_link

    try:
        with open(out_file_path, "a", encoding="utf-8") as out_file:
            if first_write:
                out_file.write(";".join(header_fields) + "\n")

            for page in range(1, 500):
                url = build_url(list_cfg["url"], page)
                print(f"📄 Каталог: {url}")

                # ждём появления карточек по CSS
                html = await error_handler.handle(
                    lambda u: fetcher.get(u, wait_css=catalog_wait_css, timeout=40),
                    url
                )
                if not html:
                    print(f"⛳ Стоп: не удалось загрузить страницу {url}")
                    break

                soup = BeautifulSoup(html, "lxml")
                nodes = soup.select(css_item_link)
                if not nodes:
                    if page == 1:
                        print("❌ На первой странице нет товаров (проверь item_link/wait_css).")
                    else:
                        print("⛳ Пустая страница, конец каталога.")
                    break

                links = []
                for node in nodes:
                    href = node.get(attr_item_link) if attr_item_link else node.get("href")
                    if href:
                        links.append(urljoin(base_url, href))

                print(f"  найдено {len(links)} ссылок")

                for link in links:
                    html_item = await error_handler.handle(
                        lambda u: fetcher.get(u, wait_css=None, timeout=40),
                        link
                    )
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
    finally:
        await fetcher.close()


if __name__ == "__main__":
    asyncio.run(run())
