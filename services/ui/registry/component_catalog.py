COMPONENT_CATALOG = {
    "ExecutiveHero": {
        "category": "identity",
        "min_data_requirements": [
            "entity.entity.name",
        ],
        "supports_images": True,
        "max_per_page": 1,
    },
    "MetricStrip": {
        "category": "metrics",
        "minimum_metrics": 3,
        "maximum_metrics": 5,
        "max_per_page": 1,
    },
    "PlatformStackMap": {
        "category": "architecture",
        "requires_any": [
            "entity.products",
            "entity.services",
            "entity.solutions",
        ],
        "max_per_page": 1,
    },
    "BrandPortfolioMap": {
        "category": "portfolio",
        "requires": [
            "entity.subsidiaries_or_brands",
        ],
        "minimum_items": 4,
    },
    "IndustryExposureMatrix": {
        "category": "industry",
        "requires": [
            "entity.solutions.industries",
        ],
        "minimum_items": 4,
    },
    "StrategicPositionCard": {
        "category": "strategy",
        "requires_any": [
            "profile.overview",
            "entity.products",
            "entity.services",
        ],
    },
    "FactMatrix": {
        "category": "identity",
        "minimum_facts": 4,
    },
    "ExecutiveTakeaway": {
        "category": "narrative",
        "max_words": 60,
        "max_per_page": 1,
    },
    "BusinessArchitectureMap": {
        "category": "architecture",
        "requires_any": [
            "entity.products",
            "entity.services",
            "entity.solutions",
            "profile.overview"
        ]
    }
}
