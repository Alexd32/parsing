import httpx
import random
import asyncio

class Fetcher:
    def __init__(self, proxies=None, headers=None, rate_limit=1.0):
        self.proxies = proxies or []
        self.headers = headers or {}
        self.rate_limit = rate_limit
        self._last_request = 0

    def _choose_proxy(self):
        return random.choice(self.proxies) if self.proxies else None

    async def get(self, url: str) -> str:
        """Выполняет один HTTP-запрос, без повторов — только базовый fetch"""
        now = asyncio.get_event_loop().time()
        if now - self._last_request < self.rate_limit:
            await asyncio.sleep(self.rate_limit - (now - self._last_request))
        self._last_request = asyncio.get_event_loop().time()

        proxy = self._choose_proxy()
        timeout = httpx.Timeout(60.0, connect=30.0)

        async with httpx.AsyncClient(proxy=proxy, headers=self.headers, timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
