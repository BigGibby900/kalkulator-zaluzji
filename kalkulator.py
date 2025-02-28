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

# Ustawienie logowania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def get_price(category: str, width: int, height: int, zybka: int, karnisz: int):
    """Pobiera cenę z odpowiedniego cennika na podstawie szerokości, wysokości oraz usług."""
    file_path = f"cenniki/{category}.xlsx"  # Ścieżka do pliku Excel

    # Dodanie logowania, aby śledzić ścieżkę do pliku
    logger.info(f"Próba otwarcia pliku: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"Brak pliku: {file_path}")
        return None, None, None, f"Brak cennika dla kategorii: {category}"

    try:
        xls = pd.ExcelFile(file_path)
        if "Cennik" not in xls.sheet_names:
            logger.error(f"Brak arkusza 'Cennik' w pliku: {file_path}")
            return None, None, None, "Brak arkusza 'Cennik' w pliku."

        df = xls.parse("Cennik", index_col=0)
    except Exception as e:
        logger.error(f"Błąd wczytywania pliku {file_path}: {str(e)}")
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
        logger.error(f"Cennik {file_path} nie zawiera prawidłowych danych.")
        return None, None, None, "Cennik nie zawiera prawidłowych danych."

    if rounded_height > max(available_heights):
        logger.error(f"Podana wysokość {rounded_height} jest zbyt duża w pliku {file_path}.")
        return None, None, None, "Podana wysokość jest zbyt duża – brak w ofercie."

    nearest_width = next((w for w in available_widths if w >= rounded_width), None)
    nearest_height = next((h for h in available_heights if h >= rounded_height), None)

    if nearest_width is None:
        logger.error(f"Podana szerokość {rounded_width} jest zbyt duża w pliku {file_path}.")
        return None, None, None, "Podana szerokość jest zbyt duża – brak w ofercie."

    # Pobranie ceny z tabeli, obsługa braku wartości
    price = df.get(nearest_width, {}).get(nearest_height, None)

    if price is None:
        logger.error(f"Brak ceny dla wymiarów {rounded_width}x{rounded_height} w pliku {file_path}.")
        return None, None, None, "Brak ceny dla podanych wymiarów."

    # Dodanie ceny za usługi
    total_price = price
    if zybka == 25:
        total_price += 35  # Prowadzenie żyłki 25
    elif zybka == 50:
        total_price += 50  # Prowadzenie żyłki 50

    if karnisz == 30:
        total_price += 30  # Karnisz

    return round(total_price), nearest_width, nearest_height, None

@app.get("/cena/")
def get_cena(
    category: str,
    szerokosci: List[int] = Query(...),
    wysokosci: List[int] = Query(...),
    zybka1: int = Query(0),
    karnisz1: int = Query(0),
    zybka2: int = Query(0, alias="zybka2"),
    karnisz2: int = Query(0, alias="karnisz2"),
    zybka3: int = Query(0, alias="zybka3"),
    karnisz3: int = Query(0, alias="karnisz3"),
    # Możliwość rozszerzania na więcej par
):
    """Obliczanie ceny na podstawie wymiarów i usług"""
    results = []
    errors = []

    # Zbieramy wszystkie wartości szerokości, wysokości i usług
    for i, (szerokosc, wysokosc) in enumerate(zip(szerokosci, wysokosci)):
        zybka = locals().get(f"zybka{i + 1}")
        karnisz = locals().get(f"karnisz{i + 1}")
        total_price, zaokraglona_szerokosc, zaokraglona_wysokosc, error = get_price(
            category, szerokosc, wysokosc, zybka, karnisz
        )
        
        if error:
            results.append({"szerokosc": szerokosc, "wysokosc": wysokosc, "error": error})
            errors.append(error)
        else:
            results.append({
                "szerokosc": szerokosc,
                "wysokosc": wysokosc,
                "cena": total_price,
                "zaokraglona_szerokosc": zaokraglona_szerokosc,
                "zaokraglona_wysokosc": zaokraglona_wysokosc
            })

    if errors:
        return {"error": "Błąd w obliczeniach", "results": results}

    return {"results": results}

# Strona główna (index.html)
@app.get("/")
async def get_index():
    return FileResponse('static/index.html')  # Wskazuje na plik index.html w katalogu static

# Dynamicznie ustawiając host na Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Domyślnie 8000, ale na Renderze będzie to port z ENV
    uvicorn.run(app, host="0.0.0.0", port=port)
