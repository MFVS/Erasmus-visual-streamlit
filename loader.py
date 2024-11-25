import polars as pl
import easygui
import logging as log
from geopy.geocoders import Nominatim
import os.path
from typing import Dict, List

# Nastavení logování NOTE: Log se ukládá do loader_log.txt
log.basicConfig(
    filename="loader_log.txt",
    encoding="utf-8",
    filemode="w",
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
    level=log.INFO
)

# Funkce vracící slovník ve formátu {jméno v načítané tabulce:jméno v ukládané tabulce} 
def getColumnTrans() -> Dict[str, str]:
    return {
        #"ciziSkolaNazev":"Univerzita",
        "ciziSkolaZkratka":"ERASMUS CODE",
        "ciziSkolaMesto":"Město",
        "ciziSkolaStatNazev":"Stát",
        "kodyIscedUvedeneUDomacichPodmSml":"Obor",
        "interniNazevSmlouvy":"Fullname"
    }

# Funkce sjednoducíjící jména načítané a ukláadané tabulky
def unite_cols(new_schools:pl.DataFrame, name_gen:pl.DataFrame) -> pl.DataFrame:
    column_translator:Dict[str, str] = getColumnTrans()
    shady_stuff:List[str] = ["Univerzita"] + list(column_translator.values())
    return new_schools.drop("ciziSkolaNazev").rename(column_translator).join(name_gen, "ERASMUS CODE", "left").select(shady_stuff)

# Funkce která získá katedry
def extract_dptmnts(new_schools:pl.DataFrame) -> pl.Series:
    #test = new_schools.get_column("Fullname").str.strip_chars().str.split(",").slice("").list.join(",")
    #log.info(test.to_list())
    #log.info(new_schools.get_column("Fullname").to_list())
    new_schools = new_schools.filter(pl.col("Fullname") != "STORNO").with_columns(pl.col("Fullname").str.replace_all(" ", "").str.split(",").list.slice(offset=1).alias("Katedry")).drop("Fullname")
    log.info(new_schools.head())
    return new_schools.with_columns(pl.col("Katedry").map_elements(lambda lst: [f"K{elem}" if elem[0] != "K" and elem not in ["NANO", "PŘF", "PRF", "PRF MIMO KGEO"] else elem for elem in lst], return_dtype=pl.List(pl.String)).list.join(", ").name.keep())
    comp_func = lambda lst: [elem if elem[0] != "K" and elem not in ["NANO", "PRF", "PRF MIMO KGEO"] else f"K{elem}" for elem in lst]

# Funkce která předělává čísla oborů na jména
def rename_subs(new_schools:pl.DataFrame) -> pl.DataFrame:
    # Tabulka se jmény oborů
    code_trans = pl.read_excel("cz_isced_f_systematicka_cast.xlsx")
    code_trans = code_trans.with_columns(
       pl.col("Název").str.replace_all(r"(?i)– obory [dj]\. n\.", "").str.strip_chars_end().alias("Based") # Hranatá závorka je regulérní výraz: V podstatě to znamená "Pokud najdeš jedno písmeno z množiny"    
    ).drop("Název").rename({"Based":"Název"}) 


    # Rozepiš obory
    new_schools = new_schools.with_columns(pl.col("Obor").str.split(", ").alias("Obor2")).drop("Obor").rename({"Obor2":"Obor"})
    new_schools_temp = new_schools.explode("Obor").join(code_trans, "Obor", how="left").rename({"Název":"Obory"}).unique()

    # Agreguj ČÍSLA oborů, a nalep je na tabulku s explodovanými obory
    obor_rename = new_schools_temp.lazy().group_by("ERASMUS CODE").agg(pl.col("Obor")).collect().with_columns(pl.col("Obor").list.join(", ").name.keep())#.drop("Název")
    new_schools_temp = new_schools_temp.drop("Obor").join(obor_rename, "ERASMUS CODE", "left")

    # Vrať zpět pracovní tabulku s názvy oborů
    log.info(new_schools_temp.columns)
    return new_schools_temp

def rename_subs_hard(new_schools:pl.DataFrame, old_schools:pl.DataFrame) -> pl.DataFrame:
    temp_schools = new_schools.select("ERASMUS CODE", "Obor").with_columns(
        pl.col("Obor").str.split(", ").name.keep()
    ).explode("Obor").lazy().group_by("ERASMUS CODE").agg(pl.col("Obor")).collect().with_columns(
        pl.col("Obor").list.join(", ").alias("Obor_neu")
    ).drop("Obor").unique("ERASMUS CODE") 
    old_schools = old_schools.select("ERASMUS CODE", "Obor").unique("ERASMUS CODE")

    # Bear with me
    # Vezmi obory z new_schools a old_schools, spoj je a vyřaď duplicitní hodnoty
    mediator:pl.DataFrame = temp_schools.join(old_schools, "ERASMUS CODE", "left").with_columns(
        pl.concat_str([pl.col("Obor_neu"), pl.col("Obor")], separator=", ", ignore_nulls=True).str.split(", ").list.unique().alias("Kódy oborů")
    ).drop("Obor_neu", "Obor")

    # Zduplikuj obory, druhý exploduj
    mediator = mediator.rename({"Kódy oborů":"Obor"}).with_columns(pl.col("Obor").list.join(", ").alias("Kódy oborů")).explode("Obor")

    # Získej tabulku jmen oborů, a očisti data (zbav se "- obory d. n." a variant toho, zbav se white space)
    code_trans = pl.read_excel("cz_isced_f_systematicka_cast.xlsx")
    code_trans = code_trans.with_columns(
       pl.col("Název").str.replace_all(r"(?i)– obory [dj]\. n\.", "").str.strip_chars_end().name.keep()#.alias("Based") # Hranatá závorka je regulérní výraz: V podstatě to znamená "Pokud najdeš jedno písmeno z množiny"    
    )#.drop("Název").rename({"Based":"Název"})

    # Spoj všechno dohromady (jména oborů -> mediátor, obory a jména oborů (mediátor) -> new_schools)
    mediator = mediator.join(code_trans, "Obor", "left").drop("Obor").rename({"Název":"Obory"})
    return new_schools.unique("ERASMUS CODE").join(mediator, "ERASMUS CODE", "left").drop("Obor").rename({"Kódy oborů":"Obor"})


# Funkce která přidává url
def get_url(new_schools:pl.DataFrame, url_source:pl.DataFrame) -> pl.DataFrame:
    return new_schools.join(url_source, "ERASMUS CODE", "left").with_columns(
        pl.when( # Potenciálně obsolete: Dá se nastavit aby se sloupeček zobrazoval jako hypertexty ve visualizeru
            pl.col("Website Url").str.starts_with("http").not_()
        ).then(
            "https://" + pl.col("Website Url")
        ).otherwise(
            pl.col("Website Url")
        ).alias("URL")
    ).drop("Website Url")#.rename({"Website Url":"URL"})

# Funkce která přidává geografické koordinace (aka zdroj všeho zla)
def get_coords(new_schools:pl.DataFrame, address_source:pl.DataFrame) -> pl.DataFrame:
    print("Získávám geokoordinace. Prosím, počkejte chvíli, tohle bude trvat.")
    # Mějme jen kódy škol a adresy
    address_source = address_source.join(new_schools.select("ERASMUS CODE", "Univerzita"), "ERASMUS CODE", "inner").unique("ERASMUS CODE")
    #address_source.write_excel("addresses.xlsx")

    # Vytvoření clienta geolokátoru
    geolocator = Nominatim(user_agent="matej@sloupovi.info") # NOTE: Tohle používá můj osobní účet. To není uplně ideální (jinak řečeno, this fuckin sucks).

    # Získání koordinací
    # Kolo 1
    names = address_source.to_series(address_source.get_column_index("Univerzita")).to_list()
    unis = address_source.to_series(address_source.get_column_index("ERASMUS CODE")).to_list()
    loc_dicts = {uni:name for uni,name in zip(unis, names)}
    relocations = {uni:geolocator.geocode(loc_dicts[uni]) for uni in unis}

    # Kolo 2: Spravení (některých) None hodnot
    fixes = [uni for uni in unis if relocations[uni] == None]
    locations = {uni:loc for uni,loc in zip(unis, address_source.to_series(address_source.get_column_index("Address")).to_list())} #NOTE: This makes me cry
    loc_dicts = {uni:{"street":locations[uni][0], "city":locations[uni][1], "country":locations[uni][2]} for uni in fixes}
    for uni in fixes:
        relocations[uni] = geolocator.geocode(loc_dicts[uni])

    # Přidání koordinací do df
    df_maker = {"ERASMUS CODE":[], "Longitude":[],"Latitude":[]}
    for loc in relocations.keys():
        df_maker["ERASMUS CODE"].append(loc)
        df_maker["Longitude"].append(str(relocations[loc].longitude) if relocations[loc] != None else None)
        df_maker["Latitude"].append(str(relocations[loc].latitude) if relocations[loc] != None else None)
        # reloc_info = f"{relocations[loc]} ({relocations[loc].latitude}, {relocations[loc].longitude})" if relocations[loc] != None else None
        #log.info(f"{loc} - {reloc_info}")
    return new_schools.join(pl.from_dict(df_maker), "ERASMUS CODE", "left")

def table_overwriter(excel_file) -> int: # Funkce zapíše všechno do souboru a následně vrátí počet řádků s nevalidními koordinacemi
    # Načítání
    current_schools = pl.DataFrame()
    if not os.path.exists("schools.xlsx"):
        current_schools = pl.from_dict({
            "ERASMUS CODE":pl.Series(dtype=pl.String),
            "Katedry":pl.Series(dtype=pl.String),
            "Univerzita":pl.Series(dtype=pl.String),
            "Město":pl.Series(dtype=pl.String),
            "Stát":pl.Series(dtype=pl.String),
            "Longitude":pl.Series(dtype=pl.String),
            "Latitude":pl.Series(dtype=pl.String),
            "URL":pl.Series(dtype=pl.String),
            "Obor":pl.Series(dtype=pl.String),
            "Obory":pl.Series(dtype=pl.String)})
    else:
        current_schools = pl.read_excel("schools.xlsx")
    new_schools = pl.read_excel(excel_file)
    addresses = pl.read_excel("url_gen.xlsx").rename({"Erasms Code":"ERASMUS CODE", "Legal Name":"Univerzita"}).with_columns(pl.concat_list(pl.col("Street"), pl.col("City"), pl.col("Country Cd")).alias("Address")).select("ERASMUS CODE", "Univerzita", "Website Url", "Address")
    log.info("Tables read successfully.")

    # Sjednocení existujících sloupců
    new_schools = unite_cols(new_schools, addresses.select("ERASMUS CODE", "Univerzita"))
    log.info("Columns united.")
    log.info(new_schools.head())

    # Přidání kateder
    new_schools = extract_dptmnts(new_schools)
    log.info("Departments extracted.")
    log.info(new_schools.head(15))

    # Přejmenování oborů
    #rename_subs(new_schools=new_schools).write_excel("schools_legacy.xlsx")
    new_schools = rename_subs_hard(new_schools, current_schools)
    log.info("Renamed cols.")
    log.info(new_schools.filter((pl.col("ERASMUS CODE") == "BG ROUSSE01") | (pl.col("ERASMUS CODE") == "E JAEN01")).head())

    # Získání url
    new_schools = get_url(new_schools, addresses.select("ERASMUS CODE", "Website Url"))
    log.info("Fetched url.")
    log.info(new_schools.head()) 

    # Získání geokoordinací
    new_schools = get_coords(new_schools, addresses.select("ERASMUS CODE", "Address"))
    log.info("Fetched geocoords.")
    log.info(new_schools.head())
    log.info(new_schools.columns)

    # Mergování a zápis
    #current_schools = current_schools.drop("Longitude", "Latitude")

    new_schools = new_schools.select(current_schools.columns)
    current_schools.join(new_schools, "ERASMUS CODE", "anti").vstack(new_schools, in_place=True).write_excel("schools.xlsx")
    log.info("Done!")

    #return len(new_schools.filter(pl.col("Longitude").is_null() | pl.col("Latitude").is_null()))
    return 0

# ------
def parseLines(excel_file:any) -> List[str]:
    log.info("Starting file parsing by ascertaining file input type.")
    if type(excel_file) != str:
        try:
            excel_file = excel_file.name
        except:
            log.info("Type determination failed at input type determination. Throwing error.")
            raise ValueError("File has been inputted via an illegal method.")
        
    log.info(excel_file)
    
    match excel_file.split(".")[-1]:
        case "xlsx":
            log.info("File is an excel file.")
            buffer = pl.read_excel(excel_file)
            return buffer.to_series(buffer.get_column_index("ERASMUS CODE")).to_list()
        case "txt":
            log.info("File is a text file.")
            with open(excel_file, "r") as txtfile:
                return txtfile.read().split('\n')
        case _:
            log.info("Uh oh.")
            raise ValueError("File is of an unreadable format.")
    

def table_eraser(excel_file) -> int:
    if not os.path.exists("schools.xlsx"):
        raise FileNotFoundError("First, make sure to have some schools.")
    log.info("Starting eraser.")
    lines:List[str] = parseLines(excel_file)
    current_schools = pl.read_excel("schools.xlsx")
    curLen = len(current_schools)
    current_schools = current_schools.filter(pl.col("ERASMUS CODE").is_in(lines).not_())
    current_schools.write_excel("schools.xlsx")
    log.info("Eraser finished correctly.")
    return curLen - len(current_schools)
    

if __name__ == "__main__":
    table_overwriter(easygui.fileopenbox("Vyberte soubor s novými školami: ", "Hi", filetypes="*.xlsx"))
    #table_eraser(easygui.fileopenbox("Vyberte soubor obsahující školy k vymazání.", filetypes=["*.xlsx", "*.txt"]))