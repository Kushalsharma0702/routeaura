"""Idempotent demo catalogue (destinations, attractions, categories).

Everything here is marked source="seed": coordinates are approximate, and costs/durations are
placeholder ESTIMATES for development, not provider data. Opening hours are deliberately left
unset (unknown) rather than invented. Refuses to run in production.
"""
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_sessionmaker
from app.models.catalog import Attraction, AttractionCategory, Destination
from app.modules.catalog.slugs import slugify

CATEGORIES = {
    "History & Heritage": "Forts, palaces, monuments and museums",
    "Beach": "Coastline and water activities",
    "Nature & Wildlife": "Parks, waterfalls, lakes and wildlife",
    "Adventure": "Trekking, mountain passes and outdoor sport",
    "Culture & Religion": "Temples, monasteries and living traditions",
    "Scenic Viewpoint": "Landscapes and viewpoints",
    "Food & Markets": "Local cuisine and bazaars",
}

# name: (country, region, lat, lng, cost/day INR, days, season start, season end, climate, categories, images, blurb)
IMG = "https://images.unsplash.com/"
DESTINATIONS = {
    "Goa": ("India", "Goa", 15.2993, 74.1240, 3500, 5, 10, 3, "tropical", ["Beach", "History & Heritage"],
            [IMG + "photo-1512343879784-a960bf40e7f2?w=800", IMG + "photo-1587922546307-776227941871?w=800"],
            "India's party capital with stunning beaches, Portuguese heritage, water sports, and a buzzing nightlife scene."),
    "Manali": ("India", "Himachal Pradesh", 32.2396, 77.1887, 3000, 6, 10, 6, "cold", ["Adventure", "Scenic Viewpoint"],
               [IMG + "photo-1626621341517-bbf3d9990a23?w=800", IMG + "photo-1585409677983-0f6c41ca9c3b?w=800"],
               "A Himalayan hill station with snow-capped peaks, adventure sports, and lush green valleys."),
    "Jaipur": ("India", "Rajasthan", 26.9124, 75.7873, 3200, 4, 10, 3, "arid", ["History & Heritage", "Food & Markets", "Culture & Religion"],
               [IMG + "photo-1599661046289-e31897846e41?w=800", IMG + "photo-1524492412937-b28074a5d7da?w=800"],
               "The Pink City: a vibrant blend of majestic forts, colourful bazaars, and royal Rajasthani culture."),
    "Kerala": ("India", "Kerala", 10.8505, 76.2711, 3800, 7, 9, 3, "tropical", ["Nature & Wildlife", "Beach"],
               [IMG + "photo-1602216056096-3b40cc0c9944?w=800", IMG + "photo-1609920658906-8223bd289001?w=800"],
               "God's Own Country: serene backwaters, lush tea gardens, Ayurveda, and tropical beaches."),
    "Ladakh": ("India", "Ladakh", 34.1526, 77.5770, 4200, 8, 6, 9, "cold", ["Adventure", "Culture & Religion", "Scenic Viewpoint"],
               [IMG + "photo-1506905925346-21bda4d32df4?w=800&q=80", IMG + "photo-1506197603052-3cc9c3a201bd?w=800&q=80"],
               "Land of high passes: stark mountains, ancient monasteries, and turquoise Pangong Lake."),
}

# destination: [(name, category, lat, lng, duration_min, outdoor)]
ATTRACTIONS = {
    "Goa": [("Baga Beach", "Beach", 15.5553, 73.7517, 180, True),
            ("Basilica of Bom Jesus", "History & Heritage", 15.5009, 73.9116, 60, False),
            ("Dudhsagar Falls", "Nature & Wildlife", 15.3144, 74.3143, 240, True),
            ("Fort Aguada", "History & Heritage", 15.4925, 73.7737, 90, True)],
    "Manali": [("Rohtang Pass", "Adventure", 32.3716, 77.2466, 300, True),
               ("Solang Valley", "Adventure", 32.3166, 77.1566, 240, True),
               ("Hadimba Temple", "Culture & Religion", 32.2480, 77.1800, 60, False),
               ("Old Manali", "Food & Markets", 32.2500, 77.1760, 120, True)],
    "Jaipur": [("Hawa Mahal", "History & Heritage", 26.9239, 75.8267, 60, False),
               ("Amber Fort", "History & Heritage", 26.9855, 75.8513, 180, False),
               ("City Palace", "History & Heritage", 26.9258, 75.8237, 120, False),
               ("Jantar Mantar", "History & Heritage", 26.9247, 75.8246, 60, True)],
    "Kerala": [("Alleppey Backwaters", "Nature & Wildlife", 9.4981, 76.3388, 240, True),
               ("Munnar Tea Gardens", "Scenic Viewpoint", 10.0889, 77.0595, 180, True),
               ("Periyar Wildlife Sanctuary", "Nature & Wildlife", 9.4623, 77.2386, 240, True),
               ("Kovalam Beach", "Beach", 8.4004, 76.9787, 150, True)],
    "Ladakh": [("Pangong Lake", "Scenic Viewpoint", 33.7595, 78.6674, 300, True),
               ("Nubra Valley", "Scenic Viewpoint", 34.6866, 77.5619, 360, True),
               ("Thiksey Monastery", "Culture & Religion", 34.0486, 77.6663, 90, False),
               ("Khardung La", "Adventure", 34.2780, 77.6040, 90, True)],
}


def seed(db: Session) -> dict[str, int]:
    created = {"categories": 0, "destinations": 0, "attractions": 0}
    cats: dict[str, AttractionCategory] = {}
    for name, desc in CATEGORIES.items():
        slug = slugify(name)
        cat = db.scalar(select(AttractionCategory).where(AttractionCategory.slug == slug))
        if cat is None:
            cat = AttractionCategory(name=name, slug=slug, description=desc)
            db.add(cat)
            created["categories"] += 1
        cats[name] = cat
    db.flush()

    for name, (country, region, lat, lng, cost, days, s_m, e_m, climate, cat_names, images, blurb) in DESTINATIONS.items():
        slug = slugify(name)
        dest = db.scalar(select(Destination).where(Destination.slug == slug))
        if dest is None:
            dest = Destination(
                slug=slug, name=name, country=country, region=region, description=blurb,
                latitude=lat, longitude=lng, estimated_cost_per_day_minor=cost * 100,
                recommended_duration_days=days, best_season_start_month=s_m, best_season_end_month=e_m,
                climate=climate, images=images, is_published=True, source="seed",
            )
            dest.categories = [cats[c] for c in cat_names]
            db.add(dest)
            db.flush()
            created["destinations"] += 1
        for a_name, a_cat, a_lat, a_lng, minutes, outdoor in ATTRACTIONS[name]:
            a_slug = slugify(a_name)
            exists = db.scalar(select(Attraction.id).where(Attraction.destination_id == dest.id,
                                                            Attraction.slug == a_slug))
            if exists is None:
                db.add(Attraction(destination_id=dest.id, category_id=cats[a_cat].id, slug=a_slug,
                                  name=a_name, latitude=a_lat, longitude=a_lng,
                                  typical_duration_minutes=minutes, is_outdoor=outdoor,
                                  is_published=True, source="seed"))
                created["attractions"] += 1
    db.commit()
    return created


def main() -> int:
    if get_settings().environment == "production":
        print("seed_catalog refuses to run in production", file=sys.stderr)
        return 1
    with get_sessionmaker()() as db:
        print("created:", seed(db))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
