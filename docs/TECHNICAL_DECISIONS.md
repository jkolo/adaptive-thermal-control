# Decyzje techniczne - Adaptive Thermal Control

## Wprowadzenie

Ten dokument przedstawia kluczowe decyzje techniczne, które należy podjąć przed rozpoczęciem implementacji projektu **Adaptive Thermal Control**. Każda sekcja zawiera porównanie dostępnych opcji z rekomendacjami dostosowanymi do wymagań projektu:

- 🎯 **Cel:** Najlepsza wydajność (czas implementacji: 3-6 miesięcy)
- 👨‍💻 **Doświadczenie:** Zaawansowany użytkownik Python/Home Assistant
- 💻 **Sprzęt:** Raspberry Pi 4/5
- 📦 **Dystrybucja:** Public release przez HACS

---

## 1. Wybór algorytmu sterowania

### Opcja A: Regulator PI (Proportional-Integral)

**Opis:**
Klasyczny regulator z człon proporcjonalnym i całkującym. Prosty w implementacji, dobrze sprawdza się dla ogrzewania podłogowego.

**Zalety:**
- ✅ Prosta implementacja (1-2 tygodnie)
- ✅ Niska złożoność obliczeniowa (idealne dla RPi)
- ✅ Dobrze zbadany i sprawdzony w praktyce
- ✅ Łatwe dostrajanie parametrów (Ziegler-Nichols, Cohen-Coon)
- ✅ Nie wymaga modelu termicznego

**Wady:**
- ❌ Brak predykcji przyszłych stanów
- ❌ Nie uwzględnia prognozy pogody
- ❌ Nie optymalizuje kosztów energii (taryfy)
- ❌ Reaguje dopiero gdy temperatura spadnie
- ❌ Oszczędności energii: ~20-30% vs ON/OFF

**Zastosowanie:**
Dobry jako **fallback** gdy MPC nie ma danych do uczenia lub jako punkt startowy projektu.

---

### Opcja B: Model Predictive Control (MPC)

**Opis:**
Zaawansowane sterowanie predykcyjne wykorzystujące model termiczny do przewidywania przyszłych stanów i optymalizacji funkcji kosztu.

**Zalety:**
- ✅ Predykcja temperatury na horyzoncie 4-8 godzin
- ✅ Wykorzystuje prognozę pogody i nasłonecznienia
- ✅ Optymalizacja kosztów energii (grzej tanio, wykorzystaj bezwładność)
- ✅ Naturalna obsługa ograniczeń (moc pieca, limity temperatur)
- ✅ Oszczędności energii: **20-40% vs ON/OFF + 10-15% dodatkowe przez optymalizację taryf**
- ✅ Komfort: redukcja naruszeń o 79-98%

**Wady:**
- ❌ Wymagana złożona implementacja (2-3 miesiące)
- ❌ Potrzebny model termiczny (uczenie z danych)
- ❌ Większe obciążenie CPU (0.5-2s na cykl vs ~10ms dla PI)
- ❌ Wymaga 7-30 dni danych historycznych do nauki

**Wymagania techniczne:**
- Solver optymalizacyjny: `scipy.optimize.minimize` (SLSQP lub L-BFGS-B)
- Biblioteki: `numpy`, `scipy`
- Obliczenia: wykonywalne na RPi 4/5 (optymalizacja trwa <2s)

---

### Opcja C: Hybrydowe (PI → MPC)

**Opis:**
Start z regulatorem PI, stopniowa migracja do MPC w miarę zbierania danych.

**Zalety:**
- ✅ Szybki start (system działa od razu)
- ✅ Zbieranie danych w tle dla MPC
- ✅ Bezpieczne przejście (PI jako fallback)
- ✅ Możliwość porównania wydajności PI vs MPC

**Wady:**
- ❌ Dodatkowa praca (implementacja obu algorytmów)
- ❌ Opóźnienie pełnych korzyści (MPC działa dopiero po 7+ dniach)

---

### ⭐ REKOMENDACJA: Opcja B (MPC od początku) z PI jako fallback

**Uzasadnienie:**

Biorąc pod uwagę:
- Cel: **najlepsza wydajność** (nie szybkość wdrożenia)
- Doświadczenie: zaawansowane (obsługa złożonych algorytmów nie jest problemem)
- Czas: 3-6 miesięcy (wystarczający dla pełnej implementacji MPC)
- Public release: MPC to USP (Unique Selling Point) - wyróżnik na rynku

**Rekomendowana architektura:**
```
┌─────────────────────────────────────┐
│  Climate Entity (Termostat)         │
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │  MPC Core    │  │  PI Fallback│ │
│  │ (primary)    │◄─┤  (backup)   │ │
│  └──────┬───────┘  └─────────────┘ │
│         │                           │
│  ┌──────▼───────┐                  │
│  │ Thermal Model│                  │
│  │ (learned)    │                  │
│  └──────────────┘                  │
└─────────────────────────────────────┘
```

**Implementacja etapowa:**
1. **Miesiąc 1:** Podstawowa struktura + PI fallback (system działa)
2. **Miesiąc 2:** Model termiczny + uczenie z danych historycznych
3. **Miesiąc 3-4:** MPC core + optymalizacja
4. **Miesiąc 5-6:** Zaawansowane features (koszty, wielostrefa, PWM)

---

## 2. Architektura implementacji

### Opcja A: AppDaemon

**Opis:**
Framework do pisania automatyzacji w Pythonie dla Home Assistant. Działa jako addon.

**Zalety:**
- ✅ Łatwy dostęp do wszystkich encji HA
- ✅ Automatyczny restart przy błędach
- ✅ Scheduler wbudowany
- ✅ Dobrze udokumentowany

**Wady:**
- ❌ Nie jest to "prawdziwa" integracja HA
- ❌ Brak Config Flow (konfiguracja przez YAML apps.yaml)
- ❌ Trudniejsza dystrybucja przez HACS
- ❌ Nie tworzy Climate entities natywnie (trzeba użyć MQTT lub template)
- ❌ Ciężki (może spowalniać HA na RPi)

**Przykład z CHAT.md:**
```python
class HeatingMPC(hass.Hass):
    def initialize(self):
        self.run_every(self.control_loop, "now", 600)
```

---

### Opcja B: Custom Component (Native Integration)

**Opis:**
Pełnoprawna integracja Home Assistant jako custom component.

**Zalety:**
- ✅ **Najlepsze dla public release przez HACS**
- ✅ Config Flow (konfiguracja przez UI)
- ✅ Natywne Climate entities (oficjalne wsparcie)
- ✅ Pełna kontrola nad kodem
- ✅ Możliwość optymalizacji wydajności
- ✅ Sensor entities dla diagnostyki
- ✅ Translations (i18n)
- ✅ Łatwa aktualizacja przez HACS

**Wady:**
- ❌ Bardziej złożona struktura (manifest, config_flow, platforms)
- ❌ Wymaga znajomości architektury HA

**Struktura:**
```
custom_components/adaptive_thermal_control/
├── __init__.py          # Setup integration
├── manifest.json        # Dependencies
├── config_flow.py       # UI configuration
├── const.py             # Constants
├── climate.py           # Climate platform
├── sensor.py            # Sensor platform
├── coordinator.py       # Data coordinator
├── mpc_controller.py    # MPC algorithm
├── thermal_model.py     # Thermal model
└── translations/
    ├── en.json
    └── pl.json
```

---

### Opcja C: Zewnętrzny kontener Docker + REST API

**Opis:**
Oddzielny serwis HTTP z algorytmem MPC, HA komunikuje się przez REST.

**Zalety:**
- ✅ Pełna separacja (crash MPC nie wpływa na HA)
- ✅ Możliwość uruchomienia na osobnej maszynie
- ✅ Łatwe skalowanie (więcej mocy obliczeniowej)

**Wady:**
- ❌ Większa złożoność deployment
- ❌ Problemy z siecią (latency, reliability)
- ❌ Trudna dystrybucja dla użytkowników (muszą uruchomić kontener)
- ❌ **Niekompatybilne z HACS** (HACS dystrybuuje tylko HA integrations)

---

### ⭐ REKOMENDACJA: Opcja B (Custom Component)

**Uzasadnienie:**

Dla public release przez HACS **to jedyna sensowna opcja**.

**Korzyści:**
- Standardowy sposób dystrybucji HA integrations
- Użytkownicy znają ten format (łatwa instalacja)
- Profesjonalny wygląd (Config Flow, natywne encje)
- Pełna integracja z ekosystemem HA

**Wymagane umiejętności (które już posiadasz):**
- Python (zaawansowany ✓)
- Struktura HA integrations (do nauki, 1-2 tygodnie)
- Config Flow API (dokumentacja dostępna)

**Wzorce do naśladowania:**
- `homeassistant/components/generic_thermostat` - podstawowy termostat
- Custom integrations z HACS (np. Better Thermostat)

---

## 3. Model termiczny

### Opcja A: Model 1R1C (jeden opór, jedna pojemność)

**Opis:**
Najprostszy model termiczny:
```
C·dT/dt = Q_grzanie - (T - T_zewn)/R
```

**Parametry:**
- `R` - opór termiczny [K/W]
- `C` - pojemność cieplna [J/K]
- `τ = R·C` - stała czasowa (typowo 10-30 godzin dla ogrzewania podłogowego)

**Zalety:**
- ✅ Prosta implementacja
- ✅ Szybka identyfikacja parametrów (2 parametry)
- ✅ Niskie wymagania obliczeniowe
- ✅ Wystarczająca dokładność dla większości przypadków

**Wady:**
- ❌ Nie modeluje warstw termicznych (beton, izolacja, etc.)
- ❌ Może być niewystarczający dla skomplikowanych budynków

**Dokładność:** ±0.5-1°C dla większości scenariuszy

---

### Opcja B: Model 2R2C (dwa opory, dwie pojemności)

**Opis:**
Rozszerzony model uwzględniający warstwową strukturę:
```
Warstwa 1 (masa termiczna): C1, R1
Warstwa 2 (otoczka budynku): C2, R2
```

**Parametry:**
- 4 parametry do identyfikacji (R1, C1, R2, C2)

**Zalety:**
- ✅ Lepsza dokładność (±0.3-0.5°C)
- ✅ Lepsze modelowanie bezwładności
- ✅ Dokładniejsze przewidywanie czasu nagrzewania

**Wady:**
- ❌ 2x więcej parametrów (wolniejsza identyfikacja)
- ❌ Większe wymagania obliczeniowe
- ❌ Ryzyko overfitting (szczególnie przy małych danych)

**Dokładność:** ±0.3-0.5°C

---

### Opcja C: Model data-driven (ML bez fizycznego modelu)

**Opis:**
Uczenie modelu bezpośrednio z danych (np. gradient boosting, sieci neuronowe).

**Zalety:**
- ✅ Może uchwycić nieliniowości
- ✅ Nie wymaga założeń o strukturze termicznej

**Wady:**
- ❌ **Bardzo wysokie wymagania obliczeniowe** (niewykonalne na RPi dla MPC w czasie rzeczywistym)
- ❌ Potrzeba dużo danych (>90 dni)
- ❌ Ryzyko overfitting
- ❌ Trudna interpretacja

**Wniosek:** Nieodpowiednie dla RPi i real-time MPC.

---

### ⭐ REKOMENDACJA: Opcja A (Model 1R1C) z możliwością upgrade do 2R2C

**Uzasadnienie:**

**Faza 1 (Miesiąc 2-3): Start z 1R1C**
- Prosty, szybki do implementacji
- Wystarczający dla większości przypadków
- Dobre do walidacji koncepcji

**Faza 2 (opcjonalnie Miesiąc 5+): Upgrade do 2R2C**
- Jeśli 1R1C nie daje zadowalającej dokładności
- Dla użytkowników z bardziej złożonymi budynkami
- Jako opcja konfiguracyjna (zaawansowani użytkownicy)

**Implementacja:**
```python
class ThermalModel:
    """Base class for thermal models"""

class Model1R1C(ThermalModel):
    """Simple 1R1C model - default"""

class Model2R2C(ThermalModel):
    """Advanced 2R2C model - optional"""
```

**Konfiguracja:**
```yaml
# Config option (advanced users only)
thermal_model_type: "1R1C"  # or "2R2C"
```

---

## 4. Biblioteki i narzędzia

### 4.1 Solver optymalizacyjny dla MPC

#### Opcja A: scipy.optimize.minimize (SLSQP)

**Opis:**
Solver dla nieliniowej optymalizacji z ograniczeniami.

```python
from scipy.optimize import minimize

result = minimize(
    fun=cost_function,
    x0=u_init,
    bounds=bounds,
    constraints=constraints,
    method='SLSQP'
)
```

**Zalety:**
- ✅ Wbudowany w scipy (brak dodatkowych zależności)
- ✅ Działa dobrze dla małych problemów (Nc=12, n_zones=20)
- ✅ Obsługuje nieliniowe ograniczenia
- ✅ **Wydajny na RPi** (0.5-2s dla 20 stref)

**Wady:**
- ❌ Wolniejszy niż dedykowane solvery QP
- ❌ Może utknąć w lokalnym minimum

**Optymalizacje:**
- Warm start (użyj poprzedniego rozwiązania jako x0)
- Cache macierzy stanu
- Ograniczenie horyzontu (Nc=6-12)

---

#### Opcja B: cvxpy (dedykowany solver QP)

**Opis:**
Biblioteka do konweksnej optymalizacji z profesjonalnymi solverami.

```python
import cvxpy as cp

u = cp.Variable((Nc, n_zones))
objective = cp.Minimize(cost_expression)
constraints = [u >= 0, u <= 100, ...]
problem = cp.Problem(objective, constraints)
problem.solve(solver=cp.OSQP)
```

**Zalety:**
- ✅ Szybsze rozwiązywanie (2-5x vs scipy dla QP)
- ✅ Gwarantowane znalezienie globalnego optimum (dla QP)
- ✅ Czytelny kod (deklaratywny)

**Wady:**
- ❌ **Dodatkowa zależność** (większy footprint)
- ❌ Kompilacja natywnych części (może być problem na niektórych platformach ARM)
- ❌ Wymaga linearyzacji modelu (utrata dokładności)

---

#### ⭐ REKOMENDACJA: Opcja A (scipy.optimize)

**Uzasadnienie:**

**Dla Raspberry Pi 4/5 i public release:**
- scipy już jest w HA dependencies (często używany)
- Mniej problemów z instalacją na ARM
- Wystarczająca wydajność dla naszego problemu
- Prostszy maintenance

**Strategia:**
1. Start z `scipy.optimize.minimize(method='SLSQP')`
2. Optymalizacje:
   - Warm start
   - Adaptive horizon (zmniejsz Nc gdy CPU zajęte)
3. Jeśli wydajność będzie problemem (>5s na cykl):
   - Rozważ cvxpy jako opcję konfiguracyjną

---

### 4.2 Algorytm identyfikacji parametrów

#### Opcja A: Batch Least Squares

**Opis:**
Jednorazowe dopasowanie parametrów do całego zbioru danych historycznych.

```python
from scipy.optimize import curve_fit

params, _ = curve_fit(model_function, X_hist, y_hist)
```

**Zalety:**
- ✅ Prosty w implementacji
- ✅ Wykorzystuje wszystkie dane naraz

**Wady:**
- ❌ Wymaga ponownego liczenia przy nowych danych
- ❌ Brak adaptacji online

---

#### Opcja B: Recursive Least Squares (RLS)

**Opis:**
Online learning - parametry aktualizowane z każdym nowym pomiarem.

```python
class RLSEstimator:
    def update(self, y_new, x_new):
        # Update P (covariance) and theta (parameters)
        ...
```

**Zalety:**
- ✅ **Adaptacja online** (parametry dostosowują się do zmian, np. sezon)
- ✅ Niskie wymagania pamięciowe (nie przechowuje całej historii)
- ✅ Szybka aktualizacja (każdy cykl)

**Wady:**
- ❌ Bardziej złożona implementacja
- ❌ Może "zapominać" ważne dane (wymaga forgetting factor)

---

#### ⭐ REKOMENDACJA: Opcja B (RLS) z初期 Batch LS

**Uzasadnienie:**

**Strategia hybrydowa:**
1. **Initial learning (7-30 dni):** Batch LS na danych historycznych
2. **Online adaptation:** RLS z forgetting factor λ=0.98

**Korzyści:**
- Szybki start z danych historycznych
- Ciągła adaptacja (parametry ewoluują z sezonem, zmianami w domu)
- Efektywność pamięciowa

**Implementacja:**
```python
class ThermalModelLearner:
    def initial_fit(self, history_data):
        """Batch LS from HA recorder data (7-30 days)"""

    def online_update(self, T_new, u_new, d_new):
        """RLS update every cycle (10 min)"""
```

---

## 5. Strategia wdrożenia

### Opcja A: Big Bang (wszystko naraz)

**Opis:**
Implementacja pełnego MPC od początku.

**Wady:**
- ❌ Długi czas bez działającego systemu
- ❌ Trudniejsze debugowanie
- ❌ Ryzyko porażki (jeśli coś nie działa, cały system nie działa)

**Niepolecane.**

---

### Opcja B: Etapowe (iteracyjne)

**Opis:**
Implementacja w fazach, każda faza dostarcza wartość.

**Fazy (szczegóły w PROJECT.md sekcja 8):**

1. **Miesiąc 1: Fundament**
   - Custom component skeleton
   - Config Flow
   - Climate entities z PI fallback
   - **Rezultat:** Działający termostat (prosty, ale działa)

2. **Miesiąc 2: Model**
   - Implementacja modelu 1R1C
   - Batch LS + RLS
   - Zbieranie danych
   - **Rezultat:** Parametry R, C nauczone

3. **Miesiąc 3-4: MPC Core**
   - Algorytm MPC
   - Funkcja kosztu (komfort + energia)
   - scipy.optimize
   - **Rezultat:** MPC działa dla pojedynczego pokoju

4. **Miesiąc 5: Features**
   - Prognoza pogody
   - Wielostrefa
   - Nasłonecznienie
   - **Rezultat:** Pełna funkcjonalność

5. **Miesiąc 6: Publikacja**
   - Optymalizacja kosztów
   - Dokumentacja
   - HACS release
   - **Rezultat:** Public release

**Zalety:**
- ✅ Działający system od Miesiąca 1
- ✅ Łatwe testowanie (każda faza osobno)
- ✅ Możliwość pivotu (zmiana planów na podstawie wyników)
- ✅ Motywacja (widoczny progress)

---

### ⭐ REKOMENDACJA: Opcja B (Etapowe)

**Uzasadnienie:**

**Agile approach** - każda iteracja dostarcza wartość.

**Kamienie milowe:**
- ✅ **Miesiąc 1:** System działa (PI)
- ✅ **Miesiąc 2:** Model się uczy
- ✅ **Miesiąc 3:** MPC działa (1 pokój)
- ✅ **Miesiąc 4:** MPC działa (multi-zona)
- ✅ **Miesiąc 5:** Full features
- ✅ **Miesiąc 6:** Public release

**Risk mitigation:**
- Jeśli MPC nie działa dobrze → fallback na PI (system nadal użyteczny)
- Jeśli parametry się nie uczą → manual tuning (jak tradycyjny termostat)
- Jeśli coś jest zbyt wolne → adaptive horizon / simplify model

---

## 6. Podsumowanie rekomendacji

### Stack technologiczny

| Komponent | Rekomendacja | Alternatywa |
|-----------|--------------|-------------|
| **Algorytm** | MPC (scipy.optimize) | PI jako fallback |
| **Architektura** | Custom Component | - |
| **Model termiczny** | 1R1C → (opcjonalnie 2R2C) | - |
| **Solver** | scipy.optimize.minimize(SLSQP) | cvxpy (advanced) |
| **Uczenie** | Batch LS + RLS | - |
| **Dystrybucja** | HACS Custom Repository | - |
| **UI** | Config Flow | - |

### Zależności Python

**manifest.json:**
```json
{
  "requirements": [
    "numpy>=1.21.0",
    "scipy>=1.7.0"
  ]
}
```

**Opcjonalne (advanced users):**
- `numba` - JIT compilation dla przyspieszenia obliczeń

### Wydajność na Raspberry Pi 4/5

**Oczekiwane czasy:**
- MPC optimization (20 stref, Np=24, Nc=12): **0.5-2 sekundy**
- RLS update: **<10ms**
- Total cycle time (10 min interval): **<2% CPU usage**

**Optymalizacje:**
- Warm start dla solvera
- Cache macierzy stanu (A, B)
- Adaptive horizon (zmniejsz Nc gdy system obciążony)

---

## 7. Plan działania (Action Items)

### Przed rozpoczęciem kodu

- [ ] Utworzyć repozytorium GitHub
- [ ] Skonfigurować pre-commit hooks (black, isort, mypy)
- [ ] Przygotować strukturę projektu
- [ ] Dodać LICENSE (MIT)
- [ ] Utworzyć README.md (wstępny)

### Faza 1 (Miesiąc 1): Fundament

**Tydzień 1-2:**
- [ ] Struktura custom_component
- [ ] manifest.json
- [ ] Podstawowy __init__.py
- [ ] Config Flow (step 1: global config)

**Tydzień 3-4:**
- [ ] Climate platform (podstawowy)
- [ ] PI controller (fallback)
- [ ] Pierwszy test na rzeczywistym HA

**Milestone:** 🎯 Działający termostat z PI

### Faza 2 (Miesiąc 2): Model termiczny

**Tydzień 1-2:**
- [ ] Implementacja modelu 1R1C
- [ ] Integracja z HA recorder (pobieranie danych historycznych)
- [ ] Batch Least Squares dla初期 fit

**Tydzień 3-4:**
- [ ] Recursive Least Squares (online learning)
- [ ] Walidacja modelu (prediction error tracking)
- [ ] Sensor entities dla diagnostyki

**Milestone:** 🎯 Model uczy się parametrów z danych

### Faza 3-4 (Miesiąc 3-4): MPC Core

**Tydzień 1:**
- [ ] Implementacja funkcji kosztu
- [ ] Predykcja na horyzoncie Np
- [ ] Constraints (bounds, power limits)

**Tydzień 2:**
- [ ] Integracja scipy.optimize
- [ ] Warm start mechanism
- [ ] Performance testing na RPi

**Tydzień 3:**
- [ ] Multi-zone coordination
- [ ] Fair-share algorithm
- [ ] Testy rzeczywiste (1-3 pokoje)

**Tydzień 4:**
- [ ] Bugfixes i optymalizacja
- [ ] Stress testing (10-20 pokoi)
- [ ] Documentation update

**Milestone:** 🎯 MPC działa dla wielu stref

### Faza 5 (Miesiąc 5): Advanced Features

**Tydzień 1-2:**
- [ ] Integracja weather forecast
- [ ] Solar irradiance + orientacja okien
- [ ] Sąsiednie pomieszczenia (thermal coupling)

**Tydzień 3-4:**
- [ ] PWM dla zaworów ON/OFF
- [ ] Advanced diagnostics (sensors)
- [ ] Dashboard templates (Lovelace)

**Milestone:** 🎯 Pełna funkcjonalność z REQUIREMENTS.md

### Faza 6 (Miesiąc 6): Publikacja

**Tydzień 1:**
- [ ] Optymalizacja kosztów energii (price entity)
- [ ] Strategia "grzej teraz bo później drożej"

**Tydzień 2:**
- [ ] Dokumentacja użytkownika (README, wiki)
- [ ] Przykładowe konfiguracje
- [ ] Troubleshooting guide

**Tydzień 3:**
- [ ] Translations (EN, PL)
- [ ] CI/CD setup (GitHub Actions)
- [ ] Unit tests

**Tydzień 4:**
- [ ] HACS submission
- [ ] Community forum post
- [ ] Initial release v1.0.0

**Milestone:** 🎯 Public release przez HACS

---

## 8. Criteria sukcesu

### Metryki techniczne

- ✅ Stabilność: <1 crash/tydzień
- ✅ Wydajność: <2s optimization time na cykl
- ✅ Dokładność modelu: prediction error <0.5°C
- ✅ Oszczędność energii: >20% vs ON/OFF (verified on real data)
- ✅ Komfort: temperatura ±0.5°C od nastawy (95% czasu)

### Metryki user experience

- ✅ Instalacja: <10 minut (przez HACS)
- ✅ Konfiguracja: <30 minut (przez Config Flow)
- ✅ Dokumentacja: kompletna i zrozumiała
- ✅ Support: aktywny (GitHub issues, forum HA)

### Metryki community

- ✅ GitHub stars: >50 (rok 1)
- ✅ HACS installs: >100 (rok 1)
- ✅ Community contributions: >5 contributors
- ✅ Forum posts: aktywne wsparcie

---

## 9. Ryzyka i mitigation

### Ryzyko 1: MPC zbyt wolny na RPi

**Prawdopodobieństwo:** Średnie
**Impact:** Wysoki

**Mitigation:**
- Start z małym Np, Nc (Np=12, Nc=6)
- Adaptive horizon (zmniejsz gdy CPU busy)
- Fallback na PI gdy timeout
- Możliwość wyłączenia MPC w config

### Ryzyko 2: Model termiczny niedokładny

**Prawdopodobieństwo:** Średnie
**Impact:** Średni

**Mitigation:**
- Start z 1R1C (prosty, łatwiejszy fit)
- Długi okres uczenia (30 dni)
- Manual tuning option dla zaawansowanych
- Fallback na PI

### Ryzyko 3: Brak danych historycznych (nowi użytkownicy)

**Prawdopodobieństwo:** Wysoki
**Impact:** Niski

**Mitigation:**
- PI działa od razu (zbiera dane w tle)
- Default parameters (conservative)
- Po 7 dniach → automatic switch to MPC

### Ryzyko 4: Trudności z HACS submission

**Prawdopodobieństwo:** Niski
**Impact:** Średni

**Mitigation:**
- Studia existing HACS integrations
- Czytaj HACS guidelines wcześnie
- Test z beta testers przed submission

---

## 10. Następne kroki

### Natychmiastowe (teraz)

1. ✅ **Przeczytać ten dokument** i potwierdzić rekomendacje
2. [ ] **Utworzyć repozytorium GitHub**
3. [ ] **Setup development environment:**
   - Clone HA core (dla testów)
   - Virtual environment z numpy, scipy
   - Pre-commit hooks

### Tydzień 1

4. [ ] **Rozpocząć Fazę 1:** Struktura custom component
5. [ ] **Czytać dokumentację:**
   - Home Assistant Developer Docs (integration)
   - Config Flow API
   - Climate platform

### Tracking

6. [ ] **Utworzyć GitHub Project Board** z fazami 1-6
7. [ ] **Weekly progress updates** (np. w tym repo)

---

## Podsumowanie

**Rekomendowana ścieżka:**

```
┌─────────────────────────────────────────────────────────┐
│ Custom Component (HACS) + MPC (scipy) + Model 1R1C     │
│                                                         │
│ Miesiąc 1: Fundament + PI                              │
│ Miesiąc 2: Model termiczny + uczenie                   │
│ Miesiąc 3-4: MPC Core                                  │
│ Miesiąc 5: Advanced features                           │
│ Miesiąc 6: Public release                              │
│                                                         │
│ Rezultat: Najlepsza integracja MPC dla HA 🎯           │
└─────────────────────────────────────────────────────────┘
```

**Kluczowe decyzje:**
- ✅ MPC (nie PI) - dla najlepszej wydajności
- ✅ Custom Component (nie AppDaemon) - dla HACS
- ✅ Model 1R1C (nie 2R2C) - start simple, iterate
- ✅ scipy.optimize (nie cvxpy) - compatible z RPi
- ✅ Etapowe wdrożenie (nie big bang) - risk mitigation

**Powodzenia! 🚀**

---

## Dodatek: Przydatne linki

### Dokumentacja Home Assistant

- [Developer Docs](https://developers.home-assistant.io/)
- [Integration Development](https://developers.home-assistant.io/docs/creating_integration_manifest)
- [Config Flow](https://developers.home-assistant.io/docs/config_entries_config_flow_handler)
- [Climate Platform](https://developers.home-assistant.io/docs/core/entity/climate)

### Przykładowe Custom Components

- [Generic Thermostat](https://github.com/home-assistant/core/tree/dev/homeassistant/components/generic_thermostat)
- [Better Thermostat](https://github.com/KartoffelToby/better_thermostat)
- [Versatile Thermostat](https://github.com/jmcollin78/versatile_thermostat)

### Algorytmy MPC

- scipy.optimize: https://docs.scipy.org/doc/scipy/reference/optimize.html
- MPC tutorial: https://www.do-mpc.com/en/latest/

### HACS

- [HACS Integration Guidelines](https://hacs.xyz/docs/publish/integration)
- [HACS Repository](https://github.com/hacs/integration)

### Community

- [Home Assistant Community Forum](https://community.home-assistant.io/)
- [Home Assistant Discord](https://discord.gg/home-assistant)
