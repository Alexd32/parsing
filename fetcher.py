import httpx
import random
import asyncio


class Fetcher:
    def __init__(self, proxies=None, headers=None, rate_limit=1.0):
        self.proxies = proxies or []
        self.headers = headers or {}
        self.rate_limit = rate_limit
        self._last_request = 0

        # создаём общий клиент с cookie-jar
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=httpx.Timeout(60.0, connect=30.0),
            follow_redirects=True
        )

        if self.proxies:
            # выбираем случайный прокси
            self.client.proxies = {"all://": random.choice(self.proxies)}

    async def bootstrap(self, url: str):
        """
        Загружает стартовую страницу, чтобы получить cookies и сессию.
        Это полезно для сайтов, которые выдают 401 без предварительного захода.
        """
        try:
            print(f"🌐 Bootstrap: загружаем {url} для инициализации сессии...")
            resp = await self.client.get(url)
            resp.raise_for_status()
            print(f"   ✅ bootstrap успешен, куки получены: {list(self.client.cookies.jar)}")
        except Exception as e:
            print(f"   ⚠️ bootstrap не удался: {e}")

    async def get(self, url: str) -> str:
        """Выполняет GET-запрос с rate-limit и общими cookie"""
        now = asyncio.get_event_loop().time()
        if now - self._last_request < self.rate_limit:
            await asyncio.sleep(self.rate_limit - (now - self._last_request))
        self._last_request = asyncio.get_event_loop().time()

        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.text

    async def close(self):
        """Закрыть клиент при завершении работы"""
        await self.client.aclose()
