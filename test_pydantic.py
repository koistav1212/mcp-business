from services.research.models import ResearchContext

news_item = {
    "title": "Test Title",
    "url": "http://test.com",
    "date": "2024-01-01",
    "snippet": "Test snippet",
    "type": "general"
}

raw_news = [{
    "value": news_item,
    "source_ids": ["news_123"],
    "confidence": 0.9
}]

context = ResearchContext(news=raw_news)
print(context.model_dump().get("news"))
