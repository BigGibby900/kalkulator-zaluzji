from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import math
import os
import uvicorn
import logging
from typing import List

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


def round_up(value, step=10):
    return math.ceil(value / step) * step


def get_price(category: str, width: int, height: int, zybka: int, karnisz: int, drabinka: bool, quantity: int):
    file_path = f"cenniki/{category}.xlsx"

    if not os.path.exists(file_path):
        return None, None, None, f"Brak cennika dla kategorii: {category}"

    try:
        xls = pd.ExcelFile(file_path)
        df = xls.parse("Cennik", index_col=0).dropna(how="all")
        df.columns = pd.to_numeric(df.columns, errors="coerce")
        df.index = pd.to_numeric(df.index, errors="coerce")
        df = df.dropna().astype(float)
    except Exception as e:
        return None, None, None, f"Błąd wczytywania pliku: {str(e)}"

    rounded_width = round_up(width, 10)
    rounded_height = round_up(height, 10)

    available_widths = sorted(df.columns)
    available_heights = sorted(df.index)

    nearest_width = next((w for w in available_widths if w >= rounded_width), None)
    nearest_height = next((h for h in available_heights if h >= rounded_height), None)

    if nearest_width is None or nearest_height is None:
        return None, None, None, "Podane wymiary są zbyt duże – brak w ofercie."

    try:
        base_price = df.at[nearest_height, nearest_width]
    except KeyError:
        return None, None, None, "Brak ceny dla podanych wymiarów."

    if drabinka:
        base_price *= 1.05  # Dodanie 5% do ceny bazowej

    total_price = (base_price + (35 if zybka == 25 else 50 if zybka == 50 else 0) + (30 if karnisz == 30 else 0)) * quantity
    return round(total_price), nearest_width, nearest_height, None


@app.get("/cena/")
def get_cena(
    category: str,
    szerokosci: str = Query(...),
    wysokosci: str = Query(...),
    ilosci: str = Query(...),
    zybka: str = Query("0"),
    karnisz: str = Query("0"),
    drabinka: str = Query("0"),  # 0 = brak, 1 = drabinka taśmowa
):
    try:
        szerokosci = list(map(int, szerokosci.split(",")))
        wysokosci = list(map(int, wysokosci.split(",")))
        ilosci = list(map(int, ilosci.split(",")))
        zybka = list(map(int, zybka.split(","))) if zybka else [0] * len(szerokosci)
        karnisz = list(map(int, karnisz.split(","))) if karnisz else [0] * len(szerokosci)
        drabinka = list(map(int, drabinka.split(","))) if drabinka else [0] * len(szerokosci)
    except ValueError:
        return {"error": "Niepoprawny format danych - wartości powinny być liczbami oddzielonymi przecinkami"}

    if not (len(szerokosci) == len(wysokosci) == len(ilosci)):
        return {"error": "Niepoprawna liczba parametrów - szerokości, wysokości i ilości muszą mieć tę samą długość"}

    results = []
    for i in range(len(szerokosci)):
        total_price, zaokraglona_szerokosc, zaokraglona_wysokosc, error = get_price(
            category,
            szerokosci[i],
            wysokosci[i],
            zybka[i] if i < len(zybka) else 0,
            karnisz[i] if i < len(karnisz) else 0,
            bool(drabinka[i]) if i < len(drabinka) else False,
            ilosci[i]
        )

        if error:
            results.append({"szerokosc": szerokosci[i], "wysokosc": wysokosci[i], "ilosc": ilosci[i], "error": error})
        else:
            results.append({
                "szerokosc": szerokosci[i],
                "wysokosc": wysokosci[i],
                "ilosc": ilosci[i],
                "cena": total_price,
                "zaokraglona_szerokosc": zaokraglona_szerokosc,
                "zaokraglona_wysokosc": zaokraglona_wysokosc
            })

    return {"results": results}


@app.get("/")
async def get_index():
    return FileResponse('static/index.html')


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
