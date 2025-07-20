from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import math
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def round_up(value, step=10):
    """Zaokrąglenie wartości w górę do najbliższego kroku."""
    return math.ceil(value / step) * step

def get_price(system: str, width: int, height: int, material: str, width2: int = None):
    file_path = "cenniki/cenniki_plis.xlsx"
    
    # Sprawdzenie, czy plik istnieje
    if not os.path.exists(file_path):
        return None, "Brak pliku z cennikami."
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # Dostosowano do nazw systemów w formacie 'System_X'
        system_name = f"System_{system}"
        if system_name not in xls.sheet_names:
            return None, f"Brak cennika dla wybranego systemu: {system_name}"
        
        # Wczytanie cennika dla systemu
        df = xls.parse(system_name, index_col=0).dropna(how="all")
        df.columns = pd.to_numeric(df.columns, errors="coerce")
        df.index = pd.to_numeric(df.index, errors="coerce")
        df = df.dropna().astype(float)
        
        # Wczytanie cennika materiałów
        materials_df = xls.parse("Material", header=0)
        materials_df.set_index(materials_df.columns[0], inplace=True)
        materials_df.columns = ["Cena"]
        materials_df["Cena"] = materials_df["Cena"].astype(str).str.replace(",", ".").astype(float)

    except Exception as e:
        return None, f"Błąd wczytywania pliku: {str(e)}"
    
    # Przetwarzanie materiału
    material = material.strip().upper()
    if material not in materials_df.index:
        return None, "Nie znaleziono wybranego materiału."
    
    material_price = materials_df.at[material, "Cena"]
    
    # Zaokrąglanie szerokości i wysokości
    rounded_width = round_up(width, 10)
    rounded_height = round_up(height, 10)
    
    available_widths = sorted(df.columns)
    available_heights = sorted(df.index)
    
    # Znalezienie najbliższych wartości szerokości i wysokości
    nearest_width = next((w for w in available_widths if w >= rounded_width), None)
    nearest_height = next((h for h in available_heights if h >= rounded_height), None)
    
    if nearest_width is None or nearest_height is None:
        return None, "Podane wymiary są zbyt duże – brak w ofercie."
    
    # Cena bazowa z cennika
    base_price = df.at[nearest_height, nearest_width]
    
    # Jeśli podano drugą szerokość
    if width2:
        rounded_width2 = round_up(width2, 10)
        nearest_width2 = next((w for w in available_widths if w >= rounded_width2), None)
        if nearest_width2:
            base_price += df.at[nearest_height, nearest_width2]
    
    # Obliczenie powierzchni i całkowitej ceny
    area = (max(width, width2) / 100) * (height / 100)  # w m2
    total_price = round(base_price + (area * material_price))
    
    return total_price, None

@app.get("/cena/")
def get_cena(system: str, szerokosc: int, wysokosc: int, material: str, szerokosc2: int = Query(None)):
    # Sprawdzenie poprawności danych
    if not system or not szerokosc or not wysokosc or not material:
        return JSONResponse(content={"error": "Wprowadź wszystkie wymagane dane (system, szerokość, wysokość, materiał)."}, status_code=400)
    
    total_price, error = get_price(system, szerokosc, wysokosc, material, szerokosc2)
    
    if error:
        return JSONResponse(content={"error": error}, status_code=400)
    
    return JSONResponse(content={"cena": total_price}, status_code=200)
    
@app.get("/materialy/")
def get_materialy():
    file_path = "cenniki/cenniki_plis.xlsx"
    if not os.path.exists(file_path):
        return JSONResponse(content={"error": "Brak pliku z cennikami."}, status_code=404)

    try:
        xls = pd.ExcelFile(file_path)
        df = xls.parse("Material", header=0)
        df.set_index(df.columns[0], inplace=True)
        material_names = df.index.tolist()
        return JSONResponse(content={"materialy": material_names}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
