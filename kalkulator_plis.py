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
    return math.ceil(value / step) * step

def get_price(system: str, width: int, height: int, material: str, width2: int = None):
    file_path = "cenniki/cenniki_plis.xlsx"
    
    if not os.path.exists(file_path):
        return None, "Brak pliku z cennikami."
    
    try:
        xls = pd.ExcelFile(file_path)
        
        if f"System {system}" not in xls.sheet_names:
            return None, "Brak cennika dla wybranego systemu."
        
        df = xls.parse(f"System {system}", index_col=0).dropna(how="all")
        df.columns = pd.to_numeric(df.columns, errors="coerce")
        df.index = pd.to_numeric(df.index, errors="coerce")
        df = df.dropna().astype(float)
        
        materials_df = xls.parse("materialy", index_col=0).dropna()
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

@app.get("/cena/")
def get_cena(system: str, szerokosc: int, wysokosc: int, material: str, szerokosc2: int = Query(None)):
    total_price, error = get_price(system, szerokosc, wysokosc, material, szerokosc2)
    return JSONResponse(content={"cena": total_price} if not error else {"error": error}, status_code=400 if error else 200)
