import streamlit as st
import spacy
import dateparser
from datetime import datetime, timedelta
import re 
from rapidfuzz import fuzz
import requests

nlp = spacy.load("nl_core_news_sm")

# tijd mapping voor woorden
tijd_mapping = {
    "ochtend": "09:00",
    "ochtends": "09:00",
    "morgen": "09:00",
    "middag": "13:00",
    "namiddag": "15:00",
    "avond": "19:00",
    "nacht": "23:00"
}

# coderen van tijdsindicatie
vandaag = datetime.today().date()
min_datum = vandaag - timedelta(days=92) # max 3 maanden terug als datum limiet

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
    # De extra vakken zijn niet zichtbaar zolang je niet op 'Analyseer tekst' klikt
    st.session_state.geanalyseerd = False

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

# de functie die tekst uit het ingevoerde tekstvak haalt
def extract_info(text):
    datum = None
    tijd = None
    locatie = None
    schade = None
    parsed = None

    schade_zinnen = []
    locatie_delen = []

    # "11u" of "11u30" omzetten naar "11:00" of "11:30" zodat dateparser het begrijpt
    text = re.sub(r'\b(\d{1,2})u(\d{2})?\b', lambda m: f"{m.group(1)}:{m.group(2) or '00'}", text)

    doc = nlp(text)  

    # zoek eerst een datum patroon in de tekst met regex
    datum_patroon = re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b', text)

    # via regex zoeken naar tijdswoorden
    tijdswoorden_patroon = re.search(
        r'\b(vandaag|net|zojuist|gisteren|eergisteren|vorige week|afgelopen \w+|maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\b',
        text.lower()
    )

    # dit checked voor USA datum formaat en zet het om naar DMY
    if datum_patroon:
        gevonden_datum = datum_patroon.group()
        parsed = dateparser.parse(gevonden_datum, languages=["nl"], settings={"DATE_ORDER": "DMY"})

        if not parsed:
            parsed = dateparser.parse(gevonden_datum, languages=["nl"], settings={"DATE_ORDER": "MDY"})
            if parsed:
                st.info("Datum leek op Amerikaans formaat (MM/DD/YYYY) en werd automatisch omgezet.")

        if parsed:
            datum = parsed.date()

            # ✅ tijd via regex zoeken in plaats van hele tekst aan dateparser geven
            tijd_match = re.search(r'\d{1,2}:\d{2}', text)
            if tijd_match:
                parsed_tijd = dateparser.parse(tijd_match.group(), languages=["nl"])
                if parsed_tijd:
                    if parsed_tijd.time().hour != 0 or parsed_tijd.time().minute != 0:
                        tijd = parsed_tijd.time()
    #als datum niet gevonden is, zoekt de code via de tijdswoorden in de tekst. Als hij één van de tijdswoorden vindt dan hard coderen wat dit is
    elif tijdswoorden_patroon:
        gevonden_tijdswoord = tijdswoorden_patroon.group()

        #hier kan je de woorden zelf hard coderen wat ze zijn. Voorlopig alles naar 'vandaag' gecodeert
        handmatige_mapping = {
            "vandaag": datetime.today().date(),
            "net": datetime.today().date(),
            "zojuist": datetime.today().date(),
            "daarnet": datetime.today().date(),
            "deze ochtend": datetime.today().date()
        }
        
        if gevonden_tijdswoord in handmatige_mapping:
            datum = handmatige_mapping[gevonden_tijdswoord]

            # tijd apart proberen uit de tekst te halen (als bv 12:55)
            tijd_match = re.search(r'\d{1,2}:\d{2}', text)
            if tijd_match:
                parsed_tijd = dateparser.parse(tijd_match.group(), languages=["nl"])
                if parsed_tijd:
                    if parsed_tijd.time().hour != 0 or parsed_tijd.time().minute != 0:
                        tijd = parsed_tijd.time()

        else:
            # Bouw zelf "gisteren om 11:00" samen zodat dateparser niet verward raakt
            tijd_match = re.search(r'\d{1,2}:\d{2}', text[tijdswoorden_patroon.start():])
            
            if tijd_match:
                # tijdswoord + tijd combineren
                combinatie = f"{gevonden_tijdswoord} om {tijd_match.group()}"
            else:
                # geen tijdstip gevonden, alleen het tijdswoord gebruiken
                combinatie = gevonden_tijdswoord

            parsed = dateparser.parse(combinatie, languages=["nl"], settings={
                "DATE_ORDER": "DMY",
                "PREFER_DATES_FROM": "past"
            })
            if parsed:
                datum = parsed.date()
                if parsed.time().hour != 0 or parsed.time().minute != 0:
                    tijd = parsed.time()
    else:
        # Geen datum patroon gevonden, probeer de hele tekst
        parsed = dateparser.parse(text, languages=["nl"], settings={
            "DATE_ORDER": "DMY", 
            "PREFER_DATES_FROM": "past"
        })
        if parsed:
            datum = parsed.date()
            # alleen tijd opslaan als het NIET middernacht is
            if parsed.time().hour != 0 or parsed.time().minute != 0:
                tijd = parsed.time()

    # tijd detectie via mapping als dateparser niets vond
    if not tijd:
        lower_text = text.lower()
        for woord, mapped_time in tijd_mapping.items():
            if woord in lower_text:
                tijd = mapped_time
                break

    # locatie detectie - tijdswoorden uitsluiten
    tijdswoorden = {"gisteren", "eergisteren", "vandaag", "maandag", "dinsdag", 
                    "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"}

    for ent in doc.ents:
        if ent.label_ in ["LOC", "GPE"]:
            if ent.text.lower() not in tijdswoorden:  # tijdswoorden uitsluiten
                locatie_delen.append(ent.text)

    # alle gevonden locaties samenvoegen
    if locatie_delen:
        locatie = ", ".join(locatie_delen)

    # schade detectie
    schade_keywords = [
    # bestaand
    "deuk", "kras", "schade", "kapot", "bumper", "scheur", "gestolen", "kwijt", "ingeslaan", 
    "gestolen", "eraf", "eruit", "gekrast"

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


#hier begint de front-end van Streamlit
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

    st.session_state.geanalyseerd = True # zodra ze op de knop klikken dit op True plaatsen
    datum, tijd, locatie, schade = extract_info(text)

    if datum:
        if min_datum <= datum <= vandaag:  # tussen 3 maanden geleden en vandaag
            st.session_state.data  ["datum"] = datum
            st.session_state.datum_goedgekeurd = True # als datum correct is, vlag op true zetten
        elif datum > vandaag:
            st.session_state.datum_goedgekeurd = False # als datum nogsteeds foutief is, vlag op False houden
            st.warning("De gedetecteerde datum ligt in de toekomst. Wat het onmogelijk maakt om een schadeclaim in te voeren wat nog niet gebeurd is. Geef een geldige datum in.")
        else:
            st.session_state.datum_goedgekeurd = False
            st.warning(f"De datum ligt meer dan 3 maanden in het verleden. Schadeclaims kunnen maximaal tot {min_datum.strftime('%d/%m/%Y')} ingediend worden.")

    if tijd:
        st.session_state.data["tijd"] = tijd

    if locatie:
        st.session_state.data["locatie"] = locatie

    if schade:
        st.session_state.data["schade"] = schade


data = st.session_state.data

if st.session_state.geanalyseerd:  # alleen tonen na klikken
    st.subheader("Gedetecteerde gegevens")

    if data["datum"] and st.session_state.datum_goedgekeurd: # dit checked als datum ingevoerd is EN als deze een correcte waarde heeft
        st.date_input("Datum", value=data["datum"])
        # st.write("Datum:", data["datum"])
    else:
        ingevoerde_datum = st.date_input(
            "(Optioneel) Voer een datum in.", 
            value=None,
            min_value=min_datum, 
            max_value= vandaag, 
            format="DD/MM/YYYY"
            ) # value = None zorgt ervoor dat tekstvak leeg blijft als incorrecte datum is ingevoerd en format zorgt voor een placeholder tekst in het tekstvak
        if ingevoerde_datum:
            data["datum"] = ingevoerde_datum
            st.session_state.datum_goedgekeurd = True
        #data["datum"] = st.date_input("Voer datum in", max_value=datetime.today().date())

    if data["tijd"]:
        st.text_input("Tijd:", value=data["tijd"])
    else:
        data["tijd"] = st.text_input("Voer tijdstip in (bijv. namiddag of 14:00)", value=None)

    if data["locatie"]:
        st.text_input("Locatie:", value=data["locatie"])
    else:
        data["locatie"] = st.text_input("Voer locatie in")

    if data["schade"]:
        st.text_area("Schade:", value=data["schade"])
    else:
        data["schade"] = st.text_area("Beschrijf schade")


verplichte_velden = {k: v for k, v in data.items() if k not in ["fotos", "tijd"]} #dictionary aanmaken die zorgt dat als alles behalve tijd en fotos ingevuld zijn het goed is
if all(verplichte_velden.values()):

    if data["datum"] > datetime.today().date():
        st.error("Datum mag niet in de toekomst liggen")
    else:
        st.success("Alle gegevens compleet!")
        text = st.write("Uw gegevens zijn:")
        st.write("Datum:", data["datum"])
        st.write("Tijd:", data["tijd"])
        st.write("Locatie:", data["locatie"])
        st.write("Schade:", data["schade"])

        # checkmark toevoegen
        bevestigd = st.checkbox("✅ Alle data is correct")

        if bevestigd:
            st.info(f"📅 Incident op {data['datum']} om {data['tijd']} in {data['locatie']}")
            st.warning("⚠️ Vergeet niet binnen 24 uur uw verzekeraar te contacteren!")
    
            with st.expander("📋 Bekijk volledige samenvatting & advies"):
                st.write("**Samenvatting:**")
                st.write(f"Op {data['datum']} om {data['tijd']} heeft u schade opgelopen op {data['locatie']}.")
                st.write(f"**Schade:** {data['schade']}")
        
                st.divider()
        
                st.write("**Advies & vervolgstappen:**")
                st.write("1. Wij nemen binnenkort contact op met je i.v.m. je schadeclaim")
                st.write("2. Bewaar alle foto's en bewijsstukken")
                st.write("3. Noteer gegevens van getuigen indien aanwezig")
                st.write("4. Rijd niet verder met een onveilig voertuig")
        

