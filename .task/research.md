# Research - Notatki badawcze i eksperymenty

**Cel:** Dokumentacja eksperymentów, research notes, literature review

---

## Literatura i referencje

### MPC Theory

- [ ] **"Model Predictive Control: Theory, Computation, and Design"** - Rawlings, Mayne & Diehl (2020)
  - 📖 Biblia MPC
  - Rozdział 2: Linear MPC (nasza implementacja)
  - Rozdział 6: Nonlinear MPC (backlog v1.3)
  - [Link do książki](https://sites.engineering.ucsb.edu/~jbraw/mpc/)

- [ ] **"Model Predictive Control for Buildings"** - IEEE Control Systems Magazine (2016)
  - Szczegóły implementacji MPC dla HVAC
  - Case studies z real-world savings
  - Typowe wartości parametrów (Q, R, S)

- [ ] **"Advanced Control Strategies for Heating Systems"** - Energy and Buildings (2019)
  - Porównanie PI, MPC, adaptive MPC
  - Wyniki: MPC oszczędza 15-25% vs PI

### Thermal Modeling

- [ ] **"Simplified thermal models for buildings"** - Building and Environment (2018)
  - Model 1R1C, 2R2C, 3R3C comparison
  - Kiedy wystarczy prosty model
  - Identyfikacja parametrów (RLS)

- [ ] **"Parameter estimation for building thermal models"** - Energy Procedia (2017)
  - Różne metody: RLS, Kalman Filter, Gradient Descent
  - Porównanie dokładności i convergence rate

### Underfloor Heating

- [ ] **"Control strategies for radiant floor heating"** - ASHRAE Transactions (2015)
  - Specyfika ogrzewania podłogowego (duża bezwładność)
  - Optymalne parametry PID/PI
  - PWM strategies dla ON/OFF valves

- [ ] **"Thermal mass utilization in buildings"** - Applied Energy (2020)
  - Wykorzystanie masy termicznej jako magazynu energii
  - Load shifting strategies
  - Case study: 20% cost reduction

### Machine Learning for HVAC

- [ ] **"LSTM-based prediction of building thermal behavior"** - Applied Energy (2021)
  - Neural networks dla predykcji zakłóceń
  - Comparison: LSTM vs linear model
  - Wniosek: LSTM lepsze dla complex disturbances

- [ ] **"Reinforcement learning for building control"** - Nature Energy (2022)
  - RL vs MPC comparison
  - RL: lepsze long-term, ale trudniejsze w implementacji
  - MPC: dobry trade-off (explainable + performant)

---

## Eksperymenty

### Eksperyment 1: Porównanie 1R1C vs 2R2C

**Cel:** Sprawdzić czy model 2R2C daje znacząco lepsze wyniki dla ogrzewania podłogowego

**Setup:**
- Dane: 30 dni historii z rzeczywistego systemu
- Podział: 70% training, 30% test
- Metryki: RMSE, MAE, R²

**Hipoteza:** 2R2C powinien dać RMSE < 0.7°C (vs 1R1C: ~0.9°C)

**Wyniki:** (do uzupełnienia po implementacji)

**Wnioski:** (TBD)

---

### Eksperyment 2: Tuning wag MPC (w_comfort, w_energy, w_cost)

**Cel:** Znaleźć optymalne wagi dla różnych use cases

**Setup:**
- Symulacja 30 dni z różnymi wagami
- Grid search: w_comfort ∈ [0.5, 0.7, 0.9], w_energy ∈ [0.1, 0.2, 0.3]
- Metryki:
  - Komfort: RMSE [°C]
  - Energia: total kWh
  - Trade-off: Pareto front

**Wyniki:** (TBD)

**Wnioski:** (TBD)

---

### Eksperyment 3: Impact of horizon length (Np)

**Cel:** Czy dłuższy horyzont = lepsze wyniki?

**Setup:**
- Testuj Np ∈ [12, 24, 36, 48] (2h, 4h, 6h, 8h)
- Fixed Nc = Np/2
- Metryka: RMSE, computation time

**Hipoteza:** Np=24 (4h) to sweet spot (trade-off accuracy vs speed)

**Wyniki:** (TBD)

**Wnioski:** (TBD)

---

### Eksperyment 4: Solar gains impact

**Cel:** Ile procent oszczędności dają solar gains w modelu?

**Setup:**
- Porównaj 2 scenariusze:
  1. MPC bez Q_solar
  2. MPC z Q_solar
- Dom z dużymi oknami południowymi
- Sunny week (lipiec)

**Hipoteza:** 5-10% redukcja zużycia energii

**Wyniki:** (TBD)

**Wnioski:** (TBD)

---

### Eksperyment 5: Load shifting effectiveness

**Cel:** Ile można zaoszczędzić przez przesunięcie grzania na tańsze godziny?

**Setup:**
- Taryfa G12 (Polska): tania noc (0.4 PLN/kWh), drogi dzień (0.7 PLN/kWh)
- Porównaj:
  1. MPC bez optymalizacji kosztów (w_cost=0)
  2. MPC z optymalizacją (w_cost=0.3)
- Metryki: koszt miesięczny, komfort (RMSE)

**Hipoteza:** 10-15% redukcja kosztów, RMSE wzrost < 10%

**Wyniki:** (TBD)

**Wnioski:** (TBD)

---

## Otwarte pytania badawcze

### Q1: Czy stochastic MPC jest warte dodatkowej złożoności?

**Problem:** Prognoza pogody ma niepewność (±2-3°C)

**Opcje:**
- Deterministic MPC (aktualnie) - używa single forecast
- Stochastic MPC - uwzględnia uncertainty, optymalizuje expected cost
- Scenario-based MPC - multiple forecasts, average solution

**Next steps:**
1. Literature review (robust MPC, stochastic MPC)
2. Implementacja prototypu (scenario-based)
3. Porównanie na real data

**Effort:** High, value: Medium (?)

---

### Q2: Jak modelować otwarcie okna?

**Problem:** Otwarcie okna to gwałtowne zakłócenie (sudden disturbance)

**Opcje:**
- Ignoruj (MPC będzie reagować z opóźnieniem)
- Binary sensor + manual override (jeśli okno otwarte → wyłącz grzanie)
- Modeluj jako dodatkowy opór termiczny (R zmniejsza się)

**Next steps:**
1. Zbierz dane z sensorem otwarcia okna
2. Zmierz impact na temperaturę (ΔT przy otwartym oknie)
3. Zamodeluj w thermal model

**Effort:** Medium, value: High (common use case)

---

### Q3: Machine learning vs model-based?

**Problem:** Czy LSTM może zastąpić thermal model?

**Comparison:**

| Cecha | Model-based MPC | Learning-based (LSTM) |
|-------|----------------|----------------------|
| Interpretability | ✅ High | ❌ Black box |
| Data requirement | ✅ 7-30 days | ❌ Months/years |
| Generalization | ✅ Physics-based | ❌ Training data only |
| Performance | ✅ Good | ✅ Potentially better |
| Complexity | ✅ Medium | ❌ High |

**Wniosek wstępny:** Model-based lepsze dla open-source projektu (prostsze, explainable)

**Backlog:** LSTM jako opcjonalny upgrade (v2.0)

---

## Benchmarks (do uzupełnienia)

### Hardware performance

| Hardware | Rooms | Np | Nc | Time [s] | Notes |
|----------|-------|----|----|----------|-------|
| RPi 4 (4GB) | 1 | 24 | 12 | TBD | |
| RPi 4 (4GB) | 5 | 24 | 12 | TBD | |
| RPi 5 (8GB) | 20 | 24 | 12 | TBD | Target < 5s |
| Desktop (i7) | 20 | 48 | 24 | TBD | Benchmark |

### Algorithm performance (simulated)

| Scenario | Controller | RMSE [°C] | Energy [kWh/day] | Cost [PLN/day] |
|----------|-----------|-----------|------------------|----------------|
| Winter, -5°C | ON/OFF | TBD | TBD | TBD (baseline) |
| Winter, -5°C | PI | TBD | TBD | TBD |
| Winter, -5°C | MPC | TBD | TBD | TBD |
| Winter, -5°C | MPC + cost opt | TBD | TBD | TBD (goal: -15%) |

---

## Użyteczne linki

### MPC Software & Tools

- **do-mpc:** https://www.do-mpc.com/ - Python MPC library (nonlinear)
- **CasADi:** https://web.casadi.org/ - Symbolic optimization
- **CVXPY:** https://www.cvxpy.org/ - Convex optimization
- **OSQP:** https://osqp.org/ - Fast QP solver

### Home Assistant

- **Developer Docs:** https://developers.home-assistant.io/
- **HACS:** https://hacs.xyz/
- **Community Forum:** https://community.home-assistant.io/

### Academic Resources

- **Google Scholar:** Search "MPC building control"
- **ResearchGate:** Papers on thermal modeling
- **IEEE Xplore:** Control theory papers

---

## Notatki ze spotkań / dyskusji

### 2025-10-26: Initial research

- Przeczytano: MPC_THEORY_AND_PRACTICE.md
- Przeczytano: "ZAAWANSOWANE SYSTEMY STEROWANIA OGRZEWANIEM PODŁOGOWYM.md"
- Wnioski:
  - Model 1R1C wystarczający dla MVP
  - PI jako fallback to must-have
  - Parametry domyślne: Kp=10, Ti=1500s dla podłogówki
  - Horyzont Np=24 (4h) optymalny

---

## Research TODO

- [ ] Literature review: stochastic MPC (Q1)
- [ ] Experiment: 1R1C vs 2R2C (Q2)
- [ ] Experiment: MPC weights tuning (Q3)
- [ ] Benchmark: RPi 4 performance (Q4)
- [ ] Case study: real installation for 3 months (Q1)

---

**Ostatnia aktualizacja:** 2025-10-26

**Kontakt:** Issues lub Discussions na GitHub
