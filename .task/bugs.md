# Bugs - Lista znanych błędów

**Cel:** Śledzenie aktualnych błędów i bugów do naprawy

**Status:** 🟢 Brak krytycznych bugów (na początku projektu)

---

## Legenda priorytetów

- 🔴 **Critical** - blokuje działanie, natychmiastowa naprawa
- 🟠 **High** - poważny problem, naprawa w ciągu tygodnia
- 🟡 **Medium** - uciążliwe, naprawa w ciągu miesiąca
- 🟢 **Low** - kosmetyczne, naprawa gdy będzie czas

---

## Otwarte bugi

### 🔴 Critical

*Brak krytycznych bugów*

---

### 🟠 High

*Brak bugów wysokiego priorytetu*

---

### 🟡 Medium

*Brak bugów średniego priorytetu*

---

### 🟢 Low

*Brak bugów niskiego priorytetu*

---

## Naprawione bugi (historia)

### v0.1.0 (przykład dla przyszłości)

- [ ] **BUG-001:** MPC optimization nie zbiega gdy Np > 48
  - **Priorytet:** 🟠 High
  - **Opis:** Solver SLSQP timeout po 10s dla dużych horyzontów
  - **Root cause:** Za duża liczba zmiennych (Nc × Np)
  - **Fix:** Zmniejszono Nc z 24 na 12, dodano warm-start
  - **Naprawione w:** commit abc123, v0.1.1
  - **Tester:** user@example.com

---

## Template zgłoszenia buga

Gdy znajdziesz bug, stwórz issue na GitHub z poniższymi informacjami:

```markdown
## Opis problemu
[Krótki opis co nie działa]

## Kroki do odtworzenia
1. Zainstaluj integrację
2. Skonfiguruj termostat X
3. Ustaw parametr Y na Z
4. Obserwuj błąd

## Oczekiwane zachowanie
[Co powinno się stać]

## Rzeczywiste zachowanie
[Co się dzieje zamiast tego]

## Środowisko
- Home Assistant version: 2024.10.1
- Adaptive Thermal Control version: 1.0.0
- Python version: 3.11
- Hardware: Raspberry Pi 4 (4GB)

## Logi
```
[Paste relevant logs from Home Assistant]
```

## Screenshots (opcjonalnie)
[Zrzuty ekranu pokazujące problem]

## Dodatkowy kontekst
[Inne informacje które mogą pomóc]
```

---

## Jak zgłosić bug?

1. **Sprawdź czy bug nie został już zgłoszony**
   - Przeszukaj GitHub Issues
   - Przeszukaj Discussions

2. **Zbierz informacje**
   - Logi z Home Assistant (`config/home-assistant.log`)
   - Wersja HA i integracji
   - Konfiguracja (Config Flow settings)

3. **Stwórz Issue na GitHub**
   - Użyj template "Bug report"
   - Label: `bug`
   - Dodaj priorytet jeśli oczywisty

4. **Bądź responsywny**
   - Odpowiadaj na pytania maintainerów
   - Testuj poprawki gdy dostępne

---

## Known Issues (nie bugi, ale ograniczenia)

### Limitacje algorytmu MPC

- MPC wymaga min. 7 dni danych historycznych
  - **Workaround:** Użyj PI controller przez pierwszy tydzień

- Optymalizacja może trwać > 2s dla 20+ pokoi
  - **Workaround:** Zmniejsz Np lub Nc w konfiguracji

- MPC nie radzi sobie dobrze z gwałtownymi zakłóceniami (otwarte okno)
  - **Workaround:** Dodaj sensor otwarcia okna (nie zaimplementowane w v1.0)

### Limitacje integracji

- Brak wsparcia dla systemów hybrydowych (grzejniki + podłogówka)
  - **Planowane:** v1.2

- Brak native integration z HA Energy dashboard
  - **Planowane:** v1.1

- PWM dla zaworów ON/OFF może powodować "clicking noise"
  - **Workaround:** Zwiększ PWM period do 60 min

---

## Debug tips

### MPC nie zbiega (optimization fails)

1. Sprawdź logi: `grep "MPC optimization" home-assistant.log`
2. Możliwe przyczyny:
   - Infeasible problem (ograniczenia sprzeczne)
   - Zbyt krótki timeout
   - Zły initial guess
3. Rozwiązania:
   - Sprawdź ograniczenia (u_min, u_max, temp limits)
   - Zwiększ `maxiter` w solverze
   - Restart integracji (reset state)

### Model drift (rosnący błąd predykcji)

1. Sprawdź sensor: `sensor.adaptive_thermal_[pokój]_prediction_error`
2. Jeśli RMSE > 2.0°C przez > 7 dni:
   - Re-train model: service `adaptive_thermal_control.retrain_model`
   - Sprawdź czy sensory działają poprawnie
3. Możliwe przyczyny:
   - Zmiana w budynku (nowa izolacja, uszczelnione okna)
   - Sensor drift (kalibracja temperatury)
   - Zmiany pogodowe (sezon)

### Zawór nie reaguje

1. Sprawdź atrybut climate entity: `valve_position`
2. Sprawdź czy encja zaworu jest dostępna:
   ```python
   state = hass.states.get('switch.valve_salon')
   ```
3. Możliwe przyczyny:
   - Encja offline (Zigbee, WiFi)
   - Permissions (HA nie może kontrolować urządzenia)
   - PWM scheduler problem (restart integracji)

---

**Ostatnia aktualizacja:** 2025-10-26

**Kontakt:** GitHub Issues - https://github.com/user/adaptive-thermal-control/issues
