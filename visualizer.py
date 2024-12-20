import streamlit as st
import polars as pl
import folium as fo
from streamlit_folium import st_folium
from typing import Dict #, List


#st.set_page_config(layout="wide")

schools_source = pl.read_excel("schools.xlsx")
filter_targets = ["Fakulta","Katedry",  "Univerzita", "Obory", "Stát"] # Mělo by reflektovat všechny potenciální filtrované sloupečky
display_targets = ["Fakulta","Katedry",  "Univerzita", "Obor", "Obory", "Stát", "URL", "ERASMUS CODE"]

#TODO: Obecně hodně těhle deklarací je sketch. Trochu se na to kouknout a optimalizovat.
schools:pl.DataFrame = schools_source.select(filter_targets) # Schools je subtabulka sloužící k filtrování a jiným sussy operacím. Asi tady deklarována zbytečně vysoko.
picks:Dict[str, pl.Series] = schools.to_dict() # Dictionary s filtrovacími klíčovými slovíčky pro každý sloupeček
for column in picks.keys():
    picks[column] = ["---"]  + picks[column].unique().sort(nulls_last=True).to_list()

def filter_schools(school_df:pl.DataFrame) -> pl.DataFrame:
    """Funkce na profiltrování škol dle více podmínek."""
    filtered = school_df
    filter_choice = []

    for column in filtered.columns:
        if column not in st.session_state: # Teoreticky by se nemělo stát (st.multiselect inicializuje ten column jako prázdný seznam, takže bude v session state)
            continue

        if len(st.session_state[column]) > 0:
            filter_choice.append(pl.col(column).is_in(st.session_state[column])) 
        
    if len(filter_choice) < 1: # Pokud nejsou žádný podmínky, dej filtru vždycky pravdivou podmínku
        filter_choice = [True]
    print(filter_choice)

    return filtered.filter(filter_choice)

st.header("ERASMUS PřF UJEP")
st.divider()

# --- TABULKA ---

# Filtrování
filters = st.columns(len(filter_targets)) # Názvy filtrovaných sloupců
for index, column in enumerate(filter_targets):
    with filters[index]:
        st.session_state[column] = st.multiselect(label=column, options=picks[column]) # Samotné filtry, NOTE: This is kinda stupid?

schools = filter_schools(schools_source)
schools_sub = schools.select(display_targets)




# --- MAPA --- TODO: Mapa pod tabulkou je hodně špatnej design. Pokud ta tabulka bude moc velká, bude to chtít hodně scrollování před nalezením mapy. Posunout mapu nahoru, nebo aspoň vedle tabulky.
# Hranice mapy
max_lat, min_lat = 75, 33
max_long, min_long = 65, -31

# Inicializace mapy
europe = fo.Map(
    [50.5, 14.25],
    zoom_start=4, # Počáteční krok přiblížení, čím menší tím oddálenější
    max_bounds=True, # Omezení tahání vedle
    min_lat=min_lat,
    max_lat=max_lat,
    min_lon=min_long,
    max_lon=max_long
)

# Barvy pro jednotlivé katedry
# category_colors = {
#     "Turecká republika":"purple",
#     "Švédské království":"lightblue",
#     "Španělské království":"lightgreen",
#     "Srbská republika":"purple",
#     "Spolková republika Německo":"pink",
#     "Slovinská republika":"lightgreen",
#     "Slovenská republika":"pink",
#     "Řecká republika":"purple",
#     "Rumunsko":"purple",
#     "Portugalská republika":"lightgreen",
#     "Polská republika":"pink",
#     "Maďarsko":"pink",
#     "Lotyšská republika":"lightblue",
#     "Litevská republika":"lightblue",
#     "Italská republika":"lightgreen",
#     "Chorvatská republika":"lightgreen",
#     "Francouzská republika":"lightgreen",
#     "Estonská republika":"lightblue",
#     "Bulharská republika":"purple"
# }
# command k command c .... command k command u

category_colors = {"PřF": "pink"}

schools = schools.filter([pl.col("Longitude").is_not_null(), pl.col("Latitude").is_not_null()])

# Vytvoření Markerů na mapě
# Extrahování koordinací z dataframeu #TODO: Tohle je extrémně špatný přístup. Holy fuck.
#coords = zip(*(schools.get_column(col_name).to_list() for col_name in display_targets))
coords = zip(
    schools.to_series(schools.get_column_index("Fakulta")).to_list(),
    schools.to_series(schools.get_column_index("Univerzita")).to_list(),
    schools.to_series(schools.get_column_index("Latitude")).to_list(),
    schools.to_series(schools.get_column_index("Longitude")).to_list(),
    schools.to_series(schools.get_column_index("Stát")).to_list(),
    schools.to_series(schools.get_column_index("URL")).to_list()
)

# Iterace a zapsání do mapy
for coord in coords:
    fakulta = coord[0]
    color = category_colors.get(fakulta, "blue")
    
    # Vytvoření popisu s názvem univerzity a URL
    popup_content = f"<strong>{coord[0]}</strong><br><a href='{coord[4]}' target='_blank'>{coord[4]}</a>"
    
    fo.Marker(
        location=[coord[2], coord[3]],
        popup=fo.Popup(popup_content),
        icon=fo.Icon(color=color, icon="graduation-cap", prefix="fa")
    ).add_to(europe)

# Spuštění 
st_folium(europe, use_container_width=True)

#st.session_state

st.dataframe(schools_sub, use_container_width=True, column_config={"URL":st.column_config.LinkColumn()})
