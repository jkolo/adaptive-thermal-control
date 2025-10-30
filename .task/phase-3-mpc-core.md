# Faza 3: MPC Core (Miesiąc 3-4)

**Status:** 🟡 W trakcie (26% - 10/38 zadań ukończonych)

**Cel:** Działający algorytm Model Predictive Control

**Czas trwania:** 6-8 tygodni

**Zależności:** Faza 1 i 2 zakończone ✅

---

## Cele fazy

- [x] Implementacja algorytmu MPC z scipy.optimize ✅
- [x] Funkcja kosztu (komfort + energia + gładkość) ✅
- [x] Horyzont predykcji 4-8 godzin (Np=24) ✅
- [x] Optymalizacja wydajności (< 2s na cykl) ✅ **Osiągnięto: 4ms (500x szybciej!)**
- [ ] Testy na danych rzeczywistych

---

## Zadania

### 3.1 Fundament MPC

- [x] **T3.1.1:** Implementuj `mpc_controller.py` - klasa MPCController ✅
  - **Priorytet:** Wysoki
  - **Czas:** 6h
  - **Zależności:** Faza 2 zakończona
  - **Kryteria akceptacji:**
    - [x] Klasa `MPCController(model: ThermalModel, config: MPCConfig)`
    - [x] Parametry:
      - `Np` (prediction horizon) = 24 (4h przy dt=10min)
      - `Nc` (control horizon) = 12 (2h)
      - `dt` (timestep) = 600s (10min)
    - [x] Metoda `compute_control(x0, setpoint, forecast) -> u_optimal`
    - [x] Wykorzystuje ThermalModel do predykcji

- [x] **T3.1.2:** Implementuj funkcję kosztu ✅
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T3.1.1
  - **Kryteria akceptacji:**
    - [x] Funkcja `cost_function(u_sequence) -> cost`
    - [x] Składniki:
      ```
      J = Σ[k=0..Np] {
          w_comfort · (T(k) - T_setpoint)²     # Komfort
        + w_energy · P(k)²                     # Energia
        + w_smooth · (P(k) - P(k-1))²          # Gładkość
      }
      ```
    - [x] Wagi domyślne: w_comfort=0.7, w_energy=0.2, w_smooth=0.1
    - [x] Normalizacja składników (energy i smooth przez 1e6)
    - [x] Opcjonalnie: terminal cost (koszt końcowy)

- [x] **T3.1.3:** Implementuj ograniczenia (constraints) ✅
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T3.1.2
  - **Kryteria akceptacji:**
    - [x] Box constraints na sterowanie: `0 ≤ u(k) ≤ u_max`
    - [x] Rate constraints: `|u(k) - u(k-1)| ≤ du_max`
    - [ ] Opcjonalnie: soft constraints na temperaturę (nie zaimplementowane)
    - [x] Format dla scipy.optimize.minimize:
      - bounds = [(u_min, u_max)] * Nc
      - constraints = [{'type': 'ineq', 'fun': ...}]

- [x] **T3.1.4:** Integracja z scipy.optimize.minimize ✅
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T3.1.3
  - **Kryteria akceptacji:**
    - [x] Metoda optymalizacji: 'SLSQP' (Sequential Least Squares Programming)
    - [x] Początkowe przypuszczenie: u_init = [u_previous] * Nc
    - [x] Options: maxiter=100, ftol=1e-6
    - [x] Error handling jeśli optymalizacja nie zbiegła
    - [x] Fallback na PI jeśli MPC fails
    - [x] Zwraca tylko pierwszy element sekwencji (receding horizon)

---

### 3.2 Prognoza zakłóceń

- [x] **T3.2.1:** Implementuj `forecast_provider.py` - klasa ForecastProvider ✅
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T3.1.1
  - **Kryteria akceptacji:**
    - [x] Metoda `get_outdoor_temperature_forecast(hours=4) -> np.array`
    - [x] Pobiera prognozę z weather entity (atrybut `forecast`)
    - [x] Interpolacja do 10-minutowych kroków
    - [x] Jeśli brak prognozy → użyj aktualnej temp jako stałej
    - [x] Extrapolacja jeśli prognoza krótsza niż Np

- [ ] **T3.2.2:** Prognoza dla innych zakłóceń (opcjonalnie) - **DO ZROBIENIA W FAZIE 4**
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.2.1
  - **Kryteria akceptacji:**
    - [ ] Prognoza nasłonecznienia (jeśli encja solar forecast dostępna)
    - [ ] Prognoza temperatur sąsiednich pokoi (prosta ekstrapolacja)
    - [ ] Agregacja w wektor d_forecast: [T_outdoor, T_neighbors, solar]

---

### 3.3 Integracja z Climate Entity

- [x] **T3.3.1:** Przełączenie z PI na MPC w coordinator ✅
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T3.1.4
  - **Kryteria akceptacji:**
    - [x] W coordinator: sprawdź czy model wytrenowany (status="trained")
    - [x] Jeśli tak → użyj MPCController
    - [x] Jeśli nie → użyj PIController (fallback)
    - [x] Atrybut climate entity: `controller_type: "MPC"` lub `"PI"`
    - [x] Logowanie: "Switched to MPC for climate.salon"

- [ ] **T3.3.2:** Zapisywanie planu sterowania (opcjonalnie) - **CZĘŚCIOWO**
  - **Priorytet:** Niski
  - **Czas:** 2h
  - **Zależności:** T3.3.1
  - **Status:** MPCResult zawiera u_sequence i predicted_temps, ale climate entity nie eksportuje ich jako atrybutów
  - **Kryteria akceptacji:**
    - [x] Zapisuj całą sekwencję u_optimal (nie tylko pierwszy krok) - w MPCResult
    - [ ] Atrybut climate entity: `control_plan: [u(0), u(1), ..., u(Nc-1)]` - NIE ZAIMPLEMENTOWANE
    - [ ] Umożliwia użytkownikowi zobaczenie "co MPC planuje zrobić"
    - [ ] Sensor diagnostyczny: `sensor.adaptive_thermal_[pokój]_control_plan` - DO ZROBIENIA W T3.7

---

### 3.4 Optymalizacja wydajności

- [x] **T3.4.1:** Warm-start dla solvera ✅
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.1.4
  - **Kryteria akceptacji:**
    - [x] Zapamiętaj poprzednie rozwiązanie u_prev_sequence
    - [x] Użyj jako initial guess: u_init = shift(u_prev_sequence)
    - [x] Zwykle przyspiesza zbieżność 2-3x
    - [x] Jeśli brak prev solution → u_init = [u_last] * Nc

- [x] **T3.4.2:** Cache macierzy modelu ✅
  - **Priorytet:** Średni
  - **Czas:** 1h
  - **Zależności:** T3.1.1
  - **Kryteria akceptacji:**
    - [x] Macierze A, B, Bd nie zmieniają się często → cache
    - [x] Przebuduj tylko gdy parametry modelu się zmienią
    - [x] Oznacz flagą: `model._cache_valid`
    - [x] Przyspiesza o ~10-20%

- [x] **T3.4.3:** Profiling i benchmarking ✅
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.4.2
  - **Wynik:** **4ms per cycle (500x szybciej niż cel!), 2.8s dla 20 pokoi**
  - **Kryteria akceptacji:**
    - [x] Zmierz czas obliczeń MPC na cykl
    - [x] Cel: < 2s dla 1 pokoju, < 5s dla 20 pokoi ✅ **PRZEKROCZONO CEL**
    - [x] Profiling: zidentyfikuj bottlenecks (cProfile)
    - [x] Logowanie czasu: "MPC optimization took 1.23s"
  - **Implementacja:** `benchmark_mpc.py`

- [x] **T3.4.4:** Optymalizacja kodu (jeśli potrzeba) ✅ **NIE POTRZEBNE**
  - **Priorytet:** Niski
  - **Czas:** 4h
  - **Zależności:** T3.4.3
  - **Status:** Osiągnięto doskonałe wyniki (4ms), dodatkowa optymalizacja niepotrzebna
  - **Kryteria akceptacji:**
    - [x] Jeśli czas > 2s → rozważ:
      - Numba JIT compilation (@njit)
      - Mniejszy horyzont Np (z 48 na 24)
      - Zmiana solvera (np. cvxpy z OSQP dla QP)
    - [x] Re-benchmark po zmianach

---

### 3.5 Tuning parametrów MPC

- [ ] **T3.5.1:** Implementuj `mpc_tuner.py` - narzędzie do tuningu
  - **Priorytet:** Średni
  - **Czas:** 4h
  - **Zależności:** T3.1.4
  - **Kryteria akceptacji:**
    - [ ] Funkcja `grid_search(param_grid, test_data) -> best_params`
    - [ ] Grid search po wagach w_comfort, w_energy, w_smooth
    - [ ] Symulacja z różnymi parametrami
    - [ ] Metryki wydajności:
      - RMSE (błąd temperatury)
      - Total energy consumption
      - Control smoothness (suma Δu²)
    - [ ] Wybór Pareto-optymalny (trade-off comfort vs energy)

- [ ] **T3.5.2:** Automatyczne dostrajanie (opcjonalnie)
  - **Priorytet:** Niski
  - **Czas:** 3h
  - **Zależności:** T3.5.1
  - **Kryteria akceptacji:**
    - [ ] Co miesiąc: uruchom tuning na danych z ostatnich 30 dni
    - [ ] Jeśli nowe parametry lepsze → zaktualizuj
    - [ ] Service call: `adaptive_thermal_control.tune_mpc_parameters`
    - [ ] Zapisz parametry do storage

---

### 3.6 Failsafe i error handling

- [x] **T3.6.1:** Mechanizm fallback PI ↔ MPC ✅
  - **Priorytet:** Wysoki
  - **Czas:** 2h → 3h (rzeczywisty)
  - **Zależności:** T3.3.1 ✅
  - **Status:** 9/9 testów przechodzi
  - **Kryteria akceptacji:**
    - [x] Jeśli MPC nie zbiegnie (3 próby) → przełącz na PI
    - [x] Jeśli model degraded (drift detected) → przełącz na PI
    - [x] Jeśli czas obliczeń > 10s → przełącz na PI (timeout protection z asyncio.wait_for)
    - [x] Powiadomienie użytkownika (persistent notification w HA)
    - [x] Automatyczny powrót do MPC gdy problem rozwiązany (5 consecutive successes)
    - [x] Retry interval (1 hour) po permanent disable
  - **Implementacja:**
    - Failsafe state tracking: `_mpc_status`, `_mpc_failure_count`, `_mpc_success_count`
    - MPC status: "active", "degraded", "disabled"
    - Timeout protection: `asyncio.wait_for()` z 10s limitem
    - Persistent notifications dla użytkownika
    - Exposed as entity attributes
  - **Pliki:**
    - `custom_components/adaptive_thermal_control/const.py` - stałe failsafe
    - `custom_components/adaptive_thermal_control/climate.py` - logika failsafe
    - `tests/test_failsafe.py` - 9 testów (100% pass)

- [ ] **T3.6.2:** Monitoring jakości sterowania
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.6.1 ✅
  - **Kryteria akceptacji:**
    - [ ] Obliczaj rolling RMSE z ostatnich 24h
    - [ ] Jeśli RMSE > 2.0°C → ostrzeżenie
    - [ ] Sensor: `sensor.adaptive_thermal_[pokój]_control_quality`
    - [ ] Stany: "excellent" (<0.5°C), "good" (<1°C), "poor" (>1°C)

---

### 3.7 Sensory diagnostyczne MPC

- [ ] **T3.7.1:** Sensory parametrów MPC
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.3.1
  - **Kryteria akceptacji:**
    - [ ] `sensor.adaptive_thermal_[pokój]_mpc_horizon_prediction` - Np
    - [ ] `sensor.adaptive_thermal_[pokój]_mpc_horizon_control` - Nc
    - [ ] `sensor.adaptive_thermal_[pokój]_mpc_weights` - [w_comfort, w_energy, w_smooth]
    - [ ] `sensor.adaptive_thermal_[pokój]_mpc_optimization_time` - czas obliczeń [s]

- [ ] **T3.7.2:** Sensor predykcji temperatury
  - **Priorytet:** Niski
  - **Czas:** 2h
  - **Zależności:** T3.3.2
  - **Kryteria akceptacji:**
    - [ ] `sensor.adaptive_thermal_[pokój]_temperature_prediction`
    - [ ] Atrybut: forecast = [T(+10min), T(+20min), ..., T(+4h)]
    - [ ] Użytkownik może zobaczyć przewidywaną trajektorię temperatury
    - [ ] Użyteczne do debugowania

---

### 3.8 Dokumentacja i testy

- [x] **T3.8.1:** Testy jednostkowe MPC ✅
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T3.1.4
  - **Status:** 19 testów w test_mpc_controller.py (wszystkie przechodzą)
  - **Kryteria akceptacji:**
    - [x] Test MPCController.compute_control()
    - [x] Test funkcji kosztu (różne wagi → różne wyniki)
    - [x] Test ograniczeń (sprawdź czy u ∈ [u_min, u_max])
    - [x] Test receding horizon (powtórzenie obliczeń daje spójne wyniki)

- [ ] **T3.8.2:** Test integracyjny - symulacja 24h
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T3.8.1
  - **Kryteria akceptacji:**
    - [ ] Mock systemu termicznego (ThermalModel jako "plant")
    - [ ] MPC steruje systemem przez 24h symulacji
    - [ ] Sprawdź:
      - Temperatura osiąga setpoint ±0.5°C
      - Brak oscylacji
      - Sterowanie jest gładkie (bez skoków)
    - [ ] Porównaj z PI controller (MPC powinien być lepszy)

- [ ] **T3.8.3:** Test na danych rzeczywistych
  - **Priorytet:** Wysoki
  - **Czas:** 4h (+ czas obserwacji)
  - **Zależności:** T3.8.2
  - **Kryteria akceptacji:**
    - [ ] Wdróż MPC w rzeczywistym systemie (1 pokój testowy)
    - [ ] Monitoruj przez 7 dni
    - [ ] Zbieraj metryki:
      - RMSE (błąd temperatury)
      - Zużycie energii
      - Liczba przełączeń zaworu
    - [ ] Porównaj z poprzednim sterowaniem (PI lub ON/OFF)

- [ ] **T3.8.4:** Dokumentacja MPC
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T3.8.3
  - **Kryteria akceptacji:**
    - [ ] README sekcja "MPC Algorithm"
    - [ ] Wyjaśnienie funkcji kosztu (po co każda waga)
    - [ ] Diagram działania MPC (receding horizon)
    - [ ] Instrukcja tuningu parametrów
    - [ ] FAQ: "Dlaczego MPC lepsze niż PI?"

---

## Kamienie milowe

- **M3.1:** Podstawowy MPC działa (bez optymalizacji) (koniec tygodnia 2)
- **M3.2:** Integracja z climate entity, MPC steruje zaworem (koniec tygodnia 4)
- **M3.3:** Optymalizacja wydajności, czas < 2s (koniec tygodnia 6)
- **M3.4:** Test na danych rzeczywistych pokazuje lepsze wyniki niż PI (koniec tygodnia 8)

---

## Metryki sukcesu fazy

- [ ] MPC utrzymuje temperaturę ±0.5°C od nastawy
- [ ] Czas obliczeń < 2s dla 1 pokoju, < 5s dla 20 pokoi
- [ ] Optymalizacja zbiegnie w > 95% przypadków
- [ ] Zużycie energii niższe o 10-20% vs. PI controller
- [ ] Brak oscylacji temperatury

---

## Notatki

- MPC to serce projektu - poświęć czas na dopracowanie
- Rozpocznij od prostego (QP problem), potem dodawaj złożoność
- Tuning wag (w_comfort, w_energy, w_smooth) jest krytyczny dla sukcesu
- Test na rzeczywistych danych to MUST - symulacja nie wystarczy
- Failsafe mechanizm (fallback PI) to konieczność - MPC może zawieść

---

**Poprzednia faza:** [Faza 2: Model termiczny](./phase-2-thermal-model.md)
**Następna faza:** [Faza 4: Zaawansowane funkcje](./phase-4-advanced-features.md)
