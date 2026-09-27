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

# Provisional, for the phone assistant (#14, decision 3 of 27.09.2026): as
# on the existing homepage (inventory in #3), to be confirmed by the practice
# before real calls. The homepage names no parking, bus or train; the
# assistant says it does not know.
ACCESS = "Der barrierefreie Zugang ist von der Bahnstraße aus."
# The homepage says "täglich"; the practice is closed at weekends.
BLOOD_DRAW = "Blutabnahme ist an jedem Öffnungstag von 8 bis 9 Uhr."


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
