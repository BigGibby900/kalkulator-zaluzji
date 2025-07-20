from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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

# ---------------- ŻALUZJE / MOSKITIERY ----------------
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
        base_price *= 1.05
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
    drabinka: str = Query("0"),
):
    try:
        szerokosci = list(map(int, szerokosci.split(",")))
        wysokosci = list(map(int, wysokosci.split(",")))
        ilosci = list(map(int, ilosci.split(",")))
        zybka = list(map(int, zybka.split(","))) if zybka else [0] * len(szerokosci)
        karnisz = list(map(int, karnisz.split(","))) if karnisz else [0] * len(szerokosci)
        drabinka = list(map(int, drabinka.split(","))) if drabinka else [0] * len(szerokosci)
    except ValueError:
        return {"error": "Niepoprawny format danych - liczby oddzielone przecinkami"}

    if not (len(szerokosci) == len(wysokosci) == len(ilosci)):
        return {"error": "Niepoprawna liczba parametrów - różne długości list"}

    results = []
    for i in range(len(szerokosci)):
        total_price, zw, zh, error = get_price(
            category, szerokosci[i], wysokosci[i],
            zybka[i] if i < len(zybka) else 0,
            karnisz[i] if i < len(karnisz) else 0,
            bool(drabinka[i]) if i < len(drabinka) else False,
            ilosci[i]
        )
        if error:
            results.append({"szerokosc": szerokosci[i], "wysokosc": wysokosci[i], "ilosc": ilosci[i], "error": error})
        else:
            results.append({
                "szerokosc": szerokosci[i], "wysokosc": wysokosci[i], "ilosc": ilosci[i],
                "cena": total_price, "zaokraglona_szerokosc": zw, "zaokraglona_wysokosc": zh
            })
    return {"results": results}

# ---------------- PLISY ----------------
def get_price_plis(system: str, width: int, height: int, material: str, width2: int = None):
    file_path = "cenniki/cenniki_plis.xlsx"
    if not os.path.exists(file_path):
        return None, "Brak pliku z cennikami."
    try:
        xls = pd.ExcelFile(file_path)
        system_name = f"System_{system}"
        if system_name not in xls.sheet_names:
            return None, f"Brak cennika dla systemu: {system_name}"
        df = xls.parse(system_name, index_col=0).dropna(how="all")
        df.columns = pd.to_numeric(df.columns, errors="coerce")
        df.index = pd.to_numeric(df.index, errors="coerce")
        df = df.dropna().astype(float)
        materials_df = xls.parse("Material", header=0)
        materials_df.set_index(materials_df.columns[0], inplace=True)
        materials_df.columns = ["Cena"]
        materials_df["Cena"] = materials_df["Cena"].astype(str).str.replace(",", ".").astype(float)
    except Exception as e:
        return None, f"Błąd wczytywania pliku: {str(e)}"

    material = material.strip().upper()
    if material not in materials_df.index:
        return None, "Nie znaleziono wybranego materiału."
    material_price = materials_df.at[material, "Cena"]
    rounded_width = round_up(width, 10)
    rounded_height = round_up(height, 10)
    available_widths = sorted(df.columns)
    available_heights = sorted(df.index)
    nearest_width = next((w for w in available_widths if w >= rounded_width), None)
    nearest_height = next((h for h in available_heights if h >= rounded_height), None)
    if nearest_width is None or nearest_height is None:
        return None, "Podane wymiary są zbyt duże – brak w ofercie."
    base_price = df.at[nearest_height, nearest_width]
    if width2:
        rounded_width2 = round_up(width2, 10)
        nearest_width2 = next((w for w in available_widths if w >= rounded_width2), None)
        if nearest_width2:
            base_price += df.at[nearest_height, nearest_width2]
    area = (max(width, width2) / 100) * (height / 100)
    total_price = round(base_price + (area * material_price))
    return total_price, None

@app.get("/cena/plisy")
def get_cena_plisy(system: str, szerokosc: int, wysokosc: int, material: str, szerokosc2: int = Query(None)):
    if not system or not szerokosc or not wysokosc or not material:
        return JSONResponse(content={"error": "Brak wymaganych danych."}, status_code=400)
    total_price, error = get_price_plis(system, szerokosc, wysokosc, material, szerokosc2)
    if error:
        return JSONResponse(content={"error": error}, status_code=400)
    return JSONResponse(content={"cena": total_price}, status_code=200)

@app.get("/materialy/plisy")
def get_materialy_plisy():
    file_path = "cenniki/cenniki_plis.xlsx"
    if not os.path.exists(file_path):
        return JSONResponse(content={"error": "Brak pliku z cennikami."}, status_code=404)
    try:
        xls = pd.ExcelFile(file_path)
        df = xls.parse("Material", header=0)
        df.set_index(df.columns[0], inplace=True)
        return JSONResponse(content={"materialy": df.index.tolist()}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/")
async def get_index():
    return FileResponse('static/index.html')

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
