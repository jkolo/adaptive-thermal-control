# Faza 5: Optymalizacja kosztów (Miesiąc 6)

**Status:** 🔴 Nie rozpoczęte

**Cel:** Inteligentna optymalizacja finansowa - "grzej teraz bo później drożej"

**Czas trwania:** 4 tygodnie

**Zależności:** Faza 4 zakończona

---

## Cele fazy

- [ ] Integracja encji cen energii (taryfowej i spot)
- [ ] Strategia "load shifting" - przesunięcie grzania na tańsze godziny
- [ ] Dashboard z kosztami i oszczędnościami
- [ ] Fine-tuning wag w funkcji kosztu (balance komfort vs oszczędność)
- [ ] Wykorzystanie masy termicznej jako "magazynu energii"

---

## Zadania

### 5.1 Integracja cen energii

- [ ] **T5.1.1:** Implementuj `price_provider.py` - dostawca cen energii
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** Faza 4 zakończona
  - **Kryteria akceptacji:**
    - [ ] Klasa `PriceProvider(entity_id: str)`
    - [ ] Metoda `get_current_price() -> float` [PLN/kWh lub EUR/kWh]
    - [ ] Metoda `get_price_forecast(hours=24) -> np.array`
    - [ ] Obsługa różnych formatów encji:
      - Sensor ze stanem = aktualna cena
      - Sensor z atrybutem `forecast` = prognoza cen
      - Taryfowy (stała taryfa dzienna/nocna)
      - Spot price (dynamiczny, np. EPEX, Nordpool)

- [ ] **T5.1.2:** Parser taryfy dwustrefowej
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T5.1.1
  - **Kryteria akceptacji:**
    - [ ] Rozpoznaj taryfę G12 (Polska) lub podobne
    - [ ] Godziny tańsze (np. 22:00-06:00, 13:00-15:00)
    - [ ] Godziny droższe (reszta)
    - [ ] Ratio: tańsza/droższa ≈ 0.6-0.7
    - [ ] Jeśli brak prognozy → generuj na podstawie godzin

- [ ] **T5.1.3:** Integracja z MPC - rozszerzenie funkcji kosztu
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T5.1.2
  - **Kryteria akceptacji:**
    - [ ] Nowa składowa funkcji kosztu:
      ```
      J = Σ[k=0..Np] {
          w_comfort · (T(k) - T_setpoint)²
        + w_energy · P(k)²
        + w_smooth · (P(k) - P(k-1))²
        + w_cost · price(k) · P(k)    ← NOWE
      }
      ```
    - [ ] Waga `w_cost` domyślnie = 0.0 (wyłączona, opt-in)
    - [ ] Jeśli encja cen podana → włącz automatycznie (w_cost=0.2)
    - [ ] MPC widzi prognozę cen na horyzoncie Np

---

### 5.2 Strategia "load shifting"

- [ ] **T5.2.1:** Pre-heating przed drogą taryfą
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T5.1.3
  - **Kryteria akceptacji:**
    - [ ] MPC widzi że za 2h cena wzrośnie 2x
    - [ ] Pre-ogrzewa pokój TERAZ (tania taryfa) do T_setpoint + δ
    - [ ] δ (overshoot) ograniczone do +1-2°C (komfort)
    - [ ] W drogiej taryfie: minimalne grzanie (tylko utrzymanie)
    - [ ] Wykorzystuje bezwładność termiczną jako "baterię"

- [ ] **T5.2.2:** Konfigurowalne ograniczenia overheating
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T5.2.1
  - **Kryteria akceptacji:**
    - [ ] Parametr w Config: `max_overshoot` [°C] (default: 1.5°C)
    - [ ] Ograniczenie w MPC: `T(k) ≤ T_setpoint + max_overshoot`
    - [ ] Użytkownik może wyłączyć (max_overshoot=0) jeśli nie lubi
    - [ ] Preset "eco": max_overshoot=2.0, w_cost=0.3 (agresywna optymalizacja)
    - [ ] Preset "comfort": max_overshoot=0.5, w_cost=0.1 (priorytet komfort)

- [ ] **T5.2.3:** Nocne "ładowanie" masy termicznej
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T5.2.2
  - **Kryteria akceptacji:**
    - [ ] W nocy (tania taryfa 22:00-06:00): podgrzej do T_setpoint + 1°C
    - [ ] Rano (droga taryfa 06:00-22:00): utrzymuj bez grzania (lub minimalnie)
    - [ ] Szczególnie skuteczne dla ogrzewania podłogowego (duża bezwładność)
    - [ ] Logowanie: "Night pre-heating: stored 8kWh thermal energy"

---

### 5.3 Monitoring kosztów

- [ ] **T5.3.1:** Implementuj `cost_tracker.py` - tracker kosztów
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T5.1.1
  - **Kryteria akceptacji:**
    - [ ] Klasa `CostTracker`
    - [ ] Metoda `record_heating(power_kW, duration_s, price_per_kWh)`
    - [ ] Obliczanie:
      - Energia zużyta [kWh] = power × (duration / 3600)
      - Koszt [PLN] = energia × cena
    - [ ] Agregacja:
      - Dziennie
      - Tygodniowo
      - Miesięcznie
    - [ ] Zapis do persystentnego storage

- [ ] **T5.3.2:** Sensory kosztów
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T5.3.1
  - **Kryteria akceptacji:**
    - [ ] `sensor.adaptive_thermal_[pokój]_heating_cost_today` [PLN]
    - [ ] `sensor.adaptive_thermal_[pokój]_heating_cost_month` [PLN]
    - [ ] `sensor.adaptive_thermal_[pokój]_energy_consumed_today` [kWh]
    - [ ] `sensor.adaptive_thermal_global_total_cost_today` [PLN]
    - [ ] `sensor.adaptive_thermal_global_total_cost_month` [PLN]
    - [ ] Reset dziennie o północy (automatyczny)

- [ ] **T5.3.3:** Porównanie z baseline (oszczędności)
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T5.3.2
  - **Kryteria akceptacji:**
    - [ ] Oblicz baseline: "ile by kosztowało bez MPC?"
      - Założenie: prosty termostat ON/OFF z +30% zużyciem
      - Lub: zapisz zużycie z pierwszego miesiąca jako baseline
    - [ ] Sensor: `sensor.adaptive_thermal_global_savings_month` [PLN]
    - [ ] Sensor: `sensor.adaptive_thermal_global_savings_percent` [%]
    - [ ] Atrybut: breakdown (ile z komfortu, ile z load shifting)

---

### 5.4 Dashboard kosztów

- [ ] **T5.4.1:** Karta Lovelace - podsumowanie kosztów
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T5.3.3
  - **Kryteria akceptacji:**
    - [ ] Karta pokazuje:
      - Koszt dzisiaj / ten miesiąc
      - Energia zużyta dzisiaj / ten miesiąc
      - Oszczędności (vs baseline)
      - Wykres: koszt per dzień (ostatnie 30 dni)
    - [ ] Przykładowy plik YAML: `examples/lovelace_cost_card.yaml`
    - [ ] Użycie standardowych kart HA (entities, gauge, apex-charts)

- [ ] **T5.4.2:** Wykres cen energii z planem grzania
  - **Priorytet:** Średni
  - **Czas:** 2h
  - **Zależności:** T5.4.1
  - **Kryteria akceptacji:**
    - [ ] Apex Charts: 2 osie Y
      - Oś 1: Cena energii [PLN/kWh] (linia)
      - Oś 2: Moc grzania [kW] (bar chart)
    - [ ] Horyzont: ostatnie 24h + prognoza na 24h
    - [ ] Wizualnie widać że grzanie przesuwa się na tańsze godziny
    - [ ] Przykładowy YAML: `examples/lovelace_price_plan_chart.yaml`

- [ ] **T5.4.3:** Statystyki długoterminowe
  - **Priorytet:** Niski
  - **Czas:** 2h
  - **Zależności:** T5.4.2
  - **Kryteria akceptacji:**
    - [ ] Wykorzystanie HA statistics (long-term stats)
    - [ ] Możliwość zobaczenia kosztów za cały sezon grzewczy
    - [ ] Porównanie rok do roku (jeśli dane dostępne)
    - [ ] Eksport do CSV (opcjonalnie)

---

### 5.5 Fine-tuning wag MPC

- [ ] **T5.5.1:** Tryby optymalizacji (preset economic mode)
  - **Priorytet:** Średni
  - **Czas:** 3h
  - **Zależności:** T5.2.2
  - **Kryteria akceptacji:**
    - [ ] Nowy preset: "ECO" (oprócz HOME, AWAY, SLEEP)
    - [ ] Preset ECO:
      - w_comfort = 0.5 (niższy priorytet)
      - w_energy = 0.1
      - w_cost = 0.4 (najwyższy priorytet)
      - max_overshoot = 2.0°C
    - [ ] Użytkownik może przełączyć: HOME → ECO przez UI
    - [ ] Logowanie: "ECO mode: prioritizing cost over comfort"

- [ ] **T5.5.2:** Automatyczne przełączanie trybu na podstawie ceny
  - **Priorytet:** Niski
  - **Czas:** 2h
  - **Zależności:** T5.5.1
  - **Kryteria akceptacji:**
    - [ ] Opcja w Config: "auto_eco_mode" (default: False)
    - [ ] Jeśli włączone:
      - Gdy cena > 150% średniej → przełącz na ECO
      - Gdy cena < 100% średniej → przełącz na HOME
    - [ ] Notyfikacja użytkownika (persistent notification)
    - [ ] Możliwość override manualnego

- [ ] **T5.5.3:** User-configurable weights (zaawansowane)
  - **Priorytet:** Niski
  - **Czas:** 3h
  - **Zależności:** T5.5.1
  - **Kryteria akceptacji:**
    - [ ] Options Flow: sekcja "Advanced - MPC Weights"
    - [ ] Slidery: w_comfort, w_energy, w_cost (0.0 - 1.0)
    - [ ] Live preview (symulacja na danych historycznych)
    - [ ] Warning: "Zmieniaj tylko jeśli wiesz co robisz"
    - [ ] Przycisk: "Reset to defaults"

---

### 5.6 Dokumentacja i testy

- [ ] **T5.6.1:** Testy jednostkowe optymalizacji kosztów
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T5.2.3
  - **Kryteria akceptacji:**
    - [ ] Test PriceProvider (różne formaty encji)
    - [ ] Test CostTracker (obliczanie kosztów)
    - [ ] Test pre-heating strategy (MPC + taryfa dwustrefowa)
    - [ ] Coverage > 75%

- [ ] **T5.6.2:** Test integracyjny - symulacja miesiąca z taryfą
  - **Priorytet:** Wysoki
  - **Czas:** 4h
  - **Zależności:** T5.6.1
  - **Kryteria akceptacji:**
    - [ ] Symuluj 30 dni z taryfą G12 (Polska)
    - [ ] Porównaj 3 scenariusze:
      1. ON/OFF thermostat
      2. MPC bez optymalizacji kosztów (w_cost=0)
      3. MPC z optymalizacją kosztów (w_cost=0.3)
    - [ ] Oczekiwane wyniki:
      - MPC(bez) oszczędza 20-30% energii vs ON/OFF
      - MPC(z kosztami) oszczędza dodatkowo 10-15% kosztów
    - [ ] Komfort (RMSE) porównywalny we wszystkich scenariuszach

- [ ] **T5.6.3:** Test na danych rzeczywistych (opcjonalnie)
  - **Priorytet:** Średni
  - **Czas:** 4h (+ 30 dni obserwacji)
  - **Zależności:** T5.6.2
  - **Kryteria akceptacji:**
    - [ ] Włącz optymalizację kosztów w rzeczywistym systemie
    - [ ] Monitoruj przez 30 dni
    - [ ] Zbieraj dane:
      - Rzeczywiste rachunki za energię
      - Zużycie energii [kWh]
      - Koszty [PLN]
    - [ ] Porównaj z poprzednim miesiącem (lub rokiem)
    - [ ] Dokumentuj wyniki jako case study

- [ ] **T5.6.4:** Dokumentacja optymalizacji kosztów
  - **Priorytet:** Wysoki
  - **Czas:** 3h
  - **Zależności:** T5.6.3
  - **Kryteria akceptacji:**
    - [ ] README sekcja "Cost Optimization"
    - [ ] Wyjaśnienie:
      - Jak działa load shifting
      - Jak skonfigurować encję cen
      - Jakie oszczędności można oczekiwać
      - Tryb ECO vs COMFORT
    - [ ] Przykłady konfiguracji:
      - Taryfa G12 (Polska)
      - Nordpool (Skandynawia)
      - EPEX Spot (Europa)
    - [ ] Screenshots dashboard kosztów
    - [ ] FAQ: "Czy to naprawdę oszczędza pieniądze?"

---

## Kamienie milowe

- **M5.1:** Integracja cen energii działa (koniec tygodnia 1)
- **M5.2:** Strategia load shifting zaimplementowana (koniec tygodnia 2)
- **M5.3:** Dashboard kosztów gotowy (koniec tygodnia 3)
- **M5.4:** Testy pokazują oszczędności 10-15% kosztów (koniec tygodnia 4)

---

## Metryki sukcesu fazy

- [ ] MPC przesuwa grzanie na tańsze godziny (widoczne na wykresie)
- [ ] Oszczędności kosztów: 10-15% vs MPC bez optymalizacji
- [ ] Komfort nie jest znacząco pogorszony (RMSE wzrost < 20%)
- [ ] Dashboard wyraźnie pokazuje oszczędności
- [ ] Użytkownik może łatwo włączyć/wyłączyć optymalizację kosztów

---

## Notatki

- Optymalizacja kosztów działa najlepiej z taryfą dynamiczną (spot price)
- Dla taryfy dwustrefowej (G12) oszczędności będą mniejsze ale wciąż znaczące
- Ważne: nie pogarszaj komfortu za bardzo - użytkownik wyłączy optymalizację
- Pre-heating musi być inteligentny - za duży overshoot = dyskomfort
- Dashboard kosztów to killer feature - użytkownik MUSI widzieć oszczędności
- Faza 5 to "icing on the cake" - system działa bez tego, ale to daje WOW factor

---

**Poprzednia faza:** [Faza 4: Zaawansowane funkcje](./phase-4-advanced-features.md)
**Następna faza:** [Faza 6: Publikacja HACS](./phase-6-hacs-publication.md)
