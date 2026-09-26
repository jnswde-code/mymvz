"""Public facts about the practice, as on the existing homepage (#3).

Used by the appointment pages and in e-mails. The homepage stays with the
practice and its agency (#3, 26.09.2026); these pages link to its imprint and
privacy policy.
"""

NAME = "MyMVZ Grevenbroich"
STREET = "Bahnstraße 56–58"
CITY = "41515 Grevenbroich"
PHONE = "02181 475762-0"
PHONE_LINK = "+4921814757620"
HOMEPAGE_URL = "https://mymvz.de/"
IMPRINT_URL = "https://mymvz.de/impressum/"
PRIVACY_URL = "https://mymvz.de/datenschutz/"


def practice_info(request):
    """Context processor: `practice` in every template."""
    return {
        "practice": {
            "name": NAME,
            "street": STREET,
            "city": CITY,
            "phone": PHONE,
            "phone_link": PHONE_LINK,
            "homepage_url": HOMEPAGE_URL,
            "imprint_url": IMPRINT_URL,
            "privacy_url": PRIVACY_URL,
        }
    }
