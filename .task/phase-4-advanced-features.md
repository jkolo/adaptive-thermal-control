# Faza 4: Zaawansowane funkcje (Miesiąc 5)

**Status:** 🔴 Nie rozpoczęte

**Cel:** Pełna funkcjonalność z inteligentną koordynacją i prognozami

**Czas trwania:** 4 tygodnie

**Zależności:** Faza 3 zakończona

---

## Cele fazy

- [ ] Integracja prognozy pogody do MPC
- [ ] Nasłonecznienie + orientacja okien
- [ ] Wpływ sąsiednich pomieszczeń (thermal coupling)
- [ ] Koordynacja stref (fair-share, limity mocy pieca)
- [ ] PWM dla zaworów ON/OFF

---

## Zadania

### 4.1 Prognoza pogody w MPC

- [ ] **T4.1.1:** Rozszerz ForecastProvider o szczegółową prognozę
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** Faza 3 zakończona
  - **Kryteria akceptacji:**
    - [ ] Pobierz forecast z weather entity
    - [ ] Wyciągnij:
      - Temperatura [°C]
      - Wiatr (wpływ na straty ciepła)
      - Zachmurzenie (wpływ na nasłonecznienie)
    - [ ] Interpolacja do kroków 10-minutowych
    - [ ] Fallback: jeśli brak prognozy → użyj aktualnych wartości

- [ ] **T4.1.2:** Uwzględnienie prognozy w funkcji kosztu
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T4.1.1
  - **Kryteria akceptacji:**
    - [ ] MPC widzi że za 3h będzie cieplej → może zmniejszyć grzanie teraz
    - [ ] MPC widzi że za 3h będzie zimniej → może pre-ogrzać
    - [ ] Model termiczny używa prognozy jako d_forecast
    - [ ] Logowanie: "Weather forecast: temp drops 5°C in 2h, pre-heating"

---

### 4.2 Nasłonecznienie i orientacja okien

- [ ] **T4.2.1:** Implementuj `solar_calculator.py` - obliczanie zysków solarnych
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T4.1.1
  - **Kryteria akceptacji:**
    - [ ] Wzór: `Q_solar = η · irradiance · A_windows · orientation_factor`
    - [ ] Parametry z Config Flow:
      - Orientacja okien (N, S, E, W, NE, SE, SW, NW)
      - Powierzchnia okien (opcjonalnie, default z powierzchni pokoju)
    - [ ] Orientation factors (uproszczone):
      - S: 1.0 (pełne słońce w południe)
      - E/W: 0.7 (słońce rano/wieczorem)
      - N: 0.3 (rozproszone światło)
    - [ ] Współczynnik absorpcji η = 0.6 (okna + ściany)

- [ ] **T4.2.2:** Integracja z encją prognozy solarnej
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T4.2.1
  - **Kryteria akceptacji:**
    - [ ] Pobierz prognozę z encji (np. `sensor.solcast_pv_forecast_power`)
    - [ ] Przelicz moc PV na irradiance [W/m²]
    - [ ] Uwzględnij w modelu termicznym jako dodatkowe Q_solar
    - [ ] Jeśli brak encji → Q_solar = 0 (graceful degradation)

- [ ] **T4.2.3:** Rozszerzenie modelu termicznego o Q_solar
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T4.2.2
  - **Kryteria akceptacji:**
    - [ ] Równanie: `C·dT/dt = Q_heating + Q_solar - (T - T_outdoor)/R`
    - [ ] Q_solar jako dodatkowy input w predykcji
    - [ ] MPC widzi prognozę słońca → zmniejsza grzanie zawczasu
    - [ ] Estymacja współczynnika η z danych historycznych (RLS)

---

### 4.3 Wpływ sąsiednich pomieszczeń

- [ ] **T4.3.1:** Implementuj thermal coupling między pokojami
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** Faza 2 zakończona
  - **Kryteria akceptacji:**
    - [ ] Model: `Q_neighbors = Σ[i] k_i · (T_i - T_room)`
    - [ ] k_i - współczynnik wymiany ciepła z sąsiadem i
    - [ ] Sąsiedzi definiowani w Config Flow (multi-select)
    - [ ] Automatyczna estymacja k_i z danych historycznych

- [ ] **T4.3.2:** Multi-room coordination w MPC
  - **Priorytet:** Średni
  - **Czas:** 5h
  - **Zależności:** T4.3.1
  - **Kryteria akceptacji:**
    - [ ] MPC dla wielu pokoi jednocześnie (coupled problem)
    - [ ] Macierze stanu rozszerzone na N pokoi:
      - x = [T_1, T_2, ..., T_N]
      - u = [P_1, P_2, ..., P_N]
    - [ ] Macierz A uwzględnia thermal coupling
    - [ ] Alternatywa (prostsza): decentralized MPC z koordynacją

- [ ] **T4.3.3:** Strategia decentralizowana z koordynacją
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T4.3.1
  - **Kryteria akceptacji:**
    - [ ] Każdy pokój ma własny MPC controller
    - [ ] Każdy MPC dostaje info o temperaturach sąsiadów
    - [ ] Koordynator: dzieli moc pieca między pokoje (fair-share)
    - [ ] Prostsze w implementacji niż centralized MPC
    - [ ] Skaluje lepiej (złożoność O(N) zamiast O(N³))

---

### 4.4 Koordynacja stref (fair-share)

- [ ] **T4.4.1:** Implementuj `zone_coordinator.py` - koordynator stref
  - **Priorytet:** Wysoki
  - **Czas:** 5h
  - **Zależności:** Faza 3 zakończona
  - **Kryteria akceptacji:**
    - [ ] Klasa `ZoneCoordinator(max_boiler_power: float)`
    - [ ] Co 10 min:
      1. Zbiera zapotrzebowanie na moc od wszystkich MPC
      2. Jeśli suma ≤ max_power → przydziel pełne zapotrzebowanie
      3. Jeśli suma > max_power → fair-share allocation
    - [ ] Metoda `allocate_power(demands: Dict[str, float]) -> Dict[str, float]`

- [ ] **T4.4.2:** Algorytm fair-share z priorytetami
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T4.4.1
  - **Kryteria akceptacji:**
    - [ ] Priorytet = (T_setpoint - T_actual) × weight_mode × weight_area
    - [ ] Weights:
      - `weight_mode`: home=1.0, away=0.5, sleep=0.7
      - `weight_area`: (area / 20m²) # normalizacja
    - [ ] Sortuj pokoje po priorytecie (malejąco)
    - [ ] Przydziel moc w kolejności do wyczerpania max_boiler_power
    - [ ] Pozostałe pokoje dostają 0 (lub minimum)
    - [ ] Rotacja: pokoje z niskim priorytetem dostaną moc w kolejnym cyklu

- [ ] **T4.4.3:** Integracja z coordinator
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T4.4.2
  - **Kryteria akceptacji:**
    - [ ] W głównym coordinator:
      ```python
      demands = {room: mpc.compute_control(...) for room in rooms}
      allocated = zone_coordinator.allocate_power(demands)
      for room, power in allocated.items():
          room.set_valve_from_power(power)
      ```
    - [ ] Logowanie: "Power allocation: salon=3kW, kuchnia=2kW, sypialnia=0kW (limit reached)"
    - [ ] Sensor: `sensor.adaptive_thermal_global_power_usage` [kW]

---

### 4.5 PWM dla zaworów ON/OFF

- [x] **T4.5.1:** Implementuj `pwm_controller.py` - Long PWM ✅
  - **Priorytet:** Wysoki
  - **Czas:** 4h → 2.5h (actual)
  - **Zależności:** Faza 3 zakończona
  - **Kryteria akceptacji:**
    - [x] Klasa `PWMController(period: float = 1800)` ✅ # 30 min period
    - [x] Metoda `set_duty_cycle(valve_entity, duty: float)` ✅
    - [x] Duty cycle ∈ [0, 100]% ✅
    - [x] Przykład: duty=65% w okresie 30min → ON przez 19.5 min, OFF przez 10.5 min ✅
    - [x] Uwzględnienie czasu otwarcia/zamknięcia zaworu (placeholder) ✅
  - **Implementacja:**
    - Nowy moduł: `pwm_controller.py` (430 lines)
    - Parametry: `period`, `min_on_time`, `min_off_time`
    - Edge cases: 0% = OFF, 100% = ON (no PWM)
    - Minimum time enforcement prevents rapid cycling
    - Multiple valve support with independent schedules
    - Comprehensive error handling

- [x] **T4.5.2:** Scheduler PWM ✅
  - **Priorytet:** Wysoki
  - **Czas:** 3h → included in T4.5.1
  - **Zależności:** T4.5.1
  - **Kryteria akceptacji:**
    - [x] Async scheduler: planuje przełączenia zaworu ✅
    - [x] Wykorzystanie `async_track_point_in_time()` z HA ✅
    - [x] Cancellable (jeśli duty cycle się zmieni) ✅
  - **Implementacja:**
    - Scheduler zintegrowany w PWMController
    - Automatic cycle continuation: ON → OFF → ON → ...
    - Cancel tokens dla pending commands
    - Schedule tracking per valve (dict structure)

- [x] **T4.5.3:** Auto-detect typu zaworu ✅
  - **Priorytet:** Średni
  - **Czas:** 2h → 1h (actual)
  - **Zależności:** T4.5.2
  - **Kryteria akceptacji:**
    - [x] Rozpoznaj typ encji zaworu: ✅
      - `number.*` → position control
      - `valve.*` with set_position → position control
      - `switch.*` → PWM
      - `valve.*` without set_position → PWM
    - [x] Atrybut climate entity: `valve_control_mode: "position" | "pwm"` ✅
    - [x] Automatyczne, użytkownik nie musi konfigurować ✅
  - **Implementacja:**
    - Dodano `_detect_valve_control_mode()` w climate.py
    - Detection podczas __init__ climate entity
    - Attribute exposed in extra_state_attributes
    - Integracja w `_set_single_valve()` - auto PWM/position switch
    - Cleanup w `async_will_remove_from_hass()`

- [x] **T4.5.4:** Testy PWM ✅
  - **Priorytet:** Średni
  - **Czas:** 2h → 1.5h (actual)
  - **Zależności:** T4.5.3
  - **Kryteria akceptacji:**
    - [x] Test: duty=50% → zawór 50% czasu ON ✅
    - [x] Test: uwzględnienie opóźnień otwarcia/zamknięcia ✅
    - [x] Test: zmiana duty cycle w trakcie okresu ✅
    - [x] Test: wielokrotne cykle PWM (stabilność) ✅
  - **Implementacja:**
    - 18 comprehensive unit tests (100% pass)
    - Test coverage:
      - Initialization
      - Edge cases (0%, 100%)
      - Duty cycle calculations (50%, 65%, 95%)
      - Minimum time enforcement
      - Schedule cancellation
      - Invalid inputs (ValueError)
      - Multiple valve independence
      - Service call failures
      - Custom periods (10min, 30min, 60min)

---

### 4.6 Sensory diagnostyczne i monitoring

- [ ] **T4.6.1:** Sensory globalnej koordynacji
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T4.4.3
  - **Kryteria akceptacji:**
    - [ ] `sensor.adaptive_thermal_global_total_power` - suma mocy [kW]
    - [ ] `sensor.adaptive_thermal_global_power_limit` - max moc pieca [kW]
    - [ ] `sensor.adaptive_thermal_global_power_usage_percent` - % limitu
    - [ ] `sensor.adaptive_thermal_global_zones_heating` - liczba aktywnych stref

- [ ] **T4.6.2:** Sensor "dlaczego nie grzeje?"
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T4.4.3
  - **Kryteria akceptacji:**
    - [ ] `sensor.adaptive_thermal_[pokój]_heating_status`
    - [ ] Stany tekstowe:
      - "Heating - MPC optimal control"
      - "Idle - temperature at setpoint"
      - "Waiting - power limit reached, priority low"
      - "Waiting - solar gains sufficient"
      - "Off - HVAC mode OFF"
      - "Error - sensor unavailable"
    - [ ] Użytkownik rozumie dlaczego zawór jest zamknięty
    - [ ] Atrybut: detailed_reason (więcej szczegółów)

---

### 4.7 Dokumentacja i testy

- [ ] **T4.7.1:** Testy jednostkowe zaawansowanych funkcji
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T4.5.4
  - **Kryteria akceptacji:**
    - [ ] Test SolarCalculator
    - [ ] Test thermal coupling między pokojami
    - [ ] Test ZoneCoordinator (fair-share)
    - [ ] Test PWMController
    - [ ] Coverage > 75%

- [ ] **T4.7.2:** Test integracyjny - koordynacja 3 pokoi
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T4.7.1
  - **Kryteria akceptacji:**
    - [ ] Symulacja: 3 pokoje, max_power = 10kW, każdy chce 5kW
    - [ ] Sprawdź że suma mocy ≤ 10kW
    - [ ] Sprawdź że priorytetyzacja działa (najpierw najzimniejszy pokój)
    - [ ] Sprawdź rotację (pokoje dostaną moc w kolejnych cyklach)

- [ ] **T4.7.3:** Test PWM na rzeczywistym zaworze (opcjonalnie)
  - **Priorytet:** Niski
  - **Czas:** 2h (+ obserwacja)
  - **Zależności:** T4.7.2
  - **Kryteria akceptacji:**
    - [ ] Podłącz do rzeczywistego switch-based valve
    - [ ] Ustaw duty=60%
    - [ ] Obserwuj przez kilka okresów (2-3h)
    - [ ] Sprawdź że średnia moc odpowiada 60%

- [ ] **T4.7.4:** Dokumentacja zaawansowanych funkcji
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T4.7.3
  - **Kryteria akceptacji:**
    - [ ] README sekcja "Advanced Features"
    - [ ] Wyjaśnienie:
      - Solar gains calculation
      - Thermal coupling between rooms
      - Fair-share power allocation
      - PWM for ON/OFF valves
    - [ ] Przykłady konfiguracji (orientacja okien, sąsiedzi)
    - [ ] Troubleshooting guide

---

## Kamienie milowe

- **M4.1:** Prognoza pogody i solar gains działają (koniec tygodnia 1)
- **M4.2:** Thermal coupling między pokojami zaimplementowany (koniec tygodnia 2)
- **M4.3:** Koordynacja stref (fair-share) działa (koniec tygodnia 3)
- **M4.4:** PWM dla zaworów ON/OFF działające (koniec tygodnia 4)

---

## Metryki sukcesu fazy

- [ ] MPC wykorzystuje prognozę pogody do pre-heating/cooling
- [ ] Solar gains redukują zużycie energii o ~5-10% w słoneczne dni
- [ ] Koordynacja stref przestrzega limitu mocy pieca
- [ ] Fair-share allocation działa sprawiedliwie (priorytetyzacja + rotacja)
- [ ] PWM dla switch-based valves działa płynnie (bez "clickowania")

---

## Notatki

- Solar gains mogą znacznie zredukować koszty w domu z dużymi oknami południowymi
- Thermal coupling jest ważny dla mieszkań/segmentów (współdzielone ściany)
- Fair-share musi być sprawiedliwy - użytkownik nie może mieć jednego pokoju zawsze zimnego
- PWM period (30-60 min) to kompromis: dłuższy = mniej przełączeń, krótszy = dokładniejsza kontrola
- Priorytetyzuj stabilność - lepiej konserwatywna koordynacja niż agresywna optymalizacja

---

**Poprzednia faza:** [Faza 3: MPC Core](./phase-3-mpc-core.md)
**Następna faza:** [Faza 5: Optymalizacja kosztów](./phase-5-cost-optimization.md)
