import json
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "config/feed-portfolio.json"

with open(path, "r") as f:
    feeds = json.load(f)

new_feeds = [
    {
        "name": "Frontiers in Physics (Biophysics)",
        "url": "https://www.frontiersin.org/journals/physics/rss",
        "priority": 5,
        "headline_mode": "preserve",
        "publisher": "Frontiers",
        "authority": "primary",
        "categories": ["quantum biology", "biophysics", "brain health"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "Light: Science & Applications",
        "url": "https://www.nature.com/lsa.rss",
        "priority": 5,
        "headline_mode": "preserve",
        "publisher": "Nature Publishing Group",
        "authority": "primary",
        "categories": ["vibrational health", "biophotonics", "cellular renewal"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "Photochemical & Photobiological Sciences",
        "url": "https://link.springer.com/search.rss?facet-journal-id=43630",
        "priority": 4,
        "headline_mode": "preserve",
        "publisher": "Springer / RSC",
        "authority": "primary",
        "categories": ["vibrational health", "metabolic health"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "Aging Cell",
        "url": "https://onlinelibrary.wiley.com/feed/14749726/most-recent",
        "priority": 5,
        "headline_mode": "preserve",
        "publisher": "Wiley / Anatomical Society",
        "authority": "primary",
        "categories": ["regenerative health", "cellular senescence", "longevity"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "Nature Aging",
        "url": "https://www.nature.com/nataging.rss",
        "priority": 5,
        "headline_mode": "preserve",
        "publisher": "Nature Publishing Group",
        "authority": "primary",
        "categories": ["regenerative health", "longevity", "metabolic health"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "GeroScience",
        "url": "https://link.springer.com/search.rss?facet-journal-id=11357",
        "priority": 4,
        "headline_mode": "preserve",
        "publisher": "American Aging Association",
        "authority": "primary",
        "categories": ["regenerative health", "longevity", "general wellness"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "Gut Microbes",
        "url": "https://www.tandfonline.com/feed/rss/kgmi20",
        "priority": 4,
        "headline_mode": "preserve",
        "publisher": "Taylor & Francis",
        "authority": "primary",
        "categories": ["gut health", "functional health"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "The ISME Journal (Microbial Ecology)",
        "url": "https://www.nature.com/ismej.rss",
        "priority": 4,
        "headline_mode": "preserve",
        "publisher": "Nature Publishing Group",
        "authority": "primary",
        "categories": ["gut health", "functional health"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "eLife Neuroscience",
        "url": "https://elifesciences.org/rss/subject/neuroscience.xml",
        "priority": 5,
        "headline_mode": "preserve",
        "publisher": "eLife Sciences",
        "authority": "primary",
        "categories": ["brain health", "functional health"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    },
    {
        "name": "Frontiers in Human Neuroscience",
        "url": "https://www.frontiersin.org/journals/human-neuroscience/rss",
        "priority": 4,
        "headline_mode": "preserve",
        "publisher": "Frontiers",
        "authority": "primary",
        "categories": ["brain health", "sleep health"],
        "max_daily_items": 1,
        "requires_secondary_check": True
    }
]

existing_urls = {f["url"] for f in feeds}
added_count = 0
for f in new_feeds:
    if f["url"] not in existing_urls:
        feeds.append(f)
        added_count += 1

with open(path, "w") as f:
    json.dump(feeds, f, indent=2)

print(f"Successfully added {added_count} new frontier feeds into feed-portfolio.json! Total active feeds now: {len(feeds)}")
