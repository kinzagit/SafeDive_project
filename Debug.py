import re
import dateparser

text = "Mijn achterbumper is helemaal ingedeukt en achterruit kapot nadat een idioot tegen mij reed van achteren. Dit gebeurde gisteren op de Utrechtseweg 58 in Utrecht"

tijdswoorden_patroon = re.search(
    r'\b(gisteren|eergisteren|vorige week|afgelopen \w+|maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\b',
    text.lower()
)

print("Gevonden tijdswoord:", tijdswoorden_patroon.group() if tijdswoorden_patroon else None)

# Als tijdswoord gevonden, test of dateparser het correct omzet
if tijdswoorden_patroon:
    gevonden_tijdswoord = tijdswoorden_patroon.group()
    parsed = dateparser.parse(gevonden_tijdswoord, languages=["nl"], settings={
        "DATE_ORDER": "DMY",
        "PREFER_DATES_FROM": "past"
    })
    print("Dateparser resultaat:", parsed)
    if parsed:
        print("Datum:", parsed.date())