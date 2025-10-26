# Faza 3: MPC Core (Miesiąc 3-4)

**Status:** 🔴 Nie rozpoczęte

**Cel:** Działający algorytm Model Predictive Control

**Czas trwania:** 6-8 tygodni

**Zależności:** Faza 1 i 2 zakończone

---

## Cele fazy

- [ ] Implementacja algorytmu MPC z scipy.optimize
- [ ] Funkcja kosztu (komfort + energia + gładkość)
- [ ] Horyzont predykcji 4-8 godzin (Np=24-48)
- [ ] Optymalizacja wydajności (< 2s na cykl)
- [ ] Testy na danych rzeczywistych

---

## Zadania

### 3.1 Fundament MPC

- [ ] **T3.1.1:** Implementuj `mpc_controller.py` - klasa MPCController
  - **Priorytet:** Wysoki
  - **Czas:** 6h
  - **Zależności:** Faza 2 zakończona
  - **Kryteria akceptacji:**
    - [ ] Klasa `MPCController(model: ThermalModel, config: MPCConfig)`
    - [ ] Parametry:
      - `Np` (prediction horizon) = 24 (4h przy dt=10min)
      - `Nc` (control horizon) = 12 (2h)
      - `dt` (timestep) = 600s (10min)
    - [ ] Metoda `compute_control(x0, setpoint, forecast) -> u_optimal`
    - [ ] Wykorzystuje ThermalModel do predykcji

- [ ] **T3.1.2:** Implementuj funkcję kosztu
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T3.1.1
  - **Kryteria akceptacji:**
    - [ ] Funkcja `cost_function(u_sequence) -> cost`
    - [ ] Składniki:
      ```
      J = Σ[k=0..Np] {
          w_comfort · (T(k) - T_setpoint)²     # Komfort
        + w_energy · P(k)²                     # Energia
        + w_smooth · (P(k) - P(k-1))²          # Gładkość
      }
      ```
    - [ ] Wagi domyślne: w_comfort=0.7, w_energy=0.2, w_smooth=0.1
    - [ ] Normalizacja składników (energy i smooth przez 1e6)
    - [ ] Opcjonalnie: terminal cost (koszt końcowy)

- [ ] **T3.1.3:** Implementuj ograniczenia (constraints)
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T3.1.2
  - **Kryteria akceptacji:**
    - [ ] Box constraints na sterowanie: `0 ≤ u(k) ≤ u_max`
    - [ ] Rate constraints: `|u(k) - u(k-1)| ≤ du_max`
    - [ ] Opcjonalnie: soft constraints na temperaturę
    - [ ] Format dla scipy.optimize.minimize:
      - bounds = [(u_min, u_max)] * Nc
      - constraints = [{'type': 'ineq', 'fun': ...}]

- [ ] **T3.1.4:** Integracja z scipy.optimize.minimize
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T3.1.3
  - **Kryteria akceptacji:**
    - [ ] Metoda optymalizacji: 'SLSQP' (Sequential Least Squares Programming)
    - [ ] Początkowe przypuszczenie: u_init = [u_previous] * Nc
    - [ ] Options: maxiter=100, ftol=1e-6
    - [ ] Error handling jeśli optymalizacja nie zbiegła
    - [ ] Fallback na PI jeśli MPC fails
    - [ ] Zwraca tylko pierwszy element sekwencji (receding horizon)

---

### 3.2 Prognoza zakłóceń

- [ ] **T3.2.1:** Implementuj `forecast_provider.py` - klasa ForecastProvider
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T3.1.1
  - **Kryteria akceptacji:**
    - [ ] Metoda `get_outdoor_temperature_forecast(hours=4) -> np.array`
    - [ ] Pobiera prognozę z weather entity (atrybut `forecast`)
    - [ ] Interpolacja do 10-minutowych kroków
    - [ ] Jeśli brak prognozy → użyj aktualnej temp jako stałej
    - [ ] Extrapolacja jeśli prognoza krótsza niż Np

- [ ] **T3.2.2:** Prognoza dla innych zakłóceń (opcjonalnie)
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.2.1
  - **Kryteria akceptacji:**
    - [ ] Prognoza nasłonecznienia (jeśli encja solar forecast dostępna)
    - [ ] Prognoza temperatur sąsiednich pokoi (prosta ekstrapolacja)
    - [ ] Agregacja w wektor d_forecast: [T_outdoor, T_neighbors, solar]

---

### 3.3 Integracja z Climate Entity

- [ ] **T3.3.1:** Przełączenie z PI na MPC w coordinator
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T3.1.4
  - **Kryteria akceptacji:**
    - [ ] W coordinator: sprawdź czy model wytrenowany (status="trained")
    - [ ] Jeśli tak → użyj MPCController
    - [ ] Jeśli nie → użyj PIController (fallback)
    - [ ] Atrybut climate entity: `controller_type: "MPC"` lub `"PI"`
    - [ ] Logowanie: "Switched to MPC for climate.salon"

- [ ] **T3.3.2:** Zapisywanie planu sterowania (opcjonalnie)
  - **Priorytet:** Niski
  - **Czas:** 2h
  - **Zależności:** T3.3.1
  - **Kryteria akceptacji:**
    - [ ] Zapisuj całą sekwencję u_optimal (nie tylko pierwszy krok)
    - [ ] Atrybut climate entity: `control_plan: [u(0), u(1), ..., u(Nc-1)]`
    - [ ] Umożliwia użytkownikowi zobaczenie "co MPC planuje zrobić"
    - [ ] Sensor diagnostyczny: `sensor.adaptive_thermal_[pokój]_control_plan`

---

### 3.4 Optymalizacja wydajności

- [ ] **T3.4.1:** Warm-start dla solvera
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.1.4
  - **Kryteria akceptacji:**
    - [ ] Zapamiętaj poprzednie rozwiązanie u_prev_sequence
    - [ ] Użyj jako initial guess: u_init = shift(u_prev_sequence)
    - [ ] Zwykle przyspiesza zbieżność 2-3x
    - [ ] Jeśli brak prev solution → u_init = [u_last] * Nc

- [ ] **T3.4.2:** Cache macierzy modelu
  - **Priorytet:** Średni
  - **Czas:** 1h
  - **Zależności:** T3.1.1
  - **Kryteria akceptacji:**
    - [ ] Macierze A, B, Bd nie zmieniają się często → cache
    - [ ] Przebuduj tylko gdy parametry modelu się zmienią
    - [ ] Oznacz flagą: `model._cache_valid`
    - [ ] Przyspiesza o ~10-20%

- [ ] **T3.4.3:** Profiling i benchmarking
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.4.2
  - **Kryteria akceptacji:**
    - [ ] Zmierz czas obliczeń MPC na cykl
    - [ ] Cel: < 2s dla 1 pokoju, < 5s dla 20 pokoi
    - [ ] Profiling: zidentyfikuj bottlenecks (cProfile)
    - [ ] Logowanie czasu: "MPC optimization took 1.23s"

- [ ] **T3.4.4:** Optymalizacja kodu (jeśli potrzeba)
  - **Priorytet:** Niski
  - **Czas:** 4h
  - **Zależności:** T3.4.3
  - **Kryteria akceptacji:**
    - [ ] Jeśli czas > 2s → rozważ:
      - Numba JIT compilation (@njit)
      - Mniejszy horyzont Np (z 48 na 24)
      - Zmiana solvera (np. cvxpy z OSQP dla QP)
    - [ ] Re-benchmark po zmianach

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

- [ ] **T3.6.1:** Mechanizm fallback PI ↔ MPC
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T3.3.1
  - **Kryteria akceptacji:**
    - [ ] Jeśli MPC nie zbiegnie (3 próby) → przełącz na PI
    - [ ] Jeśli model degraded (drift detected) → przełącz na PI
    - [ ] Jeśli czas obliczeń > 10s → przełącz na PI (timeout)
    - [ ] Powiadomienie użytkownika (persistent notification w HA)
    - [ ] Automatyczny powrót do MPC gdy problem rozwiązany

- [ ] **T3.6.2:** Monitoring jakości sterowania
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T3.6.1
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

- [ ] **T3.8.1:** Testy jednostkowe MPC
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T3.1.4
  - **Kryteria akceptacji:**
    - [ ] Test MPCController.compute_control()
    - [ ] Test funkcji kosztu (różne wagi → różne wyniki)
    - [ ] Test ograniczeń (sprawdź czy u ∈ [u_min, u_max])
    - [ ] Test receding horizon (powtórzenie obliczeń daje spójne wyniki)

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
