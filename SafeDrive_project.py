import streamlit as st
import spacy
import dateparser
from datetime import datetime

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
        "schade": None
    }


def extract_info(text):

    doc = nlp(text)

    datum = None
    tijd = None
    locatie = None
    schade = None

    parsed = dateparser.parse(text, languages=["nl"])

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
    schade_keywords = ["deuk", "kras", "schade", "kapot", "bumper"]

    for sent in doc.sents:
        if any(w in sent.text.lower() for w in schade_keywords):
            schade = sent.text

    return datum, tijd, locatie, schade


st.title("Schadeclaim via SafeDrive 🚘")

text = st.text_area("Beschrijf wat er gebeurd is")

if st.button("Analyseer tekst"):

    datum, tijd, locatie, schade = extract_info(text)

    if datum:
        st.session_state.data["datum"] = datum

    if tijd:
        st.session_state.data["tijd"] = tijd

    if locatie:
        st.session_state.data["locatie"] = locatie

    if schade:
        st.session_state.data["schade"] = schade


data = st.session_state.data

st.subheader("Gedetecteerde gegevens")

if data["datum"]:
    st.write("Datum:", data["datum"])
else:
    data["datum"] = st.date_input("Voer datum in")

if data["tijd"]:
    st.write("Tijd:", data["tijd"])
else:
    data["tijd"] = st.text_input("Voer tijdstip in (bijv. namiddag of 14:00)")

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

        

