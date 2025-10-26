# Backlog - Pomysły na przyszłość

**Cel:** Lista funkcjonalności i ulepszeń na kolejne wersje (post v1.0)

---

## Priorytety

- 🔥 **High** - ważne, duża wartość dla użytkowników
- 🌟 **Medium** - przydatne, nice-to-have
- 💡 **Low** - ciekawe, ale niska wartość / dużo pracy

---

## Funkcjonalności

### Model termiczny

- [ ] 🔥 **Model 2R2C** (dwa opory, dwie pojemności)
  - Lepsza dokładność dla ogrzewania podłogowego
  - Osobny stan dla podłogi vs powietrze
  - Estymacja 4 parametrów: R1, C1, R2, C2
  - **Effort:** High (2 tygodnie)

- [ ] 🌟 **Model z humidity** (wilgotność powietrza)
  - Wilgotność wpływa na odczuwalną temperaturę
  - Rozszerzenie funkcji kosztu: comfort_index = f(T, humidity)
  - Wymaga sensora wilgotności
  - **Effort:** Medium (1 tydzień)

- [ ] 💡 **Adaptive model selection** (1R1C vs 2R2C automatycznie)
  - System sam wybiera lepszy model na podstawie danych
  - Cross-validation: który daje niższy błąd?
  - **Effort:** Medium (1 tydzień)

### Algorytm sterowania

- [ ] 🔥 **Nonlinear MPC** (uwzględnienie nieliniowości)
  - Aktualnie: liniowy model
  - Rzeczywistość: nieliniowości (konwekcja, radiacja)
  - Solver: CasADi + IPOPT
  - **Effort:** Very High (3-4 tygodnie)

- [ ] 🌟 **Stochastic MPC** (uwzględnienie niepewności prognozy)
  - Prognoza pogody ma niepewność
  - Robust MPC: optymalizacja worst-case scenario
  - Scenario-based MPC: wiele scenariuszy, uśrednij
  - **Effort:** High (2-3 tygodnie)

- [ ] 🌟 **Adaptive MPC** (online tuning wag)
  - System uczy się preferencji użytkownika
  - Jeśli użytkownik często override → dostosuj wagi
  - Machine learning z historical overrides
  - **Effort:** High (2 tygodnie)

- [ ] 💡 **Economic MPC** (explicit cost in objective)
  - Aktualnie: weights (w_cost)
  - EMPC: bezpośrednia optymalizacja $$$ w funkcji celu
  - Lepsze wyniki dla time-varying prices
  - **Effort:** Medium (1 tydzień)

### Zaawansowane funkcje

- [ ] 🔥 **Cooling mode** (chłodzenie, klimatyzacja)
  - Ogrzewanie + chłodzenie w jednym systemie
  - Model termiczny działa w obie strony
  - Ograniczenia różne (cooling limits)
  - **Effort:** High (2-3 tygodnie)

- [ ] 🔥 **Demand response integration** (DSR)
  - Integracja z programami demand response
  - Gdy grid operator prosi o redukcję → MPC zmniejsza zużycie
  - Event: `demand_response_event` → ECO mode
  - **Effort:** Medium (1 tydzień)

- [ ] 🌟 **Occupancy detection** (obecność ludzi)
  - Integracja z sensorami PIR / phone tracking
  - Jeśli nikogo nie ma → Away mode automatycznie
  - Pre-heating przed powrotem (calendar integration)
  - **Effort:** Medium (1 tydzień)

- [ ] 🌟 **Weather radar integration** (dokładniejsza prognoza)
  - Prognoza na 15 minut z radaru pogodowego
  - Lepsze przewidywanie opadów → solar gains
  - **Effort:** Low (3 dni)

- [ ] 💡 **Learning-based disturbance prediction** (ML)
  - LSTM neural network do przewidywania zakłóceń
  - Uczy się z historii: typ dnia → typowe zakłócenia
  - Lepsze od prostej prognozy
  - **Effort:** Very High (4 tygodnie)

### UI i UX

- [ ] 🔥 **Dashboard template** (gotowy dashboard Lovelace)
  - Jeden klik → zainstaluj kompletny dashboard
  - Apex charts, gauge cards, etc. już skonfigurowane
  - **Effort:** Low (2 dni)

- [ ] 🌟 **Mobile app notifications**
  - Powiadomienie: "Model drift detected, retrain recommended"
  - Powiadomienie: "ECO mode saved 15 PLN this week!"
  - **Effort:** Low (1 dzień)

- [ ] 🌟 **Voice control integration**
  - "Hey Google, set living room to ECO mode"
  - "Alexa, what's the heating cost today?"
  - **Effort:** Low (2 dni)

- [ ] 💡 **Grafana dashboard** (zaawansowana wizualizacja)
  - Export danych do InfluxDB → Grafana
  - Piękne wykresy dla power users
  - **Effort:** Medium (1 tydzień)

### Integracje

- [ ] 🔥 **Home Assistant Energy dashboard integration**
  - Heating jako source w Energy dashboard
  - Native support (nie wymaga manual config)
  - **Effort:** Medium (1 tydzień)

- [ ] 🌟 **ESPHome integration** (bezpośrednie sterowanie)
  - Zamiast HA switch → bezpośrednio ESPHome device
  - Niższe latency, bardziej niezawodne
  - **Effort:** Medium (1 tydzień)

- [ ] 🌟 **Zigbee thermostat integration** (TRV valves)
  - Wsparcie dla termostatycznych zaworów Zigbee
  - Np. Aqara, IKEA Trådfri
  - **Effort:** Medium (1 tydzień)

- [ ] 💡 **Google Nest integration**
  - Kontrola przez Adaptive Thermal Control
  - Override Nest's algorithm z MPC
  - **Effort:** High (2 tygodnie)

### Optymalizacja i performance

- [ ] 🌟 **Numba JIT compilation** (przyspiesz obliczenia)
  - @njit na hot loops
  - 2-5x speedup
  - **Effort:** Low (2 dni)

- [ ] 🌟 **Alternative solvers** (więcej opcji optymalizacji)
  - OSQP (szybszy dla QP)
  - IPOPT (dla nonlinear MPC)
  - Gurobi (komercyjny, najszybszy - opcjonalnie)
  - **Effort:** Medium (1 tydzień)

- [ ] 💡 **Distributed MPC** (dla 20+ stref)
  - Każda strefa = osobny proces
  - Parallel optimization (multiprocessing)
  - Koordynacja przez message passing
  - **Effort:** Very High (4 tygodnie)

### Diagnostyka i debugging

- [ ] 🌟 **Debug mode** (szczegółowe logi)
  - Service call: `adaptive_thermal_control.enable_debug`
  - Loguje każdy krok MPC (cost, constraints, solution)
  - Zapisuje do pliku `/config/adaptive_thermal_debug.log`
  - **Effort:** Low (1 dzień)

- [ ] 🌟 **Model visualization** (wykresy w HA)
  - Wykres: predicted vs actual temperature
  - Wykres: control plan (u(0), u(1), ...)
  - Apex Charts custom card
  - **Effort:** Medium (1 tydzień)

- [ ] 💡 **What-if simulator** (symulacja różnych scenariuszy)
  - "Co by było gdyby temperatura zewnętrzna spadła o 10°C?"
  - Symulacja offline, wizualizacja wyników
  - **Effort:** High (2 tygodnie)

### Inne

- [ ] 🔥 **Automatic backup & restore**
  - Automatyczny backup parametrów modelu
  - Restore po reinstalacji HA
  - **Effort:** Low (2 dni)

- [ ] 🌟 **Multi-user profiles** (różne preferencje dla użytkowników)
  - Profil "Parent": priorytet komfort
  - Profil "Eco enthusiast": priorytet oszczędność
  - Automatyczne przełączanie na podstawie obecności
  - **Effort:** Medium (1 tydzień)

- [ ] 💡 **Remote monitoring** (cloud dashboard)
  - Opcjonalnie: wysyłaj dane do cloud
  - Dostęp z dowolnego miejsca (bez VPN)
  - Dashboard web: status, koszty, wykresy
  - **Effort:** Very High (4+ tygodni)

---

## Roadmap wstępny (post v1.0)

### v1.1 (Q1 2026)
- Model 2R2C
- Demand response integration
- Dashboard template
- HA Energy dashboard integration

### v1.2 (Q2 2026)
- Stochastic MPC
- Cooling mode (basic)
- Occupancy detection
- Alternative solvers (OSQP)

### v1.3 (Q3 2026)
- Adaptive MPC (learning user preferences)
- Nonlinear MPC (optional)
- ESPHome integration
- Zigbee TRV support

### v2.0 (Q4 2026)
- Full cooling support (heat pumps)
- Learning-based disturbance prediction (LSTM)
- Distributed MPC (20+ zones)
- Advanced diagnostics (what-if simulator)

---

## Jak dodać pomysł do backlogu?

1. Stwórz issue na GitHub z labelem `enhancement`
2. Opisz:
   - **Problem:** Co chcesz rozwiązać?
   - **Rozwiązanie:** Jak to zaimplementować?
   - **Alternatywy:** Inne podejścia?
   - **Value:** Ilu użytkowników to pomoże?
3. Community głosuje (👍 thumbs up)
4. Maintainer ocenia effort i dodaje do roadmap

---

## Pomysły odrzucone (i dlaczego)

- ❌ **Blockchain-based heating** - no practical value, buzzword
- ❌ **AI voice assistant built-in** - out of scope, use existing (Alexa, Google)
- ❌ **Cryptocurrency mining for heating** - legal issues, complexity
- ❌ **VR visualization of thermal flows** - cool but unnecessary

---

**Ostatnia aktualizacja:** 2025-10-26
