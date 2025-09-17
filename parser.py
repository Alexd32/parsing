from bs4 import BeautifulSoup
from datetime import datetime

def extract_text(soup, selector: str):
    """
    Возвращает текст или атрибут по селектору.
    Поддерживает "sel::attr(name)" и несколько селекторов через запятую.
    """
    if not selector:
        return None

    # поддержка нескольких селекторов
    for sel in [s.strip() for s in selector.split(",")]:
        if "::attr" in sel:
            css, attr = sel.split("::attr")
            node = soup.select_one(css.strip())
            if node and node.has_attr(attr.strip("()")):
                return node[attr.strip("()")].strip()
        else:
            node = soup.select_one(sel)
            if node and node.text.strip():
                return node.text.strip()
    return None

def parse_item(html: str, field_selectors: dict, url: str):
    soup = BeautifulSoup(html, "lxml")
    data = {}

    for field, selector in field_selectors.items():
        value = extract_text(soup, selector)

        # нормализация цены
        if field == "price" and value:
            value = value.replace("\xa0", "").replace(" ", "")
            value = value.replace("руб.", "").replace("₽", "").strip()

        data[field] = value

    data["url"] = url
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data
