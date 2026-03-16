# 🦊 PriceFox

Сервис сравнения цен на российских маркетплейсах.

## Площадки
- 🟣 Wildberries
- 🔵 Ozon  
- 🟡 Яндекс Маркет

## Как использовать
Вставь ссылку с WB или напиши название товара — PriceFox найдёт лучшую цену.

## Локальный запуск

```bash
pip install -r requirements.txt
uvicorn server:app --reload
```

Открой http://localhost:8000

## Деплой на Railway

1. Загрузи код на GitHub
2. Зайди на railway.app
3. New Project → Deploy from GitHub
4. Выбери репозиторий pricefox
5. Готово! 🚀
