import pytest

from app.modules.assistant import nlu

DESTS = {"jaipur": "Jaipur", "goa": "Goa", "manali": "Manali", "kerala": "Kerala", "ladakh": "Ladakh"}


@pytest.mark.parametrize(
    "text,lang",
    [
        ("Plan a trip to Jaipur", "en"),
        ("मुझे जयपुर घूमना है", "hi"),
        ("नमस्ते", "hi"),
        ("5 दिन की यात्रा बनाओ", "hi"),
        ("mujhe Goa ghoomne jaana hai kya", "hi"),
        ("hello", "en"),
        ("", "en"),
        ("123 456", "en"),
        ("Jaipur में 3 days", "hi"),
    ],
)
def test_language_detection(text, lang):
    assert nlu.detect_language(text)[0] == lang


def test_romanised_hindi_needs_two_markers_so_a_single_word_does_not_flip_the_language():
    assert nlu.detect_language("what is yatra")[0] == "en" and nlu.detect_language("mujhe yatra chahiye")[0] == "hi"


@pytest.mark.parametrize(
    "text,days",
    [
        ("a 5 day trip", 5),
        ("three days in goa", 3),
        ("5 दिन", 5),
        ("पाँच दिन के लिए", 5),
        ("७ दिन", 7),
        ("a weekend in manali", 2),
        ("3-day plan", 3),
        ("no number here", None),
    ],
)
def test_days_in_both_languages(text, days):
    assert nlu.extract_days(nlu._norm(text)) == days


@pytest.mark.parametrize(
    "text,minor",
    [
        ("budget ₹25,000", 2_500_000),
        ("budget 25k", 2_500_000),
        ("under rs 15000", 1_500_000),
        ("2 lakh rupees", 20_000_000),
        ("20000 रुपये", 2_000_000),
        ("बजट 30 हज़ार", 3_000_000),
        ("no money talk", None),
        ("₹0", None),
    ],
)
def test_budget_parsing(text, minor):
    assert nlu.extract_budget_minor(nlu._norm(text)) == minor


@pytest.mark.parametrize(
    "text,n",
    [("for two people", 2), ("4 people", 4), ("पाँच लोग", 5), ("honeymoon trip", 2), ("solo trip", 1), ("a trip", None)],
)
def test_travelers(text, n):
    assert nlu.extract_travelers(nlu._norm(text)) == n


def test_interests_and_destinations_in_both_languages():
    assert nlu.extract_interests("history and local food") == ["history", "food"]
    assert nlu.extract_interests(nlu._norm("मुझे इतिहास और खाना पसंद है")) == ["history", "food"]
    assert (
        nlu.extract_destination("trip to jaipur", DESTS) == "jaipur"
        and nlu.extract_destination("जयपुर घूमना", DESTS) == "jaipur"
    )
    assert nlu.extract_destination("लद्दाख", DESTS) == "ladakh" and nlu.extract_destination("paris", DESTS) is None
    assert nlu.extract_destination("जयपुर", {"goa": "Goa"}) is None  # alias for an unpublished destination is ignored


@pytest.mark.parametrize(
    "text,intent",
    [
        ("Plan a 3 day trip to Jaipur", "plan"),
        ("3 days in Goa", "plan"),
        ("5 दिन जयपुर की यात्रा बनाओ", "plan"),
        ("Recommend a place for beaches", "recommend"),
        ("कहाँ घूमने जाऊं", "recommend"),
        ("suggest something for history lovers", "recommend"),
        ("show my itinerary", "show"),
        ("मेरी यात्रा दिखाओ", "show"),
        ("remove Hawa Mahal", "remove"),
        ("Hawa Mahal हटा दो", "remove"),
        ("add Amber Fort to day 2", "add"),
        ("जयपुर में आमेर जोड़ो", "add"),
        ("move City Palace to day 2", "move"),
        ("show my bookings", "booking"),
        ("मेरी बुकिंग", "booking"),
        ("hotels in Goa", "hotels"),
        ("होटल दिखाओ", "hotels"),
        ("hello", "greeting"),
        ("नमस्ते", "greeting"),
        ("help", "help"),
        ("blah blah", "unknown"),
        ("yes", "yes"),
        ("हाँ", "yes"),
        ("no thanks", "no"),
        ("नहीं", "no"),
    ],
)
def test_intents(text, intent):
    assert nlu.understand(text, "en", DESTS).intent == intent, text


def test_yes_no_only_when_the_message_is_short_so_long_sentences_are_not_mistaken_for_confirmations():
    assert nlu.understand("ok so can you plan a trip to Goa for 3 days", "en", DESTS).intent == "plan"
    assert nlu.understand("yes please", "en", DESTS).intent == "yes"


def test_slots_flow_into_the_understanding():
    u = nlu.understand("Plan 4 days in Jaipur for two, budget 30k, history and food", "en", DESTS)
    assert (
        u.intent,
        u.slots.destination,
        u.slots.days,
        u.slots.travelers,
        u.slots.budget_minor,
        u.slots.interests,
    ) == ("plan", "jaipur", 4, 2, 3_000_000, ["history", "food"])
    h = nlu.understand("जयपुर के लिए ५ दिन का प्लान, बजट 20 हज़ार", "hi", DESTS)
    assert (h.intent, h.slots.destination, h.slots.days, h.slots.budget_minor) == ("plan", "jaipur", 5, 2_000_000)
    assert nlu.understand("move City Palace to day 3", "en", DESTS).slots.day == 3


def test_name_matching_is_conservative():
    names = {"a": "Hawa Mahal", "b": "Amber Fort", "c": "City Palace", "d": "Jantar Mantar"}
    assert nlu.match_name("remove hawa mahal please", names) == "a"
    assert nlu.match_name("add the amber fort to day 2", names) == "b"
    assert nlu.match_name("remove the palace", {"c": "City Palace", "e": "Royal Palace"}) is None  # ambiguous
    assert nlu.match_name("remove everything", names) is None and nlu.match_name("", names) is None
