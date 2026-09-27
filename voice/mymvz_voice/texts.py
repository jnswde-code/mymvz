"""Fixed announcements of the assistant, in German.

Drafts from #14 (sections 3.2 and 6); the data protection officer still has
to approve them. Numbers are also written out digit by digit, so a TTS
does not read 112 as "hundertzwölf".
"""

from __future__ import annotations

GREETING = (
    "Guten Tag, hier ist der digitale Assistent des MVZ in Grevenbroich. "
    "Ich bin eine künstliche Intelligenz. "
    "Bei einem Notfall legen Sie bitte auf und wählen Sie die 112. "
    "Wenn Sie mit einem Menschen sprechen möchten, sagen Sie „Mitarbeiter“ oder drücken Sie die 0. "
    "Das Gespräch wird nicht aufgezeichnet. "
    "Hinweise zum Datenschutz hören Sie mit der 9 und finden Sie auf unserer Website. "
    "Wie kann ich helfen?"
)

PRIVACY_NOTICE = (
    "Hinweise zum Datenschutz: Dieses Gespräch wird nicht aufgezeichnet, "
    "und es wird kein Protokoll des Gesprächsinhalts gespeichert. "
    "Gespeichert werden nur die Angaben, die Sie für eine Terminanfrage nennen. "
    "Die ausführlichen Hinweise finden Sie in der Datenschutzerklärung auf unserer Website. "
    "Wie kann ich helfen?"
)

GOODBYE = "Vielen Dank für Ihren Anruf. Auf Wiederhören."

EMERGENCY_FIRST = "Wenn Lebensgefahr besteht, legen Sie jetzt auf und wählen Sie die 112. "

EMERGENCY_CONNECTING = "Ich verbinde Sie sofort mit dem Praxisteam."

EMERGENCY_NOBODY = (
    "Ich erreiche gerade niemanden. "
    "Bei Lebensgefahr wählen Sie bitte die 112. "
    "Für dringende Beschwerden erreichen Sie den ärztlichen Bereitschaftsdienst unter 116 117. "
    "Ich wiederhole langsam: Bei Lebensgefahr die eins, eins, zwei. "
    "Den Bereitschaftsdienst unter eins, eins, sechs, eins, eins, sieben. "
)

CRISIS_LINE = (
    "Die Telefonseelsorge erreichen Sie rund um die Uhr kostenlos "
    "unter 0800 111 0 111, also null, acht, null, null, eins, eins, eins, null, eins, eins, eins. "
)

NUMBERS_UNDERSTOOD = "Haben Sie die Nummern verstanden?"

CONNECTING = "Ich verbinde Sie mit dem Praxisteam."

HEALTH_CONNECTING = "Dazu verbinde ich Sie mit dem Praxisteam."

HEALTH_NOBODY = (
    "Dazu kann ich Ihnen nichts sagen, und ich erreiche gerade niemanden aus dem Praxisteam. "
    "Bei dringenden Beschwerden erreichen Sie den ärztlichen Bereitschaftsdienst unter 116 117, "
    "bei Lebensgefahr wählen Sie bitte die 112."
)

NOBODY = (
    "Ich erreiche gerade niemanden aus dem Praxisteam. "
    "Bitte rufen Sie während der Öffnungszeiten noch einmal an. "
    "Bei Lebensgefahr wählen Sie die 112, bei dringenden Beschwerden die 116 117."
)

# Stored with every request the assistant creates (`privacy_notice_version`,
# #14 section 5). Set to the day of the change whenever GREETING or
# PRIVACY_NOTICE changes.
NOTICE_VERSION = "telefon-2026-09-27"

API_UNAVAILABLE = (
    "Das kann ich wegen eines technischen Problems gerade leider nicht erledigen. "
    "Bitte rufen Sie später noch einmal an, am besten während der Öffnungszeiten. "
    "Bei Lebensgefahr wählen Sie die 112, bei dringenden Beschwerden die 116 117."
)
