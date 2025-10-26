# Faza 1: Fundament (Miesiąc 1)

**Status:** 🟡 W trakcie

**Cel:** Działający custom component z podstawową funkcjonalnością

**Czas trwania:** 4 tygodnie

---

## Cele fazy

- [x] Struktura custom component zgodna z wytycznymi HA
- [x] Możliwość konfiguracji przez UI (Config Flow)
- [x] Podstawowe climate entities (termostaty pokojowe)
- [x] Prosty regulator PI jako fallback (przed nauczeniem MPC)
- [x] Integracja z Home Assistant recorder (odczyt danych historycznych)

---

## Zadania

### 1.1 Struktura projektu

- [x] **T1.1.1:** Stwórz strukturę katalogów `custom_components/adaptive_thermal_control/`
  - **Priorytet:** Wysoki
  - **Czas:** 1h
  - **Zależności:** Brak
  - **Kryteria akceptacji:**
    - [x] Katalog `custom_components/adaptive_thermal_control/` istnieje
    - [x] Wszystkie wymagane pliki utworzone (__init__.py, manifest.json, etc.)
    - [x] Struktura zgodna z [HA Developer Docs](https://developers.home-assistant.io/docs/creating_component_index/)

- [x] **T1.1.2:** Stwórz manifest.json z metadanymi integracji
  - **Priorytet:** Wysoki
  - **Czas:** 30min
  - **Zależności:** T1.1.1
  - **Kryteria akceptacji:**
    - [x] `manifest.json` zawiera: name, domain, documentation, requirements, version
    - [x] Dependencies: `numpy>=1.21.0`, `scipy>=1.7.0`
    - [x] `codeowners` ustawione
    - [x] `iot_class`: "local_polling"

- [x] **T1.1.3:** Implementuj `__init__.py` - inicjalizacja integracji
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T1.1.2
  - **Kryteria akceptacji:**
    - [x] Funkcja `async_setup()` zaimplementowana
    - [x] Funkcja `async_setup_entry()` ładuje konfigurację
    - [x] Funkcja `async_unload_entry()` czyści zasoby
    - [x] Platformy (climate) są rejestrowane

- [x] **T1.1.4:** Stwórz `const.py` ze stałymi projektu
  - **Priorytet:** Średni
  - **Czas:** 1h
  - **Zależności:** T1.1.1
  - **Kryteria akceptacji:**
    - [x] DOMAIN = "adaptive_thermal_control"
    - [x] Wszystkie klucze konfiguracji jako stałe
    - [x] Default values (Kp, Ti, dt dla PI controller)
    - [x] Limity (min/max temp, timeout sensora)

---

### 1.2 Config Flow (konfiguracja UI)

- [x] **T1.2.1:** Implementuj `config_flow.py` - krok 1: konfiguracja globalna
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T1.1.3
  - **Kryteria akceptacji:**
    - [x] Formularz z polami:
      - Encja temperatury zewnętrznej (selector: entity, filter: sensor, optional)
      - Encja załączania CO (selector: entity, filter: switch, optional)
      - Encja ceny energii (selector: entity, filter: sensor, optional)
      - Encja pogody (selector: entity, filter: weather, optional)
      - Encja nasłonecznienia (selector: entity, filter: sensor, optional)
      - Encja zużycia energii (selector: entity, filter: sensor, optional)
      - Moc maksymalna pieca [kW] (number input, optional)
    - [x] Walidacja: sprawdź czy encje istnieją w HA
    - [x] Zapis konfiguracji do config entry

- [x] **T1.2.2:** Config Flow - krok 2: dodawanie termostatu
  - **Priorytet:** Wysoki
  - **Czas:** 5h
  - **Zależności:** T1.2.1
  - **Kryteria akceptacji:**
    - [x] Formularz z polami:
      - Nazwa pomieszczenia (text)
      - Encja temperatury pokoju (selector: entity, filter: sensor, **required**)
      - Encje sterujące zaworami (selector: entity, multiple, filter: switch/valve/number, **required**)
      - Encje temp. wejścia/wyjścia wody (selector: entity, multiple, optional)
      - Czas otwarcia/zamknięcia zaworu [s] (number, default: 45, optional)
      - Sąsiadujące pomieszczenia (multi-select innych termostatów, optional)
      - Orientacja okien (multi-select: N, S, E, W, NE, SE, SW, NW, optional)
      - Powierzchnia [m²] (number, optional)
      - Temperatura minimalna [°C] (number, default: 15, optional)
      - Temperatura maksymalna [°C] (number, default: 28, optional)
    - [x] Możliwość dodania wielu termostatów (przycisk "Dodaj kolejny")
    - [x] Walidacja: wymagane pola nie mogą być puste

- [x] **T1.2.3:** Options Flow - edycja konfiguracji po instalacji
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T1.2.2
  - **Kryteria akceptacji:**
    - [x] Możliwość edycji konfiguracji globalnej
    - [x] Możliwość edycji każdego termostatu
    - [x] Możliwość usunięcia termostatu
    - [x] Restart integracji po zapisaniu zmian

- [ ] **T1.2.4:** Testy Config Flow
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T1.2.3
  - **Kryteria akceptacji:**
    - [ ] Test przypadku sukcesu (poprawna konfiguracja)
    - [ ] Test walidacji (błędne encje)
    - [ ] Test edycji konfiguracji
    - [ ] Test usuwania termostatu

---

### 1.3 Climate Platform

- [x] **T1.3.1:** Stwórz `climate.py` - podstawowa klasa climate entity
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T1.1.3
  - **Kryteria akceptacji:**
    - [x] Klasa `AdaptiveThermalClimate(ClimateEntity)` zaimplementowana
    - [x] Properties: temperature, target_temperature, hvac_mode, hvac_action
    - [x] Supported features: TARGET_TEMPERATURE, PRESET_MODE
    - [x] HVAC modes: OFF, HEAT
    - [x] Preset modes: HOME, AWAY, SLEEP, MANUAL

- [x] **T1.3.2:** Implementuj obsługę stanów i atrybutów
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T1.3.1
  - **Kryteria akceptacji:**
    - [x] `current_temperature` czyta z sensora temperatury pokoju
    - [x] `target_temperature` zapisuje/odczytuje nastawę
    - [x] `hvac_mode` obsługuje OFF/HEAT
    - [x] `hvac_action` pokazuje IDLE/HEATING
    - [x] Dodatkowe atrybuty: valve_position, heating_demand (%)

- [x] **T1.3.3:** Implementuj service calls (set_temperature, set_hvac_mode, set_preset_mode)
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T1.3.2
  - **Kryteria akceptacji:**
    - [x] `async_set_temperature()` ustawia target_temperature
    - [x] `async_set_hvac_mode()` zmienia tryb OFF/HEAT
    - [x] `async_set_preset_mode()` zmienia preset HOME/AWAY/SLEEP/MANUAL
    - [x] Zmiany są zapisywane do state machine
    - [x] Event `state_changed` jest emitowany

- [x] **T1.3.4:** Implementuj sterowanie zaworami
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T1.3.3
  - **Kryteria akceptacji:**
    - [x] Metoda `_set_valve_position(position: float)` (0-100%)
    - [x] Obsługa wielu zaworów na jedno pomieszczenie
    - [x] Rozpoznawanie typu zaworu:
      - `number.*` → bezpośrednie ustawienie wartości
      - `switch.*` → ON/OFF (wymaga PWM w przyszłości)
      - `valve.*` → ustawienie pozycji
    - [x] Error handling (niedostępny zawór)

---

### 1.4 Prosty regulator PI (fallback)

- [x] **T1.4.1:** Implementuj klasę `PIController` w `pi_controller.py`
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** Brak
  - **Kryteria akceptacji:**
    - [x] Równanie PI: `u(t) = Kp·e(t) + (Kp/Ti)·∫e(τ)dτ`
    - [x] Dyskretna wersja z krokiem dt
    - [x] Anti-windup (back-calculation tracking)
    - [x] Parametry domyślne dla ogrzewania podłogowego:
      - Kp = 10.0
      - Ti = 1500s (25 min)
      - dt = 600s (10 min)
    - [x] Metoda `update(setpoint, measured, dt) -> control_signal`

- [x] **T1.4.2:** Integruj PI controller z climate entity
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T1.4.1, T1.3.4
  - **Kryteria akceptacji:**
    - [x] Climate entity używa PI gdy MPC niedostępny
    - [x] Co 10 minut: wywołaj `pi.update()`, ustaw zawór
    - [x] Logowanie decyzji regulatora (INFO level)
    - [x] Atrybut `controller_type: "PI"` w climate entity

- [ ] **T1.4.3:** Testy PI controller
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T1.4.2
  - **Kryteria akceptacji:**
    - [ ] Test odpowiedzi skokowej (step response)
    - [ ] Test anti-windup (nasycenie)
    - [ ] Test stabilności (brak oscylacji)
    - [ ] Porównanie z expected behavior z literatury

---

### 1.5 Integracja z Home Assistant Recorder

- [x] **T1.5.1:** Implementuj `history_helper.py` - odczyt danych historycznych
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T1.1.3
  - **Kryteria akceptacji:**
    - [x] Funkcja `get_history(entity_id, start_time, end_time) -> List[State]`
    - [x] Wykorzystanie `history.get_states()` z HA
    - [x] Filtrowanie nieprawidłowych danych (None, "unavailable", "unknown")
    - [x] Konwersja do NumPy arrays
    - [x] Cache dla często używanych zapytań

- [x] **T1.5.2:** Implementuj zbieranie danych treningowych
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T1.5.1
  - **Kryteria akceptacji:**
    - [x] Funkcja `collect_training_data(room_id, days=30) -> DataFrame`
    - [x] Zbiera dane:
      - Temperatura pokoju (co 1-5 min)
      - Temperatura zewnętrzna
      - Pozycje zaworów
      - Temperatury sąsiednich pokoi
    - [x] Resampling do 10-minutowych interwałów
    - [x] Obsługa brakujących danych (interpolacja liniowa)

- [x] **T1.5.3:** Walidacja minimalnej ilości danych
  - **Priorytet:** Średni
  - **Czas:** 1h
  - **Zależności:** T1.5.2
  - **Kryteria akceptacji:**
    - [x] Sprawdzenie czy jest min. 7 dni danych
    - [x] Ostrzeżenie jeśli danych < 7 dni → fallback na PI
    - [x] Informacja jeśli 7-30 dni → "uczenie się w toku"
    - [x] OK jeśli > 30 dni → "gotowy do MPC"

---

### 1.6 Coordinator (Data Update Coordinator)

- [x] **T1.6.1:** Implementuj `coordinator.py` - główny koordynator aktualizacji
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T1.3.2
  - **Kryteria akceptacji:**
    - [x] Klasa `AdaptiveThermalCoordinator(DataUpdateCoordinator)`
    - [x] Metoda `_async_update_data()` co 10 minut
    - [x] Zbiera dane ze wszystkich sensorów (temp pokoi, temp zewn, etc.)
    - [x] Wywołuje algorytm sterowania (PI lub MPC)
    - [x] Aktualizuje wszystkie climate entities
    - [x] Error handling (sensor unavailable)

- [x] **T1.6.2:** Implementuj logikę koordynacji stref (podstawowa wersja)
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T1.6.1
  - **Kryteria akceptacji:**
    - [x] Jeśli podana max moc pieca → oblicz łączną moc
    - [x] Jeśli przekroczono → podstawowy fair-share (proporcjonalne skalowanie)
    - [x] Logowanie ostrzeżenia jeśli limit przekroczony
    - [x] Atrybut `total_power_usage` w coordinator

---

### 1.7 Translations

- [x] **T1.7.1:** Stwórz tłumaczenia angielskie `translations/en.json`
  - **Priorytet:** Niski
  - **Czas:** 1h
  - **Zależności:** T1.2.2
  - **Kryteria akceptacji:**
    - [x] Config Flow strings (tytuły, opisy pól)
    - [x] Error messages
    - [x] State labels (HVAC modes, presets)

- [x] **T1.7.2:** Stwórz tłumaczenia polskie `translations/pl.json`
  - **Priorytet:** Niski
  - **Czas:** 1h
  - **Zależności:** T1.7.1
  - **Kryteria akceptacji:**
    - [x] Pełne tłumaczenie z en.json
    - [x] Poprawna polska terminologia HVAC

---

### 1.8 Testy i dokumentacja

- [ ] **T1.8.1:** Testy jednostkowe podstawowych klas
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T1.6.2
  - **Kryteria akceptacji:**
    - [ ] Test `PIController`
    - [ ] Test `AdaptiveThermalClimate`
    - [ ] Test `AdaptiveThermalCoordinator`
    - [ ] Coverage > 70%

- [ ] **T1.8.2:** Test integracyjny - instalacja w HA
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T1.8.1
  - **Kryteria akceptacji:**
    - [ ] Instalacja przez UI działa
    - [ ] Climate entity pojawia się w HA
    - [ ] Możliwość ustawienia temperatury
    - [ ] Zawory są sterowalne
    - [ ] Brak błędów w logach HA

- [ ] **T1.8.3:** Dokumentacja README.md (wersja podstawowa)
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T1.8.2
  - **Kryteria akceptacji:**
    - [ ] Opis projektu
    - [ ] Wymagania (HA wersja, hardware)
    - [ ] Instrukcja instalacji (manual)
    - [ ] Podstawowa konfiguracja
    - [ ] Known issues

---

## Kamienie milowe

- **M1.1:** Struktura custom component gotowa (koniec tygodnia 1)
- **M1.2:** Config Flow działa, można dodać termostat (koniec tygodnia 2)
- **M1.3:** PI controller działa, zawory są sterowalne (koniec tygodnia 3)
- **M1.4:** Wszystkie testy przechodzą, gotowe do Fazy 2 (koniec tygodnia 4)

---

## Metryki sukcesu fazy

- [ ] Integracja instaluje się przez UI bez błędów
- [ ] Climate entity działa (ustawienie temp, zmiana trybu)
- [ ] PI controller utrzymuje temperaturę ±1°C (tymczasowo, przed MPC)
- [ ] Brak błędów krytycznych w logach HA
- [ ] Pokrycie testami > 70%

---

## Notatki

- W tej fazie skupiamy się na **fundamentach** - nie implementujemy jeszcze MPC
- PI controller to tymczasowe rozwiązanie (fallback), zostanie zastąpiony w Fazie 3
- Config Flow musi być intuicyjny - to pierwsze co zobaczy użytkownik
- Priorytetyzuj stabilność nad funkcjonalnością - lepiej mniej ale działające

---

**Następna faza:** [Faza 2: Model termiczny](./phase-2-thermal-model.md)
