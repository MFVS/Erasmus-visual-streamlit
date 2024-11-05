import streamlit as st
import base64
from loader import table_overwriter, table_eraser
from geopy.exc import GeocoderUnavailable
import os.path

#TODO: Sqlite databázka na držení whitelistu

#NOTE: The whitelist is stored in a TXT. Extremely bad design, make it into a very small db, something like SQLite.
whitelist = []
if os.path.exists("names.txt"):
    with open("names.txt", "r") as wl_file:
        whitelist = base64.b64decode(wl_file.read().encode("utf-8")).decode("utf-8").split('\n')

if "stagUserInfo" not in st.query_params and "user" not in st.session_state: #st.session_state["user"] not in whitelist :
    st.page_link("https://ws.ujep.cz/ws/login?originalURL=http://localhost:8501/admin", label="Přihlášení zde.")
    st.error("Uživatel není přihlášen. Před pokračováním se přihlašte.")
    st.stop()

def pick_user():
    candidate = st.query_params["stagUserName"]

    if len(whitelist) == 0:
        st.warning("Varování: Prázdný whitelist. Vytvářím nový a přidávám právě přihlášeného uživatele.")
        with open("names.txt", "a") as wl_file:
            wl_file.write(base64.b64encode(candidate).decode("utf-8"))

    elif candidate not in whitelist:
        st.error("Uživatel nemá oprávnění na přístup k administrátorským nástrojům. Pokud věříte, že toto je špatně, kontaktuje jednoho z administrátorů or sumin idk and idc lmao")
        st.page_link("visualizer.py", label="Zpět na hlavní stránku")
        st.stop()

    st.session_state["user"] = candidate
    

pick_user()

st.title("ERASMUS PRF: Administrátorský přístup")

if st.button("Zpět na vizualizaci"):
    st.switch_page("visualizer.py")

# -----

st.warning("Při nahrávání souboru je nutno se ujistit, že je ve správném formátu, jak je specifikováno v dokumentaci.")
fac_school_adder, fac_school_remover = st.columns(2)
fac_school_download, fac_school_docs = st.columns(2)

with fac_school_adder:
    file = st.file_uploader("Uploadujte novou tabulku", accept_multiple_files=False)
    #st.write(file)
    if file != None:
        with st.spinner("Získávám geokoordinace. Prosím, počkejte chvíli, tohle bude trvat."):
            try:
                problems = table_overwriter(file)
            except GeocoderUnavailable:
                st.error("Problém ve spojení s geolokátorem: Tabulka nebyla změněna. Prosím, zkuste to znovu později.")
            else:
                if problems:
                    st.warning(f"Detekováno {problems} řádků bez geokoordinací. Doporučujeme zkusit upravit jméno v posílané tabulce a zkusit to znovu. Vadné školy jde vidět v stažitelné tabulce.")
                
                st.success("Tabulka aktualizována.")
        file = None

with fac_school_remover:
    remfile = st.file_uploader("Uploadujte soubor s kódy odstraňovaných škol.", accept_multiple_files=False)
    if remfile != None:
        with st.spinner("Odstraňuji školy..."):
            remcount = table_eraser(remfile)
            st.warning(f"Odstraněno {remcount} řádků.")
        remfile = None

with fac_school_download:
    st.download_button("Stáhnout vizualizovanou tabulku", "schools.xlsx", "Erasmy-vizualizace.xlsx")

with fac_school_docs:
    #TODO: Sepsat dokumentaci pro uživatele a dát ji stahovat.
    pass

st.header("Přidat uživatele do whitelistu")
#TODO: Přidat


#TODO: Manipulace se vším ostatním