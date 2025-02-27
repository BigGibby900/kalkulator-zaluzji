from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import math
import os
import socket
import uvicorn

app = FastAPI()

# Pozwolenie na połączenia z frontendem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Pozwolenie na połączenia z dowolnego źródła
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Obsługa plików statycznych
app.mount("/static", StaticFiles(directory="static"), name="static")

def round_up(value, step=10):
    """Zaokrąglenie wartości do najbliższej wielokrotności `step`."""
    return math.ceil(value / step) * step

def get_price(category: str, width: int, height: int):
    """Pobiera cenę z odpowiedniego cennika na podstawie szerokości i wysokości."""
    file_path = f"cenniki/{category}.xlsx"  # Ścieżka do pliku Excel

    if not os.path.exists(file_path):
        return None, None, None, f"Brak cennika dla kategorii: {category}"

    try:
        xls = pd.ExcelFile(file_path)
        if "Cennik" not in xls.sheet_names:
            return None, None, None, "Brak arkusza 'Cennik' w pliku."

        df = xls.parse("Cennik", index_col=0)
    except Exception as e:
        return None, None, None, f"Błąd wczytywania pliku: {str(e)}"

    df = df.dropna(how="all")  # Usunięcie pustych wierszy/kolumn
    df.columns = pd.to_numeric(df.columns, errors="coerce")
    df.index = pd.to_numeric(df.index, errors="coerce")
    df = df.dropna().astype(float)  # Konwersja na liczby

    rounded_width = round_up(width, 10)
    rounded_height = round_up(height, 10)

    available_widths = sorted(df.columns)
    available_heights = sorted(df.index)

    if not available_heights or not available_widths:
        return None, None, None, "Cennik nie zawiera prawidłowych danych."

    if rounded_height > max(available_heights):
        return None, None, None, "Podana wysokość jest zbyt duża – brak w ofercie."

    nearest_width = next((w for w in available_widths if w >= rounded_width), None)
    nearest_height = next((h for h in available_heights if h >= rounded_height), None)

    if nearest_width is None:
        return None, None, None, "Podana szerokość jest zbyt duża – brak w ofercie."

    # Pobranie ceny z tabeli, obsługa braku wartości
    price = df.get(nearest_width, {}).get(nearest_height, None)

    if price is None:
        return None, None, None, "Brak ceny dla podanych wymiarów."

    return round(price), nearest_width, nearest_height, None

@app.get("/cena/")
def get_cena(
    category: str = Query(..., description="Nazwa kategorii np. drewno_25"),
    szerokosc: int = Query(..., description="Szerokość w cm"),
    wysokosc: int = Query(..., description="Wysokość w cm")
):
    """API do pobierania ceny na podstawie kategorii, szerokości i wysokości."""
    price, nearest_width, nearest_height, error_message = get_price(category, szerokosc, wysokosc)
    if error_message:
        return {"error": error_message}
    return {
        "kategoria": category,
        "szerokosc": szerokosc,
        "wysokosc": wysokosc,
        "cena": price,
        "zaokraglona_szerokosc": nearest_width,
        "zaokraglona_wysokosc": nearest_height
    }

# Strona główna (index.html)
@app.get("/")
async def get_index():
    return FileResponse('static/index.html')  # Wskazuje na plik index.html w katalogu static

# Dynamicznie ustawiając host na Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Domyślnie 8000, ale na Renderze będzie to port z ENV
    uvicorn.run(app, host="0.0.0.0", port=port)
