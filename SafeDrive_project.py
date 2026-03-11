import streamlit as st
import spacy
import dateparser
from datetime import datetime
import re 
from rapidfuzz import fuzz

nlp = spacy.load("nl_core_news_sm")

# tijd mapping voor woorden
tijd_mapping = {
    "ochtend": "09:00",
    "morgen": "09:00",
    "middag": "13:00",
    "namiddag": "15:00",
    "avond": "19:00",
    "nacht": "23:00"
}

if "data" not in st.session_state:
    st.session_state.data = {
        "datum": None,
        "tijd": None,
        "locatie": None,
        "schade": None,
        "fotos": None
    }
    #check doen als de ingevoerde datum correct is. Dit is een vlag voor deze check
    st.session_state.datum_goedgekeurd = False 

schade_zinnen = []

# def om te checken als er spellingsfouten zijn gemaakt bij het schrijven van de tekst
# aangeraden van een drempelwaarde van 75-80 te hebben
def bevat_schadewoord(zin, keywords, drempel=80):
    zin_lower = zin.lower()
    woorden_in_zin = zin_lower.split()

    for woord in woorden_in_zin:
        for keyword in keywords:
            score = fuzz.ratio(woord, keyword)
            if score >= drempel:
                return True
    return False

def extract_info(text):

    doc = nlp(text)

    datum = None
    tijd = None
    locatie = None
    schade = None

    # zoek eerst een datum patroon in de tekst met regex
    datum_patroon = re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b', text)

    # via regex zoeken naar tijdswoorden
    tijdswoorden_patroon = re.search(
        r'\b(gisteren|eergisteren|vorige week|afgelopen \w+|maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\b',
        text.lower()
    )

    if datum_patroon:
        # dit plaatst de gevonden match met re.search in een variable.
        # datum_patroon.group() is dus de datum die re.search vind. Bv "25-03-2026"
        gevonden_datum = datum_patroon.group()        

        # Nu geven we de gevonden datum door aan dateparser zonder de rest van de zin.
        # settings DATE_ORDER zorgt voor de EU standaard setting 
        parsed = dateparser.parse(gevonden_datum, languages=["nl"], settings={"DATE_ORDER": "DMY"})

        # als DMY niet lukt, check of het MDY (Amerikaans formaat) wel lukt
        if not parsed:
            parsed = dateparser.parse(gevonden_datum, languages=["nl"], settings={"DATE_ORDER": "MDY"})
            if parsed:
                st.info("Datum leek op Amerikaans formaat (MM/DD/YYYY) en werd automatisch omgezet.")
    elif tijdswoorden_patroon:
        # Gevonden tijdswoord apart aan dateparser geven
        gevonden_tijdswoord = tijdswoorden_patroon.group()
        parsed = dateparser.parse(gevonden_tijdswoord, languages=["nl"], settings={
                "DATE_ORDER": "DMY",
                "PREFER_DATES_FROM": "past"
        })
    else:
        # Geen datum patroon gevonden, probeer de hele tekst
        parsed = dateparser.parse(text, languages=["nl"], settings={
            "DATE_ORDER": "DMY", 
            "PREFER_DATES_FROM": "past"
        })

    if parsed:
        datum = parsed.date()
        tijd = parsed.time()

    # tijd detectie via mapping als dateparser niets vond
    if not tijd:
        lower_text = text.lower()
        for woord, mapped_time in tijd_mapping.items():
            if woord in lower_text:
                tijd = mapped_time
                break

    # locatie detectie
    for ent in doc.ents:
        if ent.label_ in ["LOC", "GPE"]:
            locatie = ent.text

    # schade detectie
    schade_keywords = [
    # bestaand
    "deuk", "kras", "schade", "kapot", "bumper", "scheur", "gestolen", "kwijt", "ingeslaan", "gestolen",

    # deuk/vervorming
    "deuken", "deukje", "ingedeukt", "gegedeukt", "gebutst", "buts", "bluts", "geblutst",
    "vervormd", "krom", "scheef", "knik", "plooien", "in de kreukels",

    # scheur/barst
    "scheuren", "gescheurd", "afgescheurd", "haarscheur", "doorgescheurd",
    "barst", "barsten", "gebarsten", "haarscheurtje",

    # krassen/lak
    "krassen", "krasje", "bekrast", "lakschade", "lak weg", "lak eraf",
    "steenslag", "clearcoat los", "verf afgebladderd", "doffe lak",
    "schuurplek", "schuursporen", "afschilferen",

    # breuk/verlies/bevestiging
    "gebroken", "afgebroken", "los", "losgeraakt", "loshangend",
    "bevestiging stuk", "clip stuk", "clips stuk", "weggeslagen",
    "onderdeel weg", "missend", "verdwenen", "defect", "werkt niet",

    # glas/ruiten
    "ruitschade", "ruit ingeslagen", "ingeslagen ruit", "raam ingeslagen", "ingetikt",
    "glasbreuk", "ruiten kapot", "raam kapot", "sterretje", "sterretjes", "chip in ruit",
    "barst in ruit", "voorruit gebarsten", "achterruit gebarsten", "zijruit gebroken",
    "ruit uit de sponning", "raamsponning verbogen",

    # verlichting/spiegels
    "koplamp kapot", "koplamp gebarsten", "achterlicht stuk", "mistlamp stuk",
    "lampunit gebroken", "lampglas gebarsten", "drl kapot",
    "spiegel kapot", "buitenspiegel afgebroken", "spiegelglas gebroken",
    "spiegelbehuizing stuk", "spiegel los",

    # sensoren/ADAS
    "sensor stuk", "sensor werkt niet", "pdc doet het niet", "radar uit",
    "camera uit", "kalibratie nodig", "herkalibreren", "alignment adas",
    "storing", "storingsmelding", "foutcode", "waarschuwingslampje",

    # banden/wielen/ophanging
    "lekke band", "band lek", "band leeg", "band bult", "bandwang beschadigd",
    "band gescheurd", "ventiel stuk", "velg beschadigd", "velg krom",
    "stoeprandschade", "curb rash",
    "trekt naar links", "trekt naar rechts", "stuur scheef", "trilt", "vibratie",
    "onbalans", "uitlijning van slag", "spoorstang krom", "draagarm krom",
    "veerpoot lek", "schokdemper lek", "wiellager geluid",

    # koeling/vloeistoffen
    "lekkage", "lekt", "olie lekt", "koelvloeistof lekt", "olieplek",
    "radiator lek", "condensor lek", "airco doet het niet", "koelfan kapot",
    "oververhitting", "benzinegeur", "brandstof lekt",

    # sloten/inbraak/vandalisme/diefstal
    "inbraak", "inbraakschade", "slot geforceerd", "deurslot kapot",
    "contactslot beschadigd", "bekrast vandalisme", "spiegel afgetrapt",
    "velg gestolen", "kentekenplaat weg", "opgebroken", "weggesleept", "auto weg",
    "onderdeel weggenomen",

    # airbags/veiligheid
    "airbag open", "airbag uitgeklapt", "gordelspanner geactiveerd",
    "airbag lampje", "srs storing",

    # geluid/symptomen
    "kraakt", "piept", "tikt", "rammelt", "schuurt", "zoemt", "bonkt",
    "slaat door", "klap gehoord", "gejank", "fluittoon",

    # ernst/status
    "ernstige schade", "flinke schade", "kleine schade", "total loss",
    "total-loss", "totalloss", "afgeschreven",

    # richting/locatie (combineer met schade voor context)
    "linker", "links", "rechter", "rechts", "voorkant", "achterkant", "zijkant",
    "linksvoor", "rechtsvoor", "linksachter", "rechtsachter",
    "bestuurderszijde", "passagierszijde", "neus", "kont",
    ]

    for sent in doc.sents:
        if bevat_schadewoord(sent.text, schade_keywords):
            schade_zinnen.append(sent.text) # steekt alle zinnen met schadewoorden in een list

    # alle gevonden zinnen samenvoegen tot één tekst met een spatie ertussen
    if schade_zinnen:
        schade = " ".join(schade_zinnen)

    return datum, tijd, locatie, schade


st.title("Schadeclaim via SafeDrive 🚘")

text = st.text_area("Beschrijf wat er gebeurd is")

# twee buttons toevoegen die naast elkaar staan
col1, col2 = st.columns(2)

with col1:
    analyseer_geklikt = st.button("Analyseer tekst")

with col2:
    foto_geklikt = st.button("📷 Foto's toevoegen")

# checken als er op de foto knop geklikt wordt -> foto uploader openen
if foto_geklikt:
    st.session_state.toon_uploader = True

if st.session_state.get("toon_uploader", False):
    fotos = st.file_uploader(
        "Voeg foto's van de schade toe",
        type=["jgp", "jpeg", "png"], # alleen afbeeldingen toelaten
        accept_multiple_files= True # meerdere foto's toevoegen per keer is mogelijk
    )
    if fotos:
        st.session_state.data["fotos"] = fotos
        st.success(f"{len(fotos)} foto('s) toegevoegd!")

if analyseer_geklikt:

    datum, tijd, locatie, schade = extract_info(text)

    if datum:
        if datum <= datetime.today().date(): # alleen de datum opslaan als deze vandaag of in het verleden ligt
            st.session_state.data  ["datum"] = datum
            st.session_state.datum_goedgekeurd = True # als datum correct is, vlag op true zetten
        else:
            st.session_state.datum_goedgekeurd = False # als datum nogsteeds foutief is, vlag op False houden
            st.warning("De gedetecteerde datum ligt in de toekomst. Wat het onmogelijk maakt om een schadeclaim in te voeren wat nog niet gebeurd is. Geef een geldige datum in.")

    if tijd:
        st.session_state.data["tijd"] = tijd

    if locatie:
        st.session_state.data["locatie"] = locatie

    if schade:
        st.session_state.data["schade"] = schade


data = st.session_state.data

st.subheader("Gedetecteerde gegevens")

if data["datum"] and st.session_state.datum_goedgekeurd: # dit checked als datum ingevoerd is EN als deze een correcte waarde heeft
    st.write("Datum:", data["datum"])
else:
    ingevoerde_datum = st.date_input("Voer een datum in.", value=None, max_value= datetime.today().date(), format="DD/MM/YYYY") # value = None zorgt ervoor dat tekstvak leeg blijft als incorrecte datum is ingevoerd en format zorgt voor een placeholder tekst in het tekstvak
    if ingevoerde_datum:
        data["datum"] = ingevoerde_datum
        st.session_state.datum_goedgekeurd = True
    #data["datum"] = st.date_input("Voer datum in", max_value=datetime.today().date())

if data["tijd"]:
    st.write("Tijd:", data["tijd"])
else:
    data["tijd"] = st.text_input("Voer tijdstip in (bijv. namiddag of 14:00)", value=None)

if data["locatie"]:
    st.write("Locatie:", data["locatie"])
else:
    data["locatie"] = st.text_input("Voer locatie in")

if data["schade"]:
    st.write("Schade:", data["schade"])
else:
    data["schade"] = st.text_area("Beschrijf schade")

if all(data.values()):

    if data["datum"] > datetime.today().date():
        st.error("Datum mag niet in de toekomst liggen")
    else:
        st.success("Alle gegevens compleet!")
        text = st.write("Uw gegevens zijn:")
        st.write("Datum:", data["datum"])
        st.write("Tijd:", data["tijd"])
        st.write("Locatie:", data["locatie"])
        st.write("Schade:", data["schade"])

        

