# TurboCamera - System Pomiaru Temperatury Ciała 🌡️

## 📋 Opis Projektu

**TurboCamera** to inżynierski system przesiewowego pomiaru temperatury ciała, integrujący termowizję z technologią IoT. Projekt rozwiązuje problem braku fabrycznej radiometrii w tanich modułach termowizyjnych poprzez zastosowanie autorskiego algorytmu **relatywnej estymacji temperatury** opartego na analizie kontrastu termicznego względem otoczenia.

System automatycznie wykrywa twarz, kompensuje wpływ izolatorów (okulary, fryzura) i przesyła wyniki do chmury, zapewniając bezkontaktowy i szybki pomiar.

## 🎯 Kluczowe Funkcjonalności
* **Wizja Maszynowa:** Detekcja sylwetki i ekstrakcja ROI twarzy w obrazie termicznym (OpenMV).
* **Algorytm "Contrast-to-Temperature":** Autorska metoda przeliczania jasności pikseli na temperaturę z wykorzystaniem dynamicznego punktu odniesienia (Anchor Point).
* **Inteligentna Kompensacja:** Wykrywanie okularów i grzywki z automatycznym dodawaniem offsetów korygujących (+0.5°C / +0.2°C).
* **Fuzja Sensorów:** Integracja kamery termowizyjnej z czujnikiem ultradźwiękowym (wyzwalanie pomiaru w zakresie 40-80 cm).
* **Interfejs Sprzętowy:** Wizualizacja na OLED (duże cyfry) + sygnalizacja LED (Status OK/Gorączka).
* **IoT & Cloud:** Transmisja wyników przez WiFi do dedykowanego Dashboardu (.NET).

## 🏗️ Architektura Systemu

```
┌─────────────────┐      UART      ┌─────────────────┐      WiFi      ┌─────────────────┐
│   OpenMV Camera │ ──────────────>│      ESP32      │ ──────────────>| Web Dashboard   │
│  (final_camera) │                │    (esp32.py)   │                │   (Dashboard)   │
│                 │                │                 │                │                 │
│ - Lepton Sensor │                │ - OLED Display  │                │ - REST API      │
│ - Face Detection│                │ - Ultrasonic    │                │ - Data Storage  │
│ - Temp. Calc.   │                │- Visualization  |                |- Visualization  |
└─────────────────┘                └─────────────────┘                └─────────────────┘
```

## 📦 Komponenty Sprzętowe

### Kamera OpenMV
- **Płytka**: OpenMV Cam H7 Plus
- **Czujnik termiczny**: Lepton 3.5
- **Rozdzielczość**: 160x120 pikseli
- **Zakres pomiarowy**: 32°C do +42°C
- **Dokładność**: ±0.2°C (po kalibracji)

### Moduł ESP32
- **Mikrokontroler**: ESP32
- **Wyświetlacz**: OLED SSD1306 128x64
- **Czujnik odległości**: HC-SR04 (ultradźwiękowy)
- **Komunikacja**: UART (115200 baud), WiFi 802.11 b/g/n

### Dashboard
- **Framework**: ASP.NET Core
- **Baza danych**: SQLite
- **Interfejs**: HTML, CSS, JavaScript
- **API**: RESTful JSON

## 🔧 Instalacja i Konfiguracja

### 1. Kamera OpenMV

1. Zainstaluj [OpenMV IDE](https://openmv.io/pages/download)
2. Podłącz kamerę OpenMV do komputera przez USB
3. Otwórz plik `final_camera.py` w OpenMV IDE
4. Wgraj skrypt na kamerę (Ctrl+F5 lub przycisk "Run")

**Parametry konfiguracyjne** (można dostosować w kodzie):
```python
BASE_TEMP = 36.6        # Bazowa temperatura ciała [°C]
ALARM_TEMP = 37.5       # Próg alarmowy [°C]
GAIN = 0.15             # Współczynnik wzmocnienia
TARGET_DIFF = 68        # Docelowa różnica wartości pikseli
```

### 2. Moduł ESP32

1. Zainstaluj [MicroPython](https://micropython.org/download/) na ESP32
2. Zainstaluj wymagane biblioteki:
   ```python
   # Wymagane biblioteki:
   # - hcsr04.py (czujnik ultradźwiękowy)
   # - ssd1306.py (wyświetlacz OLED)
   # - urequests (komunikacja HTTP)
   ```

3. Skonfiguruj parametry WiFi w pliku `esp32.py`:
   ```python
   WIFI_SSID = "nazwa_sieci"
   WIFI_PASSWORD = "haslo_sieci"
   ```

4. Wgraj plik `esp32.py` na ESP32

**Połączenia sprzętowe ESP32**:
- **UART**: TX=17, RX=16 (komunikacja z OpenMV)
- **HC-SR04**: Trigger=5, Echo=18
- **OLED**: SCL=22, SDA=21 (I2C)
- **LED A**: Pin 2 (zielony)
- **LED B**: Pin 4 (czerwony)

### 3. Dashboard Webowy

Uruchom
```
docker compose up
```

## 📡 Protokół Komunikacji

### OpenMV → ESP32 (UART, 115200 baud)

**Format danych podczas pomiaru**:
```
temperatura_ciała;temperatura_matrycy\n
```
Przykład: `37.2;25.5\n`

**Format danych w trybie bezczynności**:
```
IDLE;FPA:temperatura_matrycy;OBS:0\n
```
Przykład: `IDLE;FPA:25.5;OBS:0\n`

### ESP32 → Dashboard (HTTP POST)

**Endpoint**: `http://programowanie.org:8000/measurement`

**Format JSON**:
```json
{
  "Temperature": 37.2,
  "Distance": 65
}
```

## 🎨 Tryby Pracy Systemu

### 1. Tryb IDLE (Bezczynność)
- Wyświetlacz: "SYSTEM GOTOWY"
- Aktywność: Oczekiwanie na osobę

### 2. Tryb MEASURE (Pomiar)
- Wyświetlacz: Duże cyfry z temperaturą
- Aktywność: Aktywny pomiar i transmisja danych

### 3. Tryb HOLD (Przechowywanie)
- Wyświetlacz: Ostatni pomiar + "Ostatni pomiar"
- Aktywność: Wyświetlanie przez 5 sekund po opuszczeniu zakresu

## 🔬 Algorytm Pomiaru Temperatury

1. **Wykrywanie tła**: Pomiar wartości referencyjnej w regionie ANCHOR_ROI
2. **Wykrywanie ciała**: Identyfikacja obiektów termicznych powyżej progu (tło + margines)
3. **Ekstrakcja twarzy**: Analiza górnej części ciała (50% wysokości)
4. **Analiza przeszkód**: Wykrywanie grzywki i okularów przez porównanie regionów
5. **Obliczenie temperatury**:
   - Różnica termiczna: `max_val - bg_level`
   - Filtracja dolnoprzepustowa: `delta_filtered = 0.8 * delta_filtered + 0.2 * temp_change`
   - Konwersja: `temp = BASE_TEMP + (delta_filtered * GAIN)`
   - Kompensacja: `+0.2°C` (grzywka), `+0.5°C` (okulary)
6. **Walidacja**: Ograniczenie zakresu do 32.0-42.0°C

## 📊 Parametry Kalibracji

### Parametry wykrywania
- `ANCHOR_ROI`: (140, 0, 20, 20) - Region referencyjny tła
- `NOISE_MARGIN`: 20 - Margines szumu dla detekcji
- `FACE_TOP_RATIO`: 0.50 - Stosunek głowy do ciała
- `BODY_MIN_PIXELS`: 80 - Minimalna liczba pikseli ciała

### Parametry kompensacji
- `OBSTRUCTION_THRESHOLD`: 28 - Próg wykrywania przeszkód
- `OFFSET_BANGS`: 0.2°C - Kompensacja grzywki
- `OFFSET_GLASSES`: 0.5°C - Kompensacja okularów

### Parametry ESP32
- `ALARM_THRESHOLD`: 37.5°C - Próg alarmowy
- `DISPLAY_HOLD_TIME`: 5000 ms - Czas wyświetlania ostatniego pomiaru
- Zakres odległości: 40-80 cm - Optymalny zakres pomiarowy

## 🐛 Rozwiązywanie Problemów

### Kamera nie wykrywa twarzy
- Sprawdź oświetlenie termiczne (różnica temperatury tło-ciało)
- Dostosuj `NOISE_MARGIN` i `BODY_MIN_PIXELS`
- Upewnij się, że osoba jest w odpowiedniej odległości

### Nieprawidłowe odczyty temperatury
- Wykonaj kalibrację `BASE_TEMP` i `GAIN`
- Sprawdź czy `TARGET_DIFF` jest odpowiednio ustawiony
- Zweryfikuj kompensację przeszkód

### Brak komunikacji UART
- Sprawdź połączenia TX/RX między OpenMV a ESP32
- Zweryfikuj prędkość transmisji (115200 baud)
- Sprawdź czy oba urządzenia mają wspólne GND

### ESP32 nie łączy się z WiFi
- Sprawdź poprawność SSID i hasła
- Zweryfikuj zasięg sieci WiFi
- Sprawdź czy ESP32 obsługuje częstotliwość sieci (2.4 GHz)

### Dashboard nie odbiera danych
- Sprawdź czy serwer jest uruchomiony
- Zweryfikuj adres URL w kodzie ESP32
- Sprawdź logi serwera pod kątem błędów

## 📈 Wydajność Systemu

- **Częstotliwość pomiaru**: ~20 Hz (50 ms/cykl)
- **Czas odpowiedzi**: <100 ms (od wykrycia do wyświetlenia)
- **Dokładność pomiaru**: ±0.5°C (po kalibracji)
- **Zakres pomiarowy**: 40-80 cm od czujnika
- **Zużycie energii**: ~500 mA (OpenMV) + ~200 mA (ESP32)

## 🔒 Bezpieczeństwo

- System nie przechowuje danych osobowych
- Komunikacja WiFi powinna być szyfrowana (WPA2/WPA3)
- Dashboard powinien być zabezpieczony autoryzacją w środowisku produkcyjnym
- Dane pomiarowe są anonimowe (tylko temperatura i odległość)

## 📝 Licencja

Projekt edukacyjny - do użytku akademickiego.

## 👥 Autorzy

Projekt realizowany w ramach zajęć z PZSP1
Bartosz Grzanka
Jakub Złotnicki
Mikołaj Urbańczyk
Mateusz Marynowski

## 🔗 Linki

- [OpenMV Documentation](https://docs.openmv.io/)
- [MicroPython ESP32](https://docs.micropython.org/en/latest/esp32/quickref.html)
- [ASP.NET Core Documentation](https://docs.microsoft.com/aspnet/core)

---

**Uwaga**: System wymaga kalibracji przed użyciem produkcyjnym. Wszystkie parametry powinny być dostosowane do konkretnego środowiska i warunków pomiarowych.
