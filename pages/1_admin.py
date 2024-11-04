import streamlit as st
import base64
from loader import table_overwriter

#NOTE: The whitelist is stored in a TXT. Extremely bad design, make it into a very small db, something like SQLite.
whitelist = []
with open("names.txt", "r") as wl_file:
    whitelist = base64.b64decode(wl_file.read().encode("utf-8")).decode("utf-8").split('\n')

if "stagUserInfo" not in st.query_params and "user" not in st.session_state: #st.session_state["user"] not in whitelist :
    st.page_link("https://ws.ujep.cz/ws/login?originalURL=http://localhost:8501/admin", label="Přihlášení zde.")
    st.error("Uživatel není přihlášen. Před pokračováním se přihlašte.")
    st.stop()

def pick_user():
    candidate = st.query_params["stagUserName"]
    if candidate not in whitelist:
        st.error("Uživatel nemá oprávnění na přístup k administrátorským nástrojům.")
        st.page_link("visualizer.py", label="Zpět na hlavní stránku")
        st.stop()

    st.session_state["user"] = candidate
    

pick_user()

st.title("ERASMUS PRF: Administrátorský přístup")
st.header("Přidání a odebrání škol")

#NOTE: HODNĚ sketchy věcí.
# 1) Neupozorní uživatele že tam je bezlokační řádky.
# 2) I dunno obecně se mi to nelíbí
file = st.file_uploader("Uploadujte novou tabulku", accept_multiple_files=False)
st.write(file)
if file != None:
    with st.spinner("Prosím, počkejte chvíli..."):
        table_overwriter(file)
    file = None
    st.success("Vše bylo v pořádku přidáno.")

#TODO: Manipulace se vším ostatním