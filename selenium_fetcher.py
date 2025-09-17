import asyncio
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SeleniumFetcher:
    """
    Устойчивая обёртка над Selenium (Chrome):
    - единая сессия браузера с cookies
    - rate-limit между запросами
    - page_load_strategy='eager' (быстрее и меньше зависаний)
    - авто-клик по cookie/region попапам
    - возврат page_source даже при таймауте ожиданий
    """

    def __init__(
        self,
        rate_limit: float = 1.0,
        user_agent: Optional[str] = None,
        headless: bool = True,
        accept_language: str = "ru-RU,ru;q=0.9,en;q=0.8",
        page_load_timeout: int = 60,
        implicit_wait: int = 0,
    ):
        self.rate_limit = rate_limit
        self._last_request = 0.0

        opts = Options()
        # стабилизирующие флаги для Windows headless
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-software-rasterizer")
        opts.add_argument("--enable-unsafe-swiftshader")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--window-size=1366,900")
        opts.add_argument("--lang=" + accept_language.split(",")[0])
        if user_agent:
            opts.add_argument(f"--user-agent={user_agent}")

        # грузим DOM без ожидания всех ресурсов
        opts.page_load_strategy = "eager"

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=opts)
        self.driver.set_page_load_timeout(page_load_timeout)
        if implicit_wait:
            self.driver.implicitly_wait(implicit_wait)

    async def _rate_limit(self):
        now = time.perf_counter()
        delta = now - self._last_request
        if delta < self.rate_limit:
            await asyncio.sleep(self.rate_limit - delta)
        self._last_request = time.perf_counter()

    def _wait_dom_ready(self, timeout: int):
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
            )
        except TimeoutException:
            # оставляем как есть — всё равно попробуем отдать page_source
            pass

    def _click_if_exists(self, by: By, selector: str) -> bool:
        try:
            el = self.driver.find_element(by, selector)
            el.click()
            return True
        except Exception:
            return False

    def _try_close_popups(self):
        """Пробуем закрыть баннеры cookies/подтверждение города/общие модалки."""
        # 1) cookie-баннеры
        candidates_css = [
            "button.cookie-accept", "button#cookie-accept", "button[data-accept]",
            ".cookie .btn-accept", ".cookies__accept", "button[onclick*='cookie']",
            "button[aria-label*='Принять']", "button:contains('Принять')"
        ]
        for css in candidates_css:
            if self._click_if_exists(By.CSS_SELECTOR, css):
                break

        # 2) попап города/подтверждение
        city_btn_css = [
            "button[class*='confirm']", "button[class*='accept']",
            ".modal [type='button'].btn-primary", ".region-confirm__actions .button",
        ]
        for css in city_btn_css:
            if self._click_if_exists(By.CSS_SELECTOR, css):
                break

        # 3) универсальный клик по кнопкам с нужным текстом (через JS)
        js = """
        const texts = ['Принять','Согласен','Да, верно','Хорошо','Понятно','Ок','OK'];
        const btns = Array.from(document.querySelectorAll('button, a[role="button"], .btn, .button'));
        for (const b of btns) {
            const t = (b.innerText || b.textContent || '').trim();
            if (t && texts.some(x => t.toLowerCase().includes(x.toLowerCase()))) { b.click(); return true; }
        }
        return false;
        """
        try:
            self.driver.execute_script(js)
        except Exception:
            pass

    def _ensure_visible_content(self):
        """Небольшой скролл, чтобы триггерить ленивую подгрузку (если есть)."""
        try:
            self.driver.execute_script("window.scrollBy(0, 300);")
        except Exception:
            pass

    def _sync_get(self, url: str, wait_css: Optional[str], timeout: int) -> str:
        try:
            self.driver.get(url)
        except TimeoutException:
            # проигнорируем, возьмём то, что есть
            pass
        except WebDriverException:
            # попробуем «мягко» перезайти
            try:
                self.driver.get(url)
            except Exception:
                pass

        # DOM готов?
        self._wait_dom_ready(timeout=timeout)

        # закрыть попапы (если есть)
        self._try_close_popups()
        self._ensure_visible_content()

        # дождаться ключевых элементов каталога/карточки (если задано)
        if wait_css:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, wait_css))
                )
            except TimeoutException:
                # не критично — продолжим с тем, что есть
                pass

        # отдаём HTML в любом случае
        try:
            return self.driver.page_source
        except Exception:
            return ""

    async def get(self, url: str, wait_css: Optional[str] = None, timeout: int = 30) -> str:
        await self._rate_limit()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_get, url, wait_css, timeout)

    async def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass
