import random
from pathlib import Path


MOTIVATION_DIR = Path(__file__).resolve().parent / "motivation"

MOTIVATION_ITEMS = [
    {
        "image": "1.jpg",
        "text": "🌸 Пусть сегодня все важные страницы спокойно индексируются",
        "emoji": "🌸",
    },
    {
        "image": "2.jpg",
        "text": "✨ Один исправленный title уже делает сайт понятнее для клиента",
        "emoji": "✨",
    },
    {
        "image": "3.jpg",
        "text": "🔎 Проверьте sitemap.xml, а потом обязательно сделайте маленький перерыв",
        "emoji": "🔎",
    },
    {
        "image": "4.jpg",
        "text": "🌿 Хорошее SEO любит порядок, но не требует спешки",
        "emoji": "🌿",
    },
    {
        "image": "5.jpg",
        "text": "🚀 Пусть сегодня crawler найдет только приятные улучшения",
        "emoji": "🚀",
    },
    {
        "image": "6.jpg",
        "text": "🧭 Начните с одной критичной ошибки, остальное подождет",
        "emoji": "🧭",
    },
    {
        "image": "7.jpg",
        "text": "💡 Чистый robots.txt делает путь поисковиков спокойнее",
        "emoji": "💡",
    },
    {
        "image": "8.jpg",
        "text": "🌙 Даже SEO-специалисту нужен отдых, чтобы видеть главное",
        "emoji": "🌙",
    },
    {
        "image": "1.jpg",
        "text": "🌼 Пусть description сегодня звучит тепло, ясно и по делу",
        "emoji": "🌼",
    },
    {
        "image": "2.jpg",
        "text": "🛠 Маленькая правка canonical может спасти большой кусочек SEO-веса",
        "emoji": "🛠",
    },
    {
        "image": "3.jpg",
        "text": "☕ Сначала аудит, потом чай: обе вещи помогают думать лучше",
        "emoji": "☕",
    },
    {
        "image": "4.jpg",
        "text": "🌱 Сайт растет спокойнее, когда ошибки разложены по приоритетам",
        "emoji": "🌱",
    },
    {
        "image": "5.jpg",
        "text": "📈 Пусть каждая проверка приближает сайт к более сильной видимости",
        "emoji": "📈",
    },
    {
        "image": "6.jpg",
        "text": "🫶 Если ошибок много, выберите одну. Это уже движение вперед",
        "emoji": "🫶",
    },
    {
        "image": "7.jpg",
        "text": "🌤 Пусть сегодня не будет битых ссылок и лишней суеты",
        "emoji": "🌤",
    },
    {
        "image": "8.jpg",
        "text": "🎯 Хороший H1 говорит клиенту: вы попали туда, куда нужно",
        "emoji": "🎯",
    },
]


def get_random_motivation():
    item = random.choice(MOTIVATION_ITEMS)
    return {
        **item,
        "image_path": str(MOTIVATION_DIR / item["image"]),
    }
