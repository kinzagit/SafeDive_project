import re
import dateparser

text = "Op 05-03-2026 om 09:05 uur reed een scooter te dicht langs in de Leidsestraat. Linksachter zitten nu krassen en het spatbord is licht ingedeukt."

# Stap 1 - 11u conversie
text = re.sub(r'\b(\d{1,2})u(\d{2})?\b', lambda m: f"{m.group(1)}:{m.group(2) or '00'}", text)
print("Na conversie:", text)

# Stap 2 - tijd patroon zoeken
tijd_match = re.search(r'\d{1,2}:\d{2}', text)
print("Gevonden tijdstip:", tijd_match.group() if tijd_match else None)

# Stap 3 - dateparser met alleen het tijdstip
if tijd_match:
    parsed = dateparser.parse(tijd_match.group(), languages=["nl"])
    print("Dateparser tijdstip:", parsed)