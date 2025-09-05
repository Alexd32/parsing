from bs4 import BeautifulSoup
from datetime import datetime

def extract_text(soup, selector: str):
    if "::attr" in selector:
        sel, attr = selector.split("::attr")
        node = soup.select_one(sel.strip())
        return node.get(attr.strip("()")) if node else None
    node = soup.select_one(selector)
    return node.text.strip() if node else None

def parse_item(html: str, field_selectors: dict, url: str):
    soup = BeautifulSoup(html, "lxml")
    data = {}
    for field, selector in field_selectors.items():
        data[field] = extract_text(soup, selector)
    data["url"] = url
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data
