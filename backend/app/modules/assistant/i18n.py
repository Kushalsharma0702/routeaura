"""Reply templates (English / Hindi). The conversation language, not the language of the last message, picks the template."""

T: dict[str, dict[str, str]] = {
    "greeting": {
        "en": "Hello! I can suggest destinations, plan trips, change your itinerary, find hotels and check your bookings. What would you like to do?",
        "hi": "नमस्ते! मैं जगहें सुझा सकता हूँ, यात्रा की योजना बना सकता हूँ, आपकी यात्रा में बदलाव कर सकता हूँ, होटल खोज सकता हूँ और आपकी बुकिंग देख सकता हूँ। आप क्या करना चाहेंगे?",
    },
    "help": {
        "en": "Try: “recommend a place for history and food”, “plan 3 days in Jaipur for two”, “show my itinerary”, “remove Hawa Mahal”, “add Amber Fort to day 2”, “hotels in Goa” or “show my bookings”.",
        "hi": "कहकर देखें: “इतिहास और खाने के लिए जगह सुझाओ”, “जयपुर के लिए 3 दिन का प्लान बनाओ”, “मेरी यात्रा दिखाओ”, “हवा महल हटाओ”, “दिन 2 में आमेर किला जोड़ो”, “गोवा में होटल” या “मेरी बुकिंग दिखाओ”।",
    },
    "unknown": {
        "en": "I'm not sure I understood, so I haven't changed anything. I can recommend places, plan a trip, show or change your itinerary, find hotels, or check your bookings. Say “help” for examples.",
        "hi": "मुझे ठीक से समझ नहीं आया, इसलिए मैंने कुछ नहीं बदला। मैं जगहें सुझा सकता हूँ, यात्रा की योजना बना सकता हूँ, आपकी यात्रा दिखा या बदल सकता हूँ, होटल खोज सकता हूँ और बुकिंग देख सकता हूँ। उदाहरण के लिए “मदद” कहें।",
    },
    "ask_destination": {
        "en": "Which destination do you have in mind? Available: {names}.",
        "hi": "आप किस जगह जाना चाहते हैं? उपलब्ध: {names}।",
    },
    "ask_days": {"en": "How many days will the trip be?", "hi": "यात्रा कितने दिनों की होगी?"},
    "ask_day": {"en": "Which day should I use (1 to {n})?", "hi": "कौन सा दिन चुनूँ (1 से {n})?"},
    "recommend_intro": {"en": "Here are places that match you best:", "hi": "ये जगहें आपके लिए सबसे उपयुक्त हैं:"},
    "recommend_fallback": {
        "en": "These are popular places. Set your travel preferences for personalised picks.",
        "hi": "ये लोकप्रिय जगहें हैं। व्यक्तिगत सुझावों के लिए अपनी यात्रा पसंद सेट करें।",
    },
    "recommend_none": {
        "en": "I couldn't find any destinations to recommend yet.",
        "hi": "अभी सुझाने के लिए कोई जगह नहीं मिली।",
    },
    "plan_done": {
        "en": "I created a {days}-day trip to {dest} with {n} activities. {summary}",
        "hi": "मैंने {dest} की {days} दिन की यात्रा बनाई है, जिसमें {n} गतिविधियाँ हैं। {summary}",
    },
    "plan_issue": {
        "en": "Note: {n} schedule issue(s) were found; please review them in the itinerary.",
        "hi": "ध्यान दें: {n} समय-सारिणी संबंधी समस्या मिली; कृपया यात्रा में देख लें।",
    },
    "plan_fallback": {
        "en": "(Planned by the app's own planner; travel times are estimates.)",
        "hi": "(ऐप के अपने प्लानर से बनाई गई; यात्रा समय अनुमानित हैं।)",
    },
    "no_itinerary": {
        "en": "You don't have an itinerary yet. Say, for example, “plan 3 days in Jaipur”.",
        "hi": "आपकी अभी कोई यात्रा नहीं है। उदाहरण: “जयपुर के लिए 3 दिन का प्लान बनाओ”।",
    },
    "itin_header": {"en": "Your trip “{title}”:", "hi": "आपकी यात्रा “{title}”:"},
    "itin_day": {"en": "Day {d}: {items}", "hi": "दिन {d}: {items}"},
    "itin_empty": {"en": "nothing planned", "hi": "कुछ तय नहीं"},
    "confirm_remove": {
        "en": "Do you want me to remove {name} from day {day}? Say yes to confirm.",
        "hi": "क्या आप चाहते हैं कि मैं दिन {day} से {name} हटा दूँ? पुष्टि के लिए “हाँ” कहें।",
    },
    "confirm_move": {
        "en": "Move {name} to day {day}? Say yes to confirm.",
        "hi": "{name} को दिन {day} में ले जाऊँ? पुष्टि के लिए “हाँ” कहें।",
    },
    "removed": {"en": "Done. I removed {name}.", "hi": "हो गया। मैंने {name} हटा दिया।"},
    "moved": {"en": "Done. I moved {name} to day {day}.", "hi": "हो गया। मैंने {name} को दिन {day} में ले लिया।"},
    "added": {"en": "Added {name} to day {day}.", "hi": "{name} को दिन {day} में जोड़ दिया।"},
    "cancelled": {"en": "Okay, I left your itinerary unchanged.", "hi": "ठीक है, मैंने आपकी यात्रा में कोई बदलाव नहीं किया।"},
    "nothing_pending": {"en": "There is nothing waiting for confirmation.", "hi": "पुष्टि के लिए कुछ लंबित नहीं है।"},
    "activity_not_found": {
        "en": "I couldn't tell which activity you mean. Your itinerary has: {names}.",
        "hi": "मैं समझ नहीं पाया कि आप कौन सी गतिविधि कह रहे हैं। आपकी यात्रा में है: {names}।",
    },
    "attraction_not_found": {
        "en": "I couldn't find that among the published places for {dest}.",
        "hi": "{dest} के प्रकाशित स्थानों में मुझे वह नहीं मिला।",
    },
    "bookings_none": {"en": "You don't have any bookings yet.", "hi": "आपकी अभी कोई बुकिंग नहीं है।"},
    "bookings_header": {"en": "Your recent bookings:", "hi": "आपकी हाल की बुकिंग:"},
    "booking_line": {"en": "{ref}: {hotel}, {ci} to {co}, {status}", "hi": "{ref}: {hotel}, {ci} से {co}, {status}"},
    "hotels_header": {"en": "Hotels in {dest}:", "hi": "{dest} में होटल:"},
    "hotel_line": {"en": "{name} ({stars}★), from ₹{price} per night", "hi": "{name} ({stars}★), ₹{price} प्रति रात से"},
    "hotels_none": {"en": "I couldn't find hotels for {dest}.", "hi": "{dest} के लिए होटल नहीं मिले।"},
    "error": {"en": "I couldn't do that: {msg}", "hi": "मैं यह नहीं कर सका: {msg}"},
}
STATUS_HI = {
    "confirmed": "पुष्ट",
    "pending_payment": "भुगतान लंबित",
    "cancelled": "रद्द",
    "expired": "समाप्त",
    "failed": "विफल",
}


def tr(key: str, lang: str, **kw) -> str:
    return T[key].get(lang, T[key]["en"]).format(**kw)
