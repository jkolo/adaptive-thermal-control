# Faza 2: Model termiczny (Miesiąc 2)

**Status:** 🔴 Nie rozpoczęte

**Cel:** Uczenie się parametrów modelu termicznego z danych historycznych

**Czas trwania:** 4 tygodnie

**Zależności:** Faza 1 zakończona

---

## Cele fazy

- [ ] Implementacja modelu termicznego 1R1C
- [ ] Algorytm identyfikacji parametrów (Recursive Least Squares)
- [ ] Zbieranie i preprocessing danych historycznych (7-30 dni)
- [ ] Walidacja modelu (porównanie predykcji z rzeczywistością)
- [ ] Persystencja parametrów nauczonego modelu

---

## Zadania

### 2.1 Model termiczny 1R1C

- [ ] **T2.1.1:** Implementuj `thermal_model.py` - klasa ThermalModel
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** Brak
  - **Kryteria akceptacji:**
    - [ ] Równanie: `C·dT/dt = Q_grzanie - (T - T_zewn)/R + Q_zakłócenia`
    - [ ] Dyskretyzacja Eulera: `T(k+1) = A·T(k) + B·u(k) + Bd·d(k)`
    - [ ] Macierze: `A = exp(-dt/(R·C))`, `B = R·(1-A)`, `Bd = (1-A)`
    - [ ] Metoda `predict(x0, u_sequence, d_forecast) -> x_pred`
    - [ ] Metoda `simulate_step(T, u, T_zewn, dt) -> T_next`

- [ ] **T2.1.2:** Implementuj obsługę zakłóceń (disturbances)
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T2.1.1
  - **Kryteria akceptacji:**
    - [ ] Temperatura zewnętrzna jako zakłócenie główne
    - [ ] Opcjonalnie: wpływ sąsiednich pomieszczeń
    - [ ] Opcjonalnie: nasłonecznienie (Q_solar)
    - [ ] Wektor zakłóceń: `d = [T_zewn, T_neighbors, solar_gain]`

- [ ] **T2.1.3:** Testy modelu termicznego
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T2.1.2
  - **Kryteria akceptacji:**
    - [ ] Test: stała temp zewn, stałe grzanie → osiąga stan ustalony
    - [ ] Test: skok mocy grzania → eksponencjalna odpowiedź
    - [ ] Test: stała czasowa τ = R·C zgodna z teorią
    - [ ] Test: symulacja 24h bez błędów numerycznych

---

### 2.2 Identyfikacja parametrów (RLS)

- [ ] **T2.2.1:** Implementuj `parameter_estimator.py` - klasa ParameterEstimator
  - **Priorytet:** Wysoki
  - **Czas:** 5h
  - **Zależności:** T2.1.1
  - **Kryteria akceptacji:**
    - [ ] Algorytm Recursive Least Squares (RLS)
    - [ ] Estymacja R i C z danych historycznych
    - [ ] Metoda `update(T_measured, T_outdoor, P_heating, dt)`
    - [ ] Forgetting factor λ = 0.98 (daje więcej wagi świeżym danom)
    - [ ] Inicjalizacja z wartościami domyślnymi (R=0.002, C=4.5e6)

- [ ] **T2.2.2:** Implementuj preprocessing danych treningowych
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T2.2.1
  - **Kryteria akceptacji:**
    - [ ] Usuwanie outliers (temperatura poza [0, 50]°C)
    - [ ] Interpolacja brakujących danych (liniowa, max gap 30 min)
    - [ ] Resampling do stałego kroku czasowego (10 min)
    - [ ] Filtracja szumów (moving average window=3)
    - [ ] Normalizacja (opcjonalnie, dla stabilności numerycznej)

- [ ] **T2.2.3:** Implementuj batch training z danych historycznych
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T2.2.2
  - **Kryteria akceptacji:**
    - [ ] Funkcja `train_from_history(room_id, days=30)`
    - [ ] Pobiera dane z HA recorder (temperatura, grzanie, temp zewn)
    - [ ] Uruchamia RLS na całym zbiorze danych
    - [ ] Zwraca estymowane parametry (R, C, τ)
    - [ ] Oblicza metryki błędu (RMSE, MAE)

- [ ] **T2.2.4:** Online adaptation - dostrajanie modelu w trakcie działania
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T2.2.3
  - **Kryteria akceptacji:**
    - [ ] Co 24h: uruchom `train_from_history(days=7)`
    - [ ] Aktualizuj parametry modelu jeśli poprawiły się (niższy RMSE)
    - [ ] Zapisz stare parametry jako backup
    - [ ] Logowanie: "Model updated: R=..., C=..., RMSE=..."
    - [ ] Rollback jeśli nowe parametry gorsze o > 20%

---

### 2.3 Walidacja modelu

- [ ] **T2.3.1:** Implementuj `model_validator.py` - klasa ModelValidator
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T2.2.3
  - **Kryteria akceptacji:**
    - [ ] Metoda `validate(model, test_data) -> metrics`
    - [ ] Porównanie predykcji vs rzeczywistość
    - [ ] Metryki:
      - MAE (Mean Absolute Error)
      - RMSE (Root Mean Square Error)
      - R² score
      - Max error
    - [ ] Wizualizacja (opcjonalnie, do debugowania)

- [ ] **T2.3.2:** K-fold cross-validation
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T2.3.1
  - **Kryteria akceptacji:**
    - [ ] Podział danych na K foldów (np. K=5)
    - [ ] Trenowanie na K-1 foldach, test na 1
    - [ ] Średnia metryk z wszystkich foldów
    - [ ] Sprawdzenie stabilności parametrów (variance między foldami)

- [ ] **T2.3.3:** Wykrywanie drift modelu (model degradation)
  - **Priorytet:** Niski
  - **Czas:** 2h
  - **Zależności:** T2.3.2
  - **Kryteria akceptacji:**
    - [ ] Porównanie błędu predykcji z ostatnich 7 dni vs baseline
    - [ ] Jeśli błąd > 150% baseline → ostrzeżenie "Model drift detected"
    - [ ] Sugestia użytkownikowi: "Re-train model with recent data"
    - [ ] Automatyczne re-training (opcjonalnie, do decyzji)

---

### 2.4 Rozszerzenia modelu (opcjonalne)

- [ ] **T2.4.1:** Wpływ sąsiednich pomieszczeń
  - **Priorytet:** Średni
  - **Czas:** 4h
  - **Zależności:** T2.2.3
  - **Kryteria akceptacji:**
    - [ ] Rozszerzenie modelu: `Q_neighbors = Σ k_i · (T_i - T_pokoju)`
    - [ ] Estymacja współczynników k_i dla każdego sąsiada
    - [ ] Konfiguracja: lista sąsiadujących pokoi z Config Flow
    - [ ] Jeśli brak sąsiadów → k_i = 0 (model upraszcza się)

- [ ] **T2.4.2:** Nasłonecznienie przez okna
  - **Priorytet:** Średni
  - **Czas:** 4h
  - **Zależności:** T2.2.3
  - **Kryteria akceptacji:**
    - [ ] Rozszerzenie modelu: `Q_solar = η · irradiance · A_okna · orientacja`
    - [ ] Estymacja współczynnika absorpcji η
    - [ ] Orientacja okien z Config Flow (N, S, E, W, ...)
    - [ ] Jeśli brak encji solar → Q_solar = 0

- [ ] **T2.4.3:** Model 2R2C (zaawansowany, opcjonalny)
  - **Priorytet:** Niski
  - **Czas:** 8h
  - **Zależności:** T2.3.2
  - **Kryteria akceptacji:**
    - [ ] Dwa stany: temperatura powietrza + temperatura podłogi
    - [ ] Macierze 2×2 dla A, B
    - [ ] Estymacja 4 parametrów: R1, C1, R2, C2
    - [ ] Lepsza dokładność dla ogrzewania podłogowego
    - [ ] Przełącznik w Config: model 1R1C vs 2R2C

---

### 2.5 Persystencja danych

- [ ] **T2.5.1:** Zapis parametrów modelu do pliku JSON
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T2.2.3
  - **Kryteria akceptacji:**
    - [ ] Plik: `config/.storage/adaptive_thermal_control_models.json`
    - [ ] Struktura:
      ```json
      {
        "climate.salon": {
          "R": 0.0025,
          "C": 4.5e6,
          "tau": 11250,
          "neighbors_influence": {"climate.kuchnia": 0.15},
          "solar_coefficient": 0.65,
          "last_update": "2025-10-26T10:00:00Z",
          "metrics": {"rmse": 0.42, "mae": 0.31}
        }
      }
      ```
    - [ ] Atomic write (tmp file + rename)
    - [ ] Backup poprzedniej wersji pliku

- [ ] **T2.5.2:** Ładowanie parametrów przy starcie integracji
  - **Priorytet:** Wysoki
  - **Czas:** 1h
  - **Zależności:** T2.5.1
  - **Kryteria akceptacji:**
    - [ ] Przy `async_setup_entry()` → wczytaj parametry z pliku
    - [ ] Jeśli plik nie istnieje → użyj wartości domyślnych
    - [ ] Jeśli błąd odczytu → log ERROR, użyj defaults
    - [ ] Inicjalizuj ThermalModel z wczytanych parametrów

- [ ] **T2.5.3:** Historyczne wersje parametrów (opcjonalnie)
  - **Priorytet:** Niski
  - **Czas:** 2h
  - **Zależności:** T2.5.1
  - **Kryteria akceptacji:**
    - [ ] Archiwizacja starych parametrów (np. ostatnie 10 wersji)
    - [ ] Możliwość rollback do poprzedniej wersji
    - [ ] Service call: `adaptive_thermal_control.rollback_model`

---

### 2.6 Sensor diagnostyczny

- [ ] **T2.6.1:** Stwórz `sensor.py` - sensory diagnostyczne
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T2.3.1
  - **Kryteria akceptacji:**
    - [ ] Sensor: `sensor.adaptive_thermal_[pokój]_model_r` (opór termiczny)
    - [ ] Sensor: `sensor.adaptive_thermal_[pokój]_model_c` (pojemność)
    - [ ] Sensor: `sensor.adaptive_thermal_[pokój]_model_tau` (stała czasowa)
    - [ ] Sensor: `sensor.adaptive_thermal_[pokój]_prediction_error` (RMSE)
    - [ ] Unit of measurement: R [K/W], C [MJ/K], τ [h], error [°C]

- [ ] **T2.6.2:** Sensor statusu modelu
  - **Priorytet:** Średni
  - **Czas:** 1h
  - **Zależności:** T2.6.1
  - **Kryteria akceptacji:**
    - [ ] Sensor: `sensor.adaptive_thermal_[pokój]_model_status`
    - [ ] Stany:
      - "not_trained" - brak danych, używa defaults
      - "learning" - < 30 dni danych
      - "trained" - > 30 dni, dobry model
      - "degraded" - wykryto drift
    - [ ] Atrybuty: training_data_days, last_training, rmse

---

### 2.7 Dokumentacja i testy

- [ ] **T2.7.1:** Testy jednostkowe modelu termicznego
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T2.1.3
  - **Kryteria akceptacji:**
    - [ ] Test ThermalModel.predict()
    - [ ] Test ParameterEstimator.update()
    - [ ] Test ModelValidator.validate()
    - [ ] Coverage > 80% dla nowych modułów

- [ ] **T2.7.2:** Test integracyjny - uczenie z danych rzeczywistych
  - **Priorytet:** Wysoki
  - **Czas:** 2h
  - **Zależności:** T2.5.2
  - **Kryteria akceptacji:**
    - [ ] Mock danych historycznych (30 dni)
    - [ ] Uruchom training
    - [ ] Sprawdź czy parametry są sensowne (R ∈ [0.001, 0.01], C ∈ [1e6, 1e7])
    - [ ] Sprawdź czy RMSE < 1.0°C

- [ ] **T2.7.3:** Dokumentacja modelu termicznego
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T2.7.2
  - **Kryteria akceptacji:**
    - [ ] README sekcja "How it works - Thermal Model"
    - [ ] Równania matematyczne z wyjaśnieniem
    - [ ] Diagram blokowy modelu 1R1C
    - [ ] Przykładowe wartości parametrów dla różnych typów budynków

---

## Kamienie milowe

- **M2.1:** Model 1R1C zaimplementowany i przetestowany (koniec tygodnia 1)
- **M2.2:** RLS działa, parametry są estymo wane z danych (koniec tygodnia 2)
- **M2.3:** Walidacja modelu pokazuje RMSE < 1°C (koniec tygodnia 3)
- **M2.4:** Persystencja działa, model jest ładowany przy starcie (koniec tygodnia 4)

---

## Metryki sukcesu fazy

- [ ] Model termiczny przewiduje temperaturę z błędem RMSE < 1.0°C
- [ ] Parametry R i C są w sensownych zakresach
- [ ] Walidacja cross-validation pokazuje stabilność parametrów
- [ ] Model jest zapisywany i ładowany poprawnie
- [ ] Sensory diagnostyczne pokazują status modelu

---

## Notatki

- Model 1R1C to kompromis: prostota vs dokładność (wystarczy dla większości przypadków)
- Model 2R2C można dodać później jeśli 1R1C nie wystarcza
- RLS jest online algorithm - można go używać do adaptacji w czasie rzeczywistym
- Ważne: walidacja MUSI pokazać że model jest lepszy niż prosty PI (inaczej po co MPC?)

---

**Poprzednia faza:** [Faza 1: Fundament](./phase-1-foundation.md)
**Następna faza:** [Faza 3: MPC Core](./phase-3-mpc-core.md)
