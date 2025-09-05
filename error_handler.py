import asyncio
import httpx

class ErrorHandler:
    def __init__(self, retries=3, backoff=3):
        """
        retries — сколько раз пробовать
        backoff — множитель задержки между попытками
        """
        self.retries = retries
        self.backoff = backoff

    async def handle(self, coro, url: str):
        """
        coro — асинхронная функция, например fetcher.get
        url — адрес страницы
        """
        for attempt in range(1, self.retries + 1):
            try:
                return await coro(url)  # пробуем
            except httpx.ConnectTimeout:
                print(f"⏱ Таймаут подключения ({url}), попытка {attempt}")
            except httpx.ReadTimeout:
                print(f"📭 Сервер не ответил вовремя ({url}), попытка {attempt}")
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                if code in (500, 502, 503, 504):
                    print(f"⚠️ Ошибка сервера {code} ({url}), попытка {attempt}")
                elif code == 404:
                    print(f"❌ Страница {url} не найдена (404), пропускаем")
                    return None
                else:
                    print(f"⚠️ HTTP {code} ({url}), попытка {attempt}")
            except Exception as e:
                print(f"❌ Неожиданная ошибка для {url}: {e}")

            if attempt < self.retries:
                wait_time = self.backoff * attempt
                print(f"⏳ Ждём {wait_time} сек и повторяем...")
                await asyncio.sleep(wait_time)

        print(f"🚫 Все {self.retries} попытки исчерпаны для {url}")
        return None
