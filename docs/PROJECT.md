# Adaptive Thermal Control - Sterowanie ogrzewaniem podłogowym

## 1. Ogólny zarys projektu

Jest to zaawansowana integracja do Home Assistant (`adaptive_thermal_control`), która implementuje **predykcyjne sterowanie Model Predictive Control (MPC)** dla systemów ogrzewania podłogowego. System adaptacyjnie uczy się z historycznych danych i optymalizuje pracę ogrzewania, aby:

- Utrzymywać komfortową temperaturę w pomieszczeniach przy minimalnym zużyciu energii
- Predykcyjnie reagować na zmiany warunków zewnętrznych
- Optymalizować koszty ogrzewania wykorzystując taryfy cenowe
- Zarządzać wielostrefowym systemem grzewczym z ograniczeniami mocy pieca

### 1.1 Kluczowe cechy algorytmu

**Uczenie i adaptacja:**
- Uczenie parametrów modelu termicznego z danych historycznych (Home Assistant recorder)
- Adaptacyjne dostrajanie raz dziennie
- Identyfikacja charakterystyki termicznej każdego pomieszczenia

**Uwzględniane czynniki:**
- ✅ Temperatura zewnętrzna (aktualna i prognoza)
- ✅ Prognoza pogody (temperatura, nasłonecznienie)
- ✅ Temperatury sąsiednich pomieszczeń (migracja cieplna między pokojami)
- ✅ Maksymalna moc pieca (koordynacja obiegów grzewczych)
- ✅ Temperatura wejścia i wyjścia wody dla każdego obiegu
- ✅ Nasłonecznienie z orientacją okien (prognoza energii solarnej → ciepło przez okna)
- ✅ Koszty ogrzewania (optymalizacja "grzej teraz bo później drożej")
- ✅ Historia poprzednich stanów grzania
- ✅ Czas doby, dzień tygodnia, sezon

### 1.2 Cel biznesowy

- **Oszczędność energii:** 20-40% redukcja zużycia vs. sterowanie ON/OFF
- **Optymalizacja kosztów:** 10-15% redukcja kosztów poprzez wykorzystanie tanich taryf
- **Komfort:** utrzymanie temperatury w zakresie ±0.5°C od nastawy
- **Skalowalność:** obsługa 1-20+ pomieszczeń na Raspberry Pi 5

---

## 2. Architektura systemu

### 2.1 Struktura integracji Home Assistant

**Typ:** Custom Component dostępny przez HACS
**Folder:** `custom_components/adaptive_thermal_control/`
**Konfiguracja:** Przez UI (Config Flow)
**Platforma:** Climate entities (termostaty pokojowe)

**Struktura plików:**
```
custom_components/adaptive_thermal_control/
├── __init__.py                 # Inicjalizacja integracji
├── manifest.json               # Manifest z zależnościami
├── config_flow.py              # Konfiguracja przez UI
├── const.py                    # Stałe i konfiguracja
├── climate.py                  # Climate platform (termostaty)
├── coordinator.py              # Data Update Coordinator
├── mpc_controller.py           # Algorytm MPC
├── thermal_model.py            # Model termiczny pomieszczeń
├── sensor.py                   # Sensory diagnostyczne
└── translations/
    ├── en.json
    └── pl.json
```

### 2.2 Model danych

#### Termostat (Climate Entity)
Każde pomieszczenie = jedna climate entity z parametrami:

**Wymagane:**
- Encja sensora temperatury pokoju (`sensor.salon_temperature`)
- Encje sterujące zaworami (`valve.salon_zone_1`, `valve.salon_zone_2`)

**Opcjonalne:**
- Encje temperatury wejścia/wyjścia wody na obiegu
- Sąsiadujące pomieszczenia (lista entity_id innych termostatów)
- Orientacja okien (N, S, E, W, NE, SE, SW, NW) - może być wiele okien
- Powierzchnia pomieszczenia [m²]
- Czas otwarcia/zamknięcia zaworu [s]

**Tryby działania:**
- `heat` - normalne grzanie (algorytm MPC)
- `off` - wyłączone
- Preset modes:
  - `home` - pełny komfort
  - `away` - obniżona temperatura (ekonomia)
  - `sleep` - temperatura nocna
  - `manual` - wyłączenie automatyki, ręczne sterowanie

**Schedule:** Harmonogram trybów (integracja z zewnętrznym schedulerem lub wbudowany)

#### Konfiguracja globalna integracji

**Opcjonalne encje:**
- Encja temperatury zewnętrznej (`sensor.outside_temperature`)
- Encja włączania CO (`switch.boiler_master`)
- Encja ceny energii (`sensor.energy_price_current`)
- Encja pogody (`weather.home`)
- Encja nasłonecznienia - moc na m² (`sensor.solar_irradiance`)
- Encja bieżącego zużycia energii (`sensor.heating_power_consumption`)

**Parametry pieca:**
- Maksymalna moc pieca [kW] (opcjonalne)
- Temperatura wody grzewczej (stała, np. 45°C)

---

## 3. Algorytm sterowania - Model Predictive Control (MPC)

### 3.1 Podstawy MPC

**Zasada działania:**
1. Na podstawie modelu termicznego **predykcja** temperatury na horyzoncie Np (24-48 kroków = 4-8 godzin)
2. **Optymalizacja** sekwencji sterowania minimalizująca funkcję kosztu (komfort + energia + koszty)
3. **Wykonanie** tylko pierwszego kroku sterowania (receding horizon)
4. Po okresie Δt (10 minut) - powtórz proces

**Funkcja kosztu:**
```
J = Σ[k=0..Np] { w_komfort·(T(k) - T_zadana)²
                + w_energia·P(k)²
                + w_gładkość·ΔP(k)²
                + w_koszt·cena(k)·P(k) }
```

gdzie:
- `w_komfort = 0.7` - priorytet utrzymania temperatury
- `w_energia = 0.2` - minimalizacja zużycia energii
- `w_gładkość = 0.1` - unikanie gwałtownych zmian
- `w_koszt` - opcjonalny, jeśli podana encja cen

**Ograniczenia:**
- `0 ≤ pozycja_zaworu ≤ 100%`
- `T_min ≤ T_pokoju ≤ T_max` (z konfiguracji)
- Suma mocy wszystkich obiegów ≤ Moc_max_pieca

### 3.2 Model termiczny

**Model 1R1C (uproszczony) dla jednego pomieszczenia:**

```
C·dT/dt = Q_grzanie - (T - T_zewn)/R + Q_sąsiedzi + Q_słońce
```

gdzie:
- `C` - pojemność cieplna pomieszczenia [J/K]
- `R` - opór termiczny [K/W]
- `Q_grzanie` - moc grzania z obiegu [W]
- `Q_sąsiedzi` - przepływ ciepła z sąsiednich pomieszczeń
- `Q_słońce` - zyski słoneczne przez okna

**Dyskretyzacja (krok Δt = 10 minut):**

```python
T(k+1) = A·T(k) + B·u(k) + B_d·d(k)

A = exp(-Δt / (R·C))
B = R·(1 - A)
d(k) = [T_zewn(k), T_sąsiedzi(k), irradiance(k)]
```

**Parametry uczone:**
- `R`, `C` - identyfikowane z danych historycznych (Recursive Least Squares)
- Współczynniki wpływu sąsiadów
- Współczynnik absorpcji energii słonecznej przez okna

### 3.3 Strategia koordynacji stref

**Rotacja fair-share** (z REQUIREMENTS.md):

Gdy wszystkie pomieszczenia "chcą" ciepła, ale moc pieca ograniczona:

1. **Oblicz priorytet** dla każdego pomieszczenia:
   ```
   priorytet = (T_zadana - T_aktualna) × waga_trybu × waga_powierzchni
   ```

2. **Sortuj** malejąco po priorytecie

3. **Przydziel moc** w kolejności priorytetu, aż do wyczerpania mocy pieca

4. **Rotacja**: pokoje z niższym priorytetem dostaną moc w następnym cyklu

### 3.4 Implementacja PWM dla zaworów bez pozycjonowania

Dla zaworów typu switch (ON/OFF bez regulacji):

**Long PWM** (okres 30-60 minut):
```
Jeśli MPC zwróci: "zawór 65%"
→ Otwórz na 65% czasu w oknie 30 min
→ Przykład: włącz na 19.5 min, wyłącz na 10.5 min
```

Uwzględnienie czasu otwarcia/zamknięcia zaworu (30-60s z konfiguracji).

---

## 4. Dane wejściowe i integracje zewnętrzne

### 4.1 Prognoza pogody

**Źródło:** Encja podana w konfiguracji (np. `weather.home`)
**Wykorzystanie:**
- Temperatura zewnętrzna (prognoza do 24h)
- Nasłonecznienie (jeśli dostępne)

**Format:** Wykorzystanie atrybutu `forecast` z weather entity

### 4.2 Nasłonecznienie i orientacja okien

**Źródło:** Encja prognozy energii fotowoltaicznej
**Przykład:** `sensor.solcast_pv_forecast_power_now`

**Kalkulacja ciepła przez okna:**
```python
Q_słońce = Σ[okna] (energia_PV(t) × orientacja_okna × współczynnik_okna × powierzchnia_okna)
```

**Orientacja okien:**
- Konfigurowane per pomieszczenie
- Wiele okien o różnych orientacjach

### 4.3 Ceny energii

**Źródło:** Encja podana w konfiguracji
**Przykład:** `sensor.energa_taryfa_current` + `sensor.energa_taryfa_forecast`

**Strategia:** "Podgrzej teraz bo później drożej"
- MPC widzi prognozę cen na horyzont 24h
- Preferuje grzanie w tańszych godzinach
- Wykorzystuje bezwładność termiczną jako magazyn energii

---

## 5. Tryby pracy i bezpieczeństwo

### 5.1 Fallback i tryby awaryjne

**Brak danych do uczenia modelu:**
- Fallback: prosty regulator PI z wartościami domyślnymi
- Po zebraniu min. 7 dni danych → przejście na MPC

**Brak danych z sensorów:**
- **Temperatura pokoju (wymagana):** BŁĄD - wyłączenie grzania pomieszczenia
- **Temperatura zewnętrzna (opcjonalna):** OSTRZEŻENIE - kontynuuj z ostatnią znaną wartością
- **Prognoza pogody (opcjonalna):** Użyj aktualnej temperatury jako prognozy
- **Nasłonecznienie (opcjonalne):** Załóż Q_słońce = 0
- **Cena energii (opcjonalna):** Pomiń optymalizację kosztową

### 5.2 Limity bezpieczeństwa

**Z konfiguracji (per termostat):**
- Temperatura maksymalna (wyłączenie awaryjne)
- Temperatura minimalna (ochrona przed zamarznięciem)

**Timeout sensora:** 30 minut
- Po 30 min braku odczytu → error state

**Brak limitu czasu grzania:** System może grzać ciągle jeśli potrzeba

### 5.3 Tryb ręczny

**Do przemyślenia później** (z REQUIREMENTS.md)

Wstępna koncepcja:
- Preset `manual` wyłącza algorytm MPC
- Użytkownik ręcznie ustawia pozycję zaworów przez service call

---

## 6. UI i konfiguracja

### 6.1 Config Flow - konfiguracja początkowa

**Krok 1: Globalna konfiguracja integracji**
- Encja temperatury zewnętrznej (opcjonalne)
- Encja włączania CO (opcjonalne)
- Encja ceny energii (opcjonalne)
- Encja pogody (opcjonalne)
- Encja nasłonecznienia (opcjonalne)
- Encja zużycia energii (opcjonalne)
- Maksymalna moc pieca [kW] (opcjonalne)

**Krok 2: Dodawanie termostatów (pokoi)**

Dla każdego pomieszczenia:
- **Wymagane:**
  - Encja temperatury w pokoju
  - Encje sterujące zaworami (może być wiele)

- **Opcjonalne:**
  - Encje temperatury wejścia/wyjścia wody
  - Czas otwarcia/zamknięcia zaworu [s]
  - Sąsiadujące pomieszczenia (multi-select innych termostatów)
  - Orientacja okien (multi-select: N, S, E, W, NE, SE, SW, NW)
  - Powierzchnia [m²]
  - Temperatura minimalna [°C]
  - Temperatura maksymalna [°C]

### 6.2 Dashboardy i karty

**Encje diagnostyczne (sensory):**
- `sensor.adaptive_thermal_[pokój]_heating_demand` - aktualne zapotrzebowanie na ciepło [%]
- `sensor.adaptive_thermal_[pokój]_prediction_error` - błąd predykcji modelu [°C]
- `sensor.adaptive_thermal_[pokój]_next_action` - tekstowy opis dlaczego grzeje/nie grzeje
- `sensor.adaptive_thermal_global_total_power` - suma mocy wszystkich obiegów [kW]
- `sensor.adaptive_thermal_global_efficiency` - efektywność algorytmu [%]

**Karty Lovelace (sugerowane):**
- Thermostat card dla każdego pomieszczenia
- Apex Charts z historią temperatur
- Gauge card z wydajnością algorytmu
- Entities card z diagnostyką

---

## 7. Persystencja i diagnostyka

### 7.1 Zapisywanie stanu

**Parametry modelu:**
- Zapisywane w plikach JSON w `config/.storage/adaptive_thermal_control_models.json`
- Automatyczny zapis po każdym update modelu (raz dziennie)

**Struktura:**
```json
{
  "climate.salon": {
    "R": 0.0025,
    "C": 4.5e6,
    "tau": 11250,
    "neighbors_influence": {"climate.kuchnia": 0.15},
    "solar_coefficient": 0.65,
    "last_update": "2025-10-26T10:00:00Z"
  }
}
```

### 7.2 Logi i debugowanie

**Poziomy logowania:**
- `INFO` - decyzje sterowania, stan systemu
- `DEBUG` - szczegóły obliczeń MPC, wartości predykcji
- `WARNING` - brakujące dane, fallback na PI
- `ERROR` - błędy krytyczne (brak sensora temperatury)

**Logi zawierają:**
- Timestamp
- Pomieszczenie
- Aktualna temperatura / zadana
- Wyjście algorytmu (pozycja zaworu)
- Dlaczego podjęto decyzję (reasoning)

---

## 8. Roadmap wdrożenia

### Faza 1: Fundament (Miesiąc 1)
**Cel:** Działający custom component z podstawową funkcjonalnością

- [ ] Struktura custom component
- [ ] Config Flow (konfiguracja przez UI)
- [ ] Climate platform (podstawowe termostaty)
- [ ] Prosty regulator PI jako fallback
- [ ] Integracja z Home Assistant recorder (odczyt danych historycznych)

### Faza 2: Model termiczny (Miesiąc 2)
**Cel:** Uczenie się parametrów z danych

- [ ] Implementacja modelu 1R1C
- [ ] Algorytm identyfikacji parametrów (Recursive Least Squares)
- [ ] Zbieranie danych historycznych (7-30 dni)
- [ ] Walidacja modelu (porównanie predykcji z rzeczywistością)

### Faza 3: MPC Core (Miesiąc 3-4)
**Cel:** Działający algorytm MPC

- [ ] Implementacja MPC z scipy.optimize
- [ ] Funkcja kosztu (komfort + energia)
- [ ] Horyzont predykcji 4-8 godzin
- [ ] Optymalizacja wydajności (cache, pre-computing)
- [ ] Testy na danych rzeczywistych

### Faza 4: Zaawansowane funkcje (Miesiąc 5)
**Cel:** Pełna funkcjonalność z REQUIREMENTS.md

- [ ] Integracja prognozy pogody
- [ ] Nasłonecznienie + orientacja okien
- [ ] Wpływ sąsiadujących pomieszczeń
- [ ] Koordynacja stref (fair-share, limity mocy)
- [ ] PWM dla zaworów ON/OFF

### Faza 5: Optymalizacja kosztów (Miesiąc 6)
**Cel:** Inteligentna optymalizacja finansowa

- [ ] Integracja encji cen energii
- [ ] Strategia "grzej teraz bo później drożej"
- [ ] Dashboard z kosztami i oszczędnościami
- [ ] Fine-tuning wag w funkcji kosztu

### Faza 6: Publikacja HACS (Miesiąc 6+)
**Cel:** Gotowy do publicznego release

- [ ] Dokumentacja użytkownika (README, wiki)
- [ ] Przykładowe konfiguracje
- [ ] Tłumaczenia (EN, PL)
- [ ] CI/CD (automated tests)
- [ ] Publikacja w HACS

---

## 9. Wymagania techniczne

### 9.1 Zależności Python

**Core:**
- `numpy >= 1.21.0` - obliczenia numeryczne
- `scipy >= 1.7.0` - optymalizacja (minimize, SLSQP)

**Home Assistant:**
- `homeassistant >= 2024.1.0`

### 9.2 Wydajność na Raspberry Pi 4/5

**Założenia:**
- 20 pomieszczeń
- Horyzont predykcji Np = 24 (4 godziny)
- Horyzont sterowania Nc = 12 (2 godziny)
- Okres aktualizacji 10 minut

**Oczekiwany czas obliczeń:**
- Model 1R1C: 0.5-2 sekundy na cykl MPC
- Model 2R2C: 2-5 sekund na cykl MPC

**Optymalizacje:**
- Kompilacja JIT z Numba (opcjonalnie)
- Cache obliczeń macierzy stanu
- Warm-start dla solvera (użyj poprzedniego rozwiązania)

### 9.3 Pamięć

**RAM:** ~50-100 MB dla całej integracji (20 pokoi)

---

## 10. Dodatkowe uwagi

### 10.1 Różnice od standardowych termostatów

**Standardowy termostat (ON/OFF):**
- Reaguje tylko na aktualną temperaturę
- Duże wahania (histereза ±1-2°C)
- Marnotrawstwo energii

**Regulator PI:**
- Gładsze sterowanie
- Mniejsze wahania (±0.5°C)
- Brak predykcji

**MPC (ten projekt):**
- Predykcja przyszłych stanów
- Wykorzystanie prognozy pogody
- Optymalizacja kosztów energii
- Najlepsza wydajność dla systemów o wysokiej bezwładności (ogrzewanie podłogowe)

### 10.2 Typowe oszczędności (z literatury)

- **Energia:** 20-40% vs. ON/OFF
- **Koszty:** 10-15% dodatkowa redukcja dzięki optymalizacji taryf
- **Komfort:** 79-98% redukcja naruszeń komfortu (przekroczeń zadanej temperatury)

### 10.3 Czas uczenia się systemu

- **Minimum:** 7 dni danych historycznych
- **Optymalnie:** 30 dni (różne warunki pogodowe)
- **Pełna adaptacja:** 3 miesiące (cały sezon grzewczy)

---

## 11. Licencja i rozwój

**Licencja:** MIT (open source)
**Repozytorium:** GitHub (do utworzenia)
**HACS:** Dostępny jako custom repository
**Język:** Polski i angielski

**Community:**
- Zachęcamy do zgłaszania issues
- Pull requests mile widziane
- Forum Home Assistant dla wsparcia

---

## 12. Referencje

- [MPC_THEORY_AND_PRACTICE.md](MPC_THEORY_AND_PRACTICE.md) - Teoria i praktyka MPC
- [REQUIREMENTS.md](REQUIREMENTS.md) - Szczegółowa specyfikacja wymagań
