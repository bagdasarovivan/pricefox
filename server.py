from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx
import asyncio
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def extract_wb_article(url: str):
    """Извлекаем артикул из ссылки WB"""
    match = re.search(r'catalog/(\d+)', url)
    return match.group(1) if match else None


async def parse_wildberries(query: str, client: httpx.AsyncClient):
    """Парсим Wildberries"""
    try:
        # Если это ссылка — получаем данные по артикулу
        if "wildberries.ru" in query or "wb.ru" in query:
            article = extract_wb_article(query)
            if article:
                url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&nm={article}"
                resp = await client.get(url, headers=HEADERS, timeout=10)
                data = resp.json()
                products = data.get("data", {}).get("products", [])
                if products:
                    p = products[0]
                    price = p.get("salePriceU", 0) // 100
                    old_price = p.get("priceU", 0) // 100
                    return [{
                        "platform": "wb",
                        "name": p.get("name", ""),
                        "price": price,
                        "oldPrice": old_price if old_price > price else None,
                        "rating": p.get("rating", 0),
                        "reviews": p.get("feedbacks", 0),
                        "delivery": "1-2 дня",
                        "url": f"https://www.wildberries.ru/catalog/{article}/detail.aspx"
                    }]

        # Поиск по названию
        search_url = "https://search.wb.ru/exactmatch/ru/common/v9/search"
        params = {
            "query": query,
            "resultset": "catalog",
            "limit": 5,
            "sort": "popular",
            "curr": "rub",
            "dest": "-1257786",
        }
        resp = await client.get(search_url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()
        products = data.get("data", {}).get("products", [])

        results = []
        for p in products[:3]:
            price = p.get("salePriceU", 0) // 100
            old_price = p.get("priceU", 0) // 100
            article_id = p.get("id", "")
            results.append({
                "platform": "wb",
                "name": p.get("name", ""),
                "price": price,
                "oldPrice": old_price if old_price > price else None,
                "rating": p.get("rating", 0),
                "reviews": p.get("feedbacks", 0),
                "delivery": "1-2 дня",
                "url": f"https://www.wildberries.ru/catalog/{article_id}/detail.aspx"
            })
        return results

    except Exception as e:
        print(f"WB error: {e}")
        return []


async def parse_ozon(query: str, client: httpx.AsyncClient):
    """Парсим Ozon через их поисковый API"""
    try:
        # Если ссылка на Ozon
        if "ozon.ru" in query:
            return []

        url = "https://api.ozon.ru/composer-api.bx/page/json/v2"
        params = {
            "url": f"/search/?text={query}&sorting=score"
        }
        headers = {
            **HEADERS,
            "x-o3-app-name": "ozonapp_android",
            "x-o3-app-version": "16.0.0",
        }
        resp = await client.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()

        results = []
        # Ищем товары в ответе
        items = []
        def find_items(obj):
            if isinstance(obj, dict):
                if obj.get("component") == "searchResultsV2":
                    items.extend(obj.get("items", []))
                for v in obj.values():
                    find_items(v)
            elif isinstance(obj, list):
                for i in obj:
                    find_items(i)

        find_items(data)

        for item in items[:3]:
            price_str = item.get("price", "0")
            price = int(re.sub(r'\D', '', str(price_str))) if price_str else 0
            old_price_str = item.get("oldPrice", "")
            old_price = int(re.sub(r'\D', '', str(old_price_str))) if old_price_str else None

            results.append({
                "platform": "ozon",
                "name": item.get("name", ""),
                "price": price,
                "oldPrice": old_price if old_price and old_price > price else None,
                "rating": item.get("rating", 0),
                "reviews": item.get("reviews", 0),
                "delivery": "2-3 дня",
                "url": "https://ozon.ru" + item.get("action", {}).get("link", "")
            })
        return results

    except Exception as e:
        print(f"Ozon error: {e}")
        return []


async def parse_yandex_market(query: str, client: httpx.AsyncClient):
    """Парсим Яндекс Маркет"""
    try:
        url = "https://market.yandex.ru/api/search"
        params = {
            "text": query,
            "cvredirect": 1,
            "local-offers-first": 0,
        }
        headers = {
            **HEADERS,
            "Accept": "application/json, text/plain, */*",
        }
        resp = await client.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()

        results = []
        products = data.get("results", [])

        for p in products[:3]:
            price = p.get("prices", {}).get("min", 0)
            old_price = p.get("prices", {}).get("max", 0)
            results.append({
                "platform": "ym",
                "name": p.get("name", ""),
                "price": int(price) if price else 0,
                "oldPrice": int(old_price) if old_price and int(old_price) > int(price or 0) else None,
                "rating": p.get("rating", {}).get("value", 0),
                "reviews": p.get("rating", {}).get("count", 0),
                "delivery": "1-3 дня",
                "url": p.get("url", "https://market.yandex.ru")
            })
        return results

    except Exception as e:
        print(f"YM error: {e}")
        return []


async def parse_aliexpress(query: str, client: httpx.AsyncClient):
    """Парсим AliExpress"""
    try:
        url = "https://www.aliexpress.com/ajax/search.htm"
        params = {
            "SearchText": query,
            "SortType": "default",
            "CatId": 0,
            "page": 1,
        }
        headers = {
            **HEADERS,
            "Referer": "https://www.aliexpress.com",
        }
        resp = await client.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()

        results = []
        items = data.get("mods", {}).get("itemList", {}).get("content", [])

        for item in items[:3]:
            price_info = item.get("prices", {})
            price_str = price_info.get("salePrice", {}).get("minPrice", "0")
            try:
                price = int(float(str(price_str).replace(",", ".")) * 90)  # USD to RUB примерно
            except:
                price = 0

            results.append({
                "platform": "ali",
                "name": item.get("title", {}).get("displayTitle", ""),
                "price": price,
                "oldPrice": None,
                "rating": item.get("evaluation", {}).get("starRating", 0),
                "reviews": item.get("evaluation", {}).get("totalValidNum", 0),
                "delivery": "15-30 дней",
                "url": "https:" + item.get("productDetailUrl", "//aliexpress.com")
            })
        return results

    except Exception as e:
        print(f"AliExpress error: {e}")
        return []


async def parse_avito(query: str, client: httpx.AsyncClient):
    """Парсим Авито"""
    try:
        url = "https://www.avito.ru/api/11/items"
        params = {
            "query": query,
            "locationId": 637640,  # Россия
            "limit": 5,
            "offset": 0,
        }
        headers = {
            **HEADERS,
            "Authorization": "Bearer v.1.avito.public",
        }
        resp = await client.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()

        results = []
        items = data.get("items", []) or []

        for item in items[:3]:
            price = item.get("price", {}).get("value", {}).get("raw", 0)
            results.append({
                "platform": "avito",
                "name": item.get("title", ""),
                "price": int(price) if price else 0,
                "oldPrice": None,
                "rating": 0,
                "reviews": 0,
                "delivery": "Самовывоз/доставка",
                "url": "https://avito.ru" + item.get("urlPath", "")
            })
        return results

    except Exception as e:
        print(f"Avito error: {e}")
        return []


async def parse_megamarket(query: str, client: httpx.AsyncClient):
    """Парсим Мегамаркет (СберМегаМаркет)"""
    try:
        url = "https://megamarket.ru/api/mobile/v1/catalogService/catalog/search"
        payload = {
            "requestVersion": 10,
            "text": query,
            "limit": 5,
            "offset": 0,
            "sorting": 1,
        }
        headers = {
            **HEADERS,
            "Content-Type": "application/json",
        }
        resp = await client.post(url, json=payload, headers=headers, timeout=10)
        data = resp.json()

        results = []
        items = data.get("items", []) or []

        for item in items[:3]:
            price = item.get("salePriceU", 0) // 100 if item.get("salePriceU") else item.get("finalPrice", 0)
            old_price = item.get("regularPriceU", 0) // 100 if item.get("regularPriceU") else 0
            goods_id = item.get("goodsId", "")

            results.append({
                "platform": "mega",
                "name": item.get("name", ""),
                "price": int(price) if price else 0,
                "oldPrice": int(old_price) if old_price and old_price > price else None,
                "rating": item.get("rating", 0),
                "reviews": item.get("reviewsCount", 0),
                "delivery": "1-3 дня",
                "url": f"https://megamarket.ru/catalog/details/{goods_id}/"
            })
        return results

    except Exception as e:
        print(f"Megamarket error: {e}")
        return []


@app.get("/search")
async def search(q: str, platforms: str = "wb,ozon,ym"):
    """Главный эндпоинт поиска"""
    platform_list = platforms.split(",")
    results = []

    async with httpx.AsyncClient() as client:
        tasks = []
        if "wb" in platform_list:
            tasks.append(parse_wildberries(q, client))
        if "ozon" in platform_list:
            tasks.append(parse_ozon(q, client))
        if "ym" in platform_list:
            tasks.append(parse_yandex_market(q, client))
        if "ali" in platform_list:
            tasks.append(parse_aliexpress(q, client))
        if "avito" in platform_list:
            tasks.append(parse_avito(q, client))
        if "mega" in platform_list:
            tasks.append(parse_megamarket(q, client))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in all_results:
            if isinstance(r, list):
                results.extend(r)

    # Сортируем по цене
    results = [r for r in results if r.get("price", 0) > 0]
    results.sort(key=lambda x: x["price"])

    return {"results": results, "query": q}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "PriceFox 🦊"}


# Раздаём статику (index.html)
app.mount("/", StaticFiles(directory=".", html=True), name="static")
