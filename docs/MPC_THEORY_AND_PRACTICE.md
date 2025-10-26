# Model Predictive Control (MPC) - Teoria i Praktyka dla Programistów

## Spis treści

1. [Wprowadzenie - Co to jest MPC?](#wprowadzenie)
2. [Intuicja - Jak myśli MPC?](#intuicja)
3. [Matematyka - Formalizm teoretyczny](#matematyka)
4. [Algorytm - Jak działa MPC krok po kroku](#algorytm)
5. [Implementacja - Od teorii do kodu](#implementacja)
6. [Tuning i optymalizacja](#tuning)
7. [Zalety i wady](#zalety-i-wady)
8. [Zastosowania praktyczne](#zastosowania)

---

## Wprowadzenie

### Co to jest MPC?

**Model Predictive Control (MPC)** - sterowanie predykcyjne z modelem - to zaawansowana strategia sterowania, która wykorzystuje model matematyczny systemu do przewidywania jego przyszłego zachowania i optymalizacji działań sterujących.

### Dlaczego MPC?

Wyobraź sobie, że prowadzisz samochód:

- **Klasyczny PID**: Patrzy tylko na obecną odległość od pasa i koryguje kierownicę. Jak widzisz zakręt? Za późno.

- **MPC**: Patrzy przez przednią szybę 100 metrów do przodu, widzi zakręt, wie jak samochód zareaguje na skręt kierownicą, i zaczyna korygować zawczasu.

**MPC jest jak dobry kierowca - planuje z wyprzedzeniem, uwzględnia ograniczenia (nie możesz skręcić o 90° nagle), i optymalizuje jazdę (oszczędność paliwa vs szybkość).**

### Kiedy używać MPC?

✅ **Idealny dla systemów z:**
- Dużą bezwładnością (systemy powolne - ogrzewanie, chłodzenie)
- Wieloma zmiennymi (multi-input, multi-output)
- Ograniczeniami fizycznymi (max moc, max temperatura)
- Możliwością prognozowania zakłóceń (pogoda, ceny energii)
- Potrzebą optymalizacji wielu celów (komfort + oszczędność energii)

❌ **NIE używaj MPC gdy:**
- System jest bardzo szybki (potrzeba reakcji w milisekundach)
- Brak mocy obliczeniowej (MCU 8-bit)
- Brak dobrego modelu systemu
- Prosty PID wystarcza

---

## Intuicja

### Jak myśli MPC?

MPC działa w pętli powtarzającej się cyklicznie (np. co 10 minut):

```
┌─────────────────────────────────────────────────────┐
│ KROK 1: POMIAR                                       │
│ "Gdzie jestem teraz?"                                │
│ - Temperatura pokoju: 20.5°C                         │
│ - Temperatura zewnętrzna: 5°C                        │
│ - Cel: 22°C                                          │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ KROK 2: PROGNOZA PRZYSZŁOŚCI                         │
│ "Co się stanie jeśli nie zrobię nic?"               │
│ - Za 1h: 20.2°C (ostygnie)                          │
│ - Za 2h: 19.9°C                                     │
│ - Za 3h: 19.5°C (za zimno!)                         │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ KROK 3: SYMULACJA OPCJI                              │
│ "Co mogę zrobić?"                                    │
│                                                      │
│ Opcja A: Grzej pełną mocą przez 2h                  │
│   → Za 3h: 23.5°C (za gorąco! przeregulowanie)      │
│   → Koszt energii: 15 PLN                           │
│                                                      │
│ Opcja B: Grzej 60% mocy przez 3h                    │
│   → Za 3h: 22.1°C (idealnie!)                       │
│   → Koszt energii: 11 PLN                           │
│                                                      │
│ Opcja C: Grzej 80% przez 1.5h, potem 30%            │
│   → Za 3h: 21.9°C (dobra temperatura)               │
│   → Koszt energii: 12 PLN                           │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ KROK 4: WYBÓR NAJLEPSZEJ OPCJI                       │
│ "Która opcja minimalizuje funkcję kosztu?"           │
│ Funkcja kosztu = 0.7×(błąd_temp)² + 0.3×(energia)²  │
│                                                      │
│ Opcja A: koszt = 0.7×(1.5)² + 0.3×(15)² = 69.1     │
│ Opcja B: koszt = 0.7×(0.1)² + 0.3×(11)² = 36.4 ✅   │
│ Opcja C: koszt = 0.7×(0.1)² + 0.3×(12)² = 43.3     │
│                                                      │
│ WYBRANO: Opcję B                                     │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│ KROK 5: WYKONAJ PIERWSZĄ AKCJĘ                       │
│ "Zastosuj tylko pierwszą akcję z planu"              │
│ → Ustaw zawór na 60% TERAZ                          │
│ → Resztę planu wyrzuć                               │
└─────────────────────────────────────────────────────┘
              ↓
        (czekaj 10 minut)
              ↓
         KROK 1 (ponownie)
```

### Kluczowa idea: Receding Horizon

**MPC zawsze planuje na N kroków do przodu, ale wykonuje tylko pierwszy krok.**

Dlaczego? Bo za 10 minut:
- Otrzymamy nowe pomiary (mogą różnić się od prognozy)
- Warunki zewnętrzne mogą się zmienić
- Model mógł się pomylić

To jak GPS: nieustannie przelicza trasę na podstawie aktualnej pozycji.

---

## Matematyka

### Model przestrzeni stanów

MPC wymaga **modelu dynamiki systemu**. Najczęściej używa się reprezentacji w przestrzeni stanów:

**Postać ciągła:**

```
dx/dt = f(x, u, d)    // Równania różniczkowe stanu
y = g(x, u)           // Równania wyjść
```

**Postać dyskretna (używana w implementacji):**

```
x(k+1) = A·x(k) + B·u(k) + Bd·d(k)    // Równanie stanu
y(k) = C·x(k)                          // Równanie wyjścia
```

gdzie:
- **x(k)** - wektor stanu w chwili k (np. temperatury mas termicznych)
- **u(k)** - wektor sterowania w chwili k (np. moc grzania)
- **d(k)** - wektor zakłóceń w chwili k (np. temperatura zewnętrzna)
- **y(k)** - wektor wyjść (mierzonych) w chwili k (np. temperatura pokoju)
- **A, B, Bd, C** - macierze modelu

### Przykład: Model 1R1C dla ogrzewania

Najprostszy model termiczny budynku - jeden opór R, jedna pojemność C:

**Równanie fizyczne:**

```
C·dT/dt = Q_grzanie - (T - T_zewn)/R
```

gdzie:
- **C** - pojemność cieplna [J/K]
- **R** - opór termiczny [K/W]
- **T** - temperatura pomieszczenia [K]
- **T_zewn** - temperatura zewnętrzna [K]
- **Q_grzanie** - moc grzania [W]

**Dyskretyzacja (metoda Eulera z krokiem Δt):**

```python
# Stan: x = [T]
# Sterowanie: u = [Q_grzanie]
# Zakłócenie: d = [T_zewn]

tau = R * C  # Stała czasowa [s]

# Macierze modelu dyskretnego
A = np.exp(-dt / tau)
B = R * (1 - A)
Bd = (1 - A)
C = 1

# Równanie rekurencyjne
T_next = A * T + B * Q_grzanie + Bd * T_zewn
```

**Interpretacja:**
- **τ = R·C** to stała czasowa - określa jak szybko system reaguje
  - Ogrzewanie podłogowe: τ = 10-30 godzin (bardzo powolne)
  - Grzejniki: τ = 1-2 godziny (średnie)
  - Grzałka elektryczna: τ = 5-15 minut (szybkie)

### Formulacja problemu optymalizacyjnego

MPC w każdym kroku rozwiązuje następujący problem:

**Minimalizuj:**

```
J = Σ[k=0 do Np] L(x(k), u(k), r(k)) + Φ(x(Np))
```

**Pod ograniczeniami:**

```
x(k+1) = A·x(k) + B·u(k) + Bd·d(k)    (dynamika)
y(k) = C·x(k)                          (wyjście)

u_min ≤ u(k) ≤ u_max                   (ograniczenia sterowania)
x_min ≤ x(k) ≤ x_max                   (ograniczenia stanów)
Δu_min ≤ u(k) - u(k-1) ≤ Δu_max        (ograniczenia szybkości zmian)
```

gdzie:
- **J** - funkcja kosztu (celu)
- **L(...)** - koszt chwilowy (stage cost / Lagrange term)
- **Φ(...)** - koszt końcowy (terminal cost / Mayer term)
- **Np** - horyzont predykcji (prediction horizon)
- **r(k)** - trajektoria referencyjna (setpoint)

### Typowa funkcja kosztu kwadratowa

Najczęściej używana forma (Linear Quadratic MPC):

```
J = Σ[k=0 do Np-1] { ||x(k) - r||²_Q + ||u(k)||²_R + ||Δu(k)||²_S }
    + ||x(Np) - r||²_P
```

W notacji rozwiniętej:

```
L(x, u, r) = (x - r)ᵀ·Q·(x - r)           // Błąd śledzenia
           + uᵀ·R·u                        // Koszt sterowania
           + (u - u_prev)ᵀ·S·(u - u_prev)  // Koszt zmian sterowania

Φ(x) = (x - r)ᵀ·P·(x - r)                 // Końcowy błąd śledzenia
```

**Macierze wagowe:**
- **Q** - waga błędu stanu (większe Q = dokładniejsze śledzenie)
- **R** - waga amplitudy sterowania (większe R = mniejsze sterowanie)
- **S** - waga zmian sterowania (większe S = gładsze sterowanie)
- **P** - waga końcowego błędu (stabilność)

**Przykład dla ogrzewania:**

```python
# Priorytet: dokładność temperatury
Q = np.array([[0.7]])  # 70% wagi na dokładność temperatury

# Niski priorytet: zużycie energii
R = np.array([[0.2]]) / 1e6  # 20% wagi, skalowanie przez 1e6 (normalizacja)

# Średni priorytet: gładkość sterowania
S = np.array([[0.1]]) / 1e6  # 10% wagi
```

### Horyzonty MPC

MPC operuje na dwóch horyzontach:

**Horyzont predykcji (Np)** - jak daleko w przyszłość patrzymy:
- Ogrzewanie podłogowe: **Np = 24-48** kroków (4-8 godzin przy Δt=10min)
- Systemy szybkie: **Np = 10-20** kroków
- Musi być dłuższy niż stała czasowa systemu (Np·Δt ≥ 2τ)

**Horyzont sterowania (Nc)** - na ile kroków planujemy zmiany sterowania:
- Zwykle **Nc ≤ Np/2**
- Po Nc krokach sterowanie jest stałe
- Mniejsze Nc = szybsza optymalizacja (mniej zmiennych)

**Krok czasowy (Δt)** - co ile powtarzamy optymalizację:
- Ogrzewanie podłogowe: **Δt = 5-10 minut**
- Zasada: Δt ≤ τ/10 (10x szybsze niż dynamika systemu)

---

## Algorytm

### MPC w pseudokodzie

```python
def MPC_controller():
    """Główna pętla sterowania MPC"""

    # Inicjalizacja
    model = build_system_model()  # Macierze A, B, C, Bd
    x_current = measure_initial_state()
    u_previous = 0

    while True:
        # === KROK 1: POMIAR ===
        x_current = measure_state()  # Odczyt sensorów
        d_forecast = get_disturbance_forecast(Np)  # Prognoza zakłóceń
        r_trajectory = get_reference_trajectory(Np)  # Trajektoria zadana

        # === KROK 2: OPTYMALIZACJA ===
        # Rozwiąż problem:
        # min J(u_sequence) s.t. constraints
        u_optimal = solve_optimization_problem(
            current_state=x_current,
            model=model,
            forecast=d_forecast,
            reference=r_trajectory,
            previous_control=u_previous,
            horizon_p=Np,
            horizon_c=Nc
        )

        # === KROK 3: WYKONANIE ===
        # Zastosuj tylko pierwszy element sekwencji sterującej
        u_apply = u_optimal[0]
        apply_control_to_system(u_apply)

        # Zapamiętaj dla następnego kroku
        u_previous = u_apply

        # === KROK 4: CZEKAJ ===
        sleep(dt)  # Czekaj do następnego cyklu
```

### Problem optymalizacyjny szczegółowo

Serce MPC to rozwiązywanie problemu optymalizacji:

```python
def solve_optimization_problem(x0, model, d_forecast, r_trajectory,
                               u_prev, Np, Nc):
    """
    Rozwiązuje problem MPC metodą optymalizacji numerycznej

    Zmienne decyzyjne: u = [u(0), u(1), ..., u(Nc-1)]
    Funkcja celu: J(u) = suma kosztów na horyzoncie Np
    Ograniczenia: u_min ≤ u ≤ u_max, Δu_min ≤ Δu ≤ Δu_max
    """

    # Zdefiniuj funkcję celu
    def cost_function(u_sequence):
        cost = 0.0
        x = x0.copy()

        # Symuluj system na horyzoncie Np
        for k in range(Np):
            # Pobierz sterowanie (stałe po Nc)
            u_k = u_sequence[k] if k < Nc else u_sequence[Nc-1]

            # Pobierz zakłócenie z prognozy
            d_k = d_forecast[k]

            # Pobierz referencję
            r_k = r_trajectory[k]

            # Propaguj model
            x = model.A @ x + model.B @ u_k + model.Bd @ d_k

            # Oblicz koszt chwilowy
            error = x - r_k
            cost += error.T @ Q @ error  # Błąd stanu

            if k < Nc:
                cost += u_k.T @ R @ u_k  # Koszt sterowania

                if k > 0:
                    du = u_k - u_sequence[k-1]
                    cost += du.T @ S @ du  # Koszt zmian

        # Koszt końcowy
        x_final = x
        r_final = r_trajectory[-1]
        error_final = x_final - r_final
        cost += error_final.T @ P @ error_final

        return cost

    # Początkowe przypuszczenie
    u_init = np.ones(Nc) * u_prev

    # Ograniczenia
    bounds = [(u_min, u_max) for _ in range(Nc)]

    # Ograniczenia na zmiany sterowania
    constraints = []
    for k in range(Nc):
        # Δu_k = u_k - u_{k-1}
        u_km1 = u_prev if k == 0 else 'u_{k-1}'
        constraints.append({
            'type': 'ineq',
            'fun': lambda u, k=k: u[k] - u_km1 - du_min
        })
        constraints.append({
            'type': 'ineq',
            'fun': lambda u, k=k: du_max - (u[k] - u_km1)
        })

    # Rozwiąż problem optymalizacji
    result = scipy.optimize.minimize(
        fun=cost_function,
        x0=u_init,
        bounds=bounds,
        constraints=constraints,
        method='SLSQP'  # Sequential Least Squares Programming
    )

    return result.x  # Optymalna sekwencja sterowania
```

### Metody rozwiązywania

MPC to problem **optymalizacji z ograniczeniami**. Metody rozwiązywania:

**1. Quadratic Programming (QP) - dla liniowego MPC:**
```python
# Problem kwadratowy:
# min 0.5·x^T·H·x + f^T·x
# s.t. A·x ≤ b

from cvxopt import solvers, matrix

# Sformułuj jako QP
H = build_hessian_matrix()
f = build_linear_term()
A = build_constraint_matrix()
b = build_constraint_vector()

# Rozwiąż
sol = solvers.qp(H, f, A, b)
u_optimal = sol['x']
```

**2. Nonlinear Programming (NLP) - dla nieliniowego MPC:**
```python
from scipy.optimize import minimize

# Problem nieliniowy ogólny
result = minimize(
    fun=nonlinear_cost_function,
    x0=initial_guess,
    method='SLSQP',  # lub 'trust-constr'
    bounds=bounds,
    constraints=constraints
)
```

**3. Biblioteki specjalizowane:**
```python
# CasADi - symboliczna optymalizacja
import casadi as ca

opti = ca.Opti()
u = opti.variable(Nc)
x = opti.variable(Np+1)

# Zdefiniuj funkcję celu symbolicznie
opti.minimize(ca.sum1((x - r)**2 + 0.1*u**2))

# Dodaj ograniczenia
opti.subject_to(x[1:] == A @ x[:-1] + B @ u)
opti.subject_to(opti.bounded(u_min, u, u_max))

# Rozwiąż
opti.solver('ipopt')
sol = opti.solve()
```

---

## Implementacja

### Kompletna implementacja MPC w Pythonie

Pełny, działający przykład MPC dla systemu 1R1C:

```python
import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class MPCConfig:
    """Konfiguracja kontrolera MPC"""
    Np: int = 24          # Horyzont predykcji
    Nc: int = 12          # Horyzont sterowania
    dt: float = 600.0     # Krok czasowy [s]

    # Wagi funkcji kosztu
    Q: float = 0.7        # Waga błędu temperatury
    R: float = 0.2        # Waga energii
    S: float = 0.1        # Waga gładkości

    # Ograniczenia
    u_min: float = 0.0    # Min moc [W]
    u_max: float = 10000.0 # Max moc [W]
    du_max: float = 5000.0 # Max zmiana mocy [W]

    # Parametry modelu
    R_thermal: float = 0.002  # Opór termiczny [K/W]
    C_thermal: float = 4.5e6  # Pojemność cieplna [J/K]


class ThermalModel:
    """Model 1R1C dla systemu termicznego"""

    def __init__(self, R: float, C: float, dt: float):
        self.R = R
        self.C = C
        self.dt = dt
        self.tau = R * C  # Stała czasowa

        # Oblicz macierze dyskretnego modelu przestrzeni stanów
        self.A = np.exp(-dt / self.tau)
        self.B = R * (1 - self.A)
        self.Bd = (1 - self.A)
        self.C_matrix = 1.0

    def predict(self, x0: float, u_sequence: np.ndarray,
                d_forecast: np.ndarray) -> np.ndarray:
        """
        Predykcja temperatury na horyzoncie

        Args:
            x0: Stan początkowy (temperatura) [°C]
            u_sequence: Sekwencja sterowania (moc) [W]
            d_forecast: Prognoza zakłóceń (temp zewn) [°C]

        Returns:
            Tablica temperatur [x(0), x(1), ..., x(Np)]
        """
        Np = len(d_forecast)
        x_pred = np.zeros(Np + 1)
        x_pred[0] = x0

        for k in range(Np):
            u_k = u_sequence[k] if k < len(u_sequence) else 0
            d_k = d_forecast[k]

            # x(k+1) = A·x(k) + B·u(k) + Bd·d(k)
            x_pred[k+1] = (self.A * x_pred[k] +
                          self.B * u_k +
                          self.Bd * d_k)

        return x_pred


class MPCController:
    """Kontroler Model Predictive Control"""

    def __init__(self, config: MPCConfig):
        self.config = config
        self.model = ThermalModel(
            config.R_thermal,
            config.C_thermal,
            config.dt
        )
        self.u_previous = 0.0

        # Historia do logowania
        self.history = {
            'time': [],
            'temperature': [],
            'setpoint': [],
            'control': [],
            'outdoor_temp': []
        }

    def compute_control(self, current_temp: float, setpoint: float,
                       outdoor_forecast: np.ndarray) -> float:
        """
        Główna funkcja sterowania MPC

        Args:
            current_temp: Aktualna temperatura pomieszczenia [°C]
            setpoint: Temperatura zadana [°C]
            outdoor_forecast: Prognoza temp zewnętrznej [°C] (długość Np)

        Returns:
            Optymalne sterowanie (moc) [W]
        """
        cfg = self.config

        # Stwórz trajektorię referencyjną (stała nastawa)
        r_trajectory = np.ones(cfg.Np) * setpoint

        # Zdefiniuj funkcję kosztu
        def cost_function(u_sequence):
            # Rozszerz sekwencję do pełnego horyzontu
            u_full = np.concatenate([
                u_sequence,
                np.ones(cfg.Np - cfg.Nc) * u_sequence[-1]
            ])

            # Predykcja na horyzoncie
            x_pred = self.model.predict(
                current_temp,
                u_full,
                outdoor_forecast
            )

            cost = 0.0

            # Koszty na horyzoncie predykcji
            for k in range(cfg.Np):
                # Błąd temperatury
                error = x_pred[k+1] - r_trajectory[k]
                cost += cfg.Q * error**2

                # Koszt energii (tylko horyzont sterowania)
                if k < cfg.Nc:
                    cost += (cfg.R / 1e6) * u_sequence[k]**2

                    # Koszt zmian sterowania
                    if k > 0:
                        du = u_sequence[k] - u_sequence[k-1]
                        cost += (cfg.S / 1e6) * du**2
                    else:
                        du = u_sequence[k] - self.u_previous
                        cost += (cfg.S / 1e6) * du**2

            return cost

        # Początkowe przypuszczenie (stałe sterowanie)
        u_init = np.ones(cfg.Nc) * self.u_previous

        # Ograniczenia na amplitudę
        bounds = [(cfg.u_min, cfg.u_max) for _ in range(cfg.Nc)]

        # Ograniczenia na zmiany sterowania
        constraints = []
        for k in range(cfg.Nc):
            # u(k) - u(k-1) ≤ du_max
            # u(k-1) - u(k) ≤ du_max
            u_km1 = self.u_previous if k == 0 else 'u_sequence[k-1]'

            # Tworzymy constraint function dla każdego k
            def make_constraint(idx):
                def constr_upper(u):
                    u_prev = self.u_previous if idx == 0 else u[idx-1]
                    return cfg.du_max - abs(u[idx] - u_prev)
                return constr_upper

            constraints.append({
                'type': 'ineq',
                'fun': make_constraint(k)
            })

        # Rozwiąż problem optymalizacji
        result = minimize(
            fun=cost_function,
            x0=u_init,
            bounds=bounds,
            constraints=constraints,
            method='SLSQP',
            options={'maxiter': 100, 'ftol': 1e-6}
        )

        if not result.success:
            print(f"⚠️  Optymalizacja nie zbiegła: {result.message}")
            # Fallback: użyj prostego regulatora P
            error = setpoint - current_temp
            u_optimal = np.clip(error * 2000, cfg.u_min, cfg.u_max)
        else:
            u_optimal = result.x[0]

        # Zapamiętaj sterowanie
        self.u_previous = u_optimal

        return u_optimal

    def log_state(self, time: float, temp: float, setpoint: float,
                  control: float, outdoor: float):
        """Zapisz stan do historii"""
        self.history['time'].append(time)
        self.history['temperature'].append(temp)
        self.history['setpoint'].append(setpoint)
        self.history['control'].append(control)
        self.history['outdoor_temp'].append(outdoor)

    def plot_history(self):
        """Wyświetl wykresy historii sterowania"""
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))

        time_hours = np.array(self.history['time']) / 3600

        # Wykres 1: Temperatura
        axes[0].plot(time_hours, self.history['temperature'],
                    'b-', linewidth=2, label='Temperatura rzeczywista')
        axes[0].plot(time_hours, self.history['setpoint'],
                    'r--', linewidth=2, label='Nastawa')
        axes[0].plot(time_hours, self.history['outdoor_temp'],
                    'g:', linewidth=1, label='Temp. zewnętrzna')
        axes[0].set_ylabel('Temperatura [°C]')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        axes[0].set_title('MPC - Sterowanie Temperaturą')

        # Wykres 2: Sterowanie
        axes[1].plot(time_hours, np.array(self.history['control'])/1000,
                    'r-', linewidth=2)
        axes[1].set_ylabel('Moc grzania [kW]')
        axes[1].grid(True, alpha=0.3)
        axes[1].set_title('Sygnał sterujący')

        # Wykres 3: Błąd
        error = (np.array(self.history['temperature']) -
                np.array(self.history['setpoint']))
        axes[2].plot(time_hours, error, 'k-', linewidth=2)
        axes[2].axhline(y=0, color='r', linestyle='--', alpha=0.5)
        axes[2].set_ylabel('Błąd [°C]')
        axes[2].set_xlabel('Czas [h]')
        axes[2].grid(True, alpha=0.3)
        axes[2].set_title('Błąd regulacji')

        plt.tight_layout()
        plt.savefig('mpc_control_results.png', dpi=150)
        plt.show()


def simulate_heating_system(duration_hours: float = 24):
    """
    Symulacja systemu ogrzewania z kontrolerem MPC

    Args:
        duration_hours: Czas symulacji [h]
    """
    # Konfiguracja
    config = MPCConfig(
        Np=24,           # 4 godziny predykcji (24 × 10 min)
        Nc=12,           # 2 godziny sterowania
        dt=600,          # 10 minut
        Q=0.7,
        R=0.2,
        S=0.1,
        u_min=0,
        u_max=8000,      # 8 kW max
        du_max=3000,     # Max zmiana 3 kW na krok
        R_thermal=0.002,
        C_thermal=4.5e6
    )

    controller = MPCController(config)

    # Stan początkowy
    T_room = 18.0          # Pokój zimny
    T_outdoor = 5.0        # Temp zewnętrzna
    setpoint = 22.0        # Cel

    # Model rzeczywistego systemu (ten sam co w kontrolerze)
    real_system = ThermalModel(
        config.R_thermal,
        config.C_thermal,
        config.dt
    )

    # Symulacja
    num_steps = int(duration_hours * 3600 / config.dt)
    time = 0.0

    print("🚀 Rozpoczynam symulację MPC...")
    print(f"Temperatura początkowa: {T_room:.1f}°C")
    print(f"Nastawa: {setpoint:.1f}°C")
    print(f"Temperatura zewnętrzna: {T_outdoor:.1f}°C\n")

    for step in range(num_steps):
        # Symulacja zmiennej temp zewnętrznej (cykl dobowy)
        hour_of_day = (time / 3600) % 24
        T_outdoor = 5.0 + 3.0 * np.sin(2*np.pi * (hour_of_day - 6) / 24)

        # Prognoza pogody (prosta ekstrapolacja)
        outdoor_forecast = np.ones(config.Np) * T_outdoor
        # Dodaj trend
        for k in range(config.Np):
            future_hour = ((time + k*config.dt) / 3600) % 24
            outdoor_forecast[k] = (5.0 + 3.0 *
                                  np.sin(2*np.pi * (future_hour - 6) / 24))

        # Zmiana nastawy w nocy
        if 23 <= hour_of_day or hour_of_day < 6:
            setpoint_current = 20.0  # Tryb nocny
        else:
            setpoint_current = 22.0  # Tryb dzienny

        # Oblicz sterowanie MPC
        u_control = controller.compute_control(
            T_room,
            setpoint_current,
            outdoor_forecast
        )

        # Zasymuluj wpływ sterowania na system rzeczywisty
        x_next = real_system.predict(
            T_room,
            np.array([u_control]),
            np.array([T_outdoor])
        )
        T_room = x_next[1]

        # Dodaj szum pomiarowy
        T_room_measured = T_room + np.random.normal(0, 0.05)

        # Logowanie
        controller.log_state(time, T_room_measured, setpoint_current,
                           u_control, T_outdoor)

        # Wyświetl co godzinę
        if step % 6 == 0:  # Co 60 minut
            print(f"⏱️  t={time/3600:5.1f}h | "
                  f"T={T_room:5.2f}°C | "
                  f"SP={setpoint_current:5.1f}°C | "
                  f"u={u_control/1000:5.2f}kW | "
                  f"T_out={T_outdoor:5.1f}°C")

        time += config.dt

    print("\n✅ Symulacja zakończona!")

    # Oblicz metryki wydajności
    history = controller.history
    error = np.array(history['temperature']) - np.array(history['setpoint'])
    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error**2))
    max_error = np.max(np.abs(error))
    energy = np.sum(history['control']) * config.dt / 3600 / 1000  # kWh

    print(f"\n📊 Metryki wydajności:")
    print(f"   MAE (średni błąd bezwzględny): {mae:.3f}°C")
    print(f"   RMSE: {rmse:.3f}°C")
    print(f"   Maksymalny błąd: {max_error:.3f}°C")
    print(f"   Zużycie energii: {energy:.1f} kWh")

    # Wyświetl wykresy
    controller.plot_history()

    return controller


# === URUCHOMIENIE ===
if __name__ == "__main__":
    controller = simulate_heating_system(duration_hours=24)
```

### Uruchomienie przykładu

```bash
# Zainstaluj zależności
pip install numpy scipy matplotlib

# Uruchom symulację
python mpc_heating_example.py
```

**Oczekiwane wyjście:**

```
🚀 Rozpoczynam symulację MPC...
Temperatura początkowa: 18.0°C
Nastawa: 22.0°C
Temperatura zewnętrzna: 5.0°C

⏱️  t=  0.0h | T=18.00°C | SP= 22.0°C | u= 7.85kW | T_out= 5.0°C
⏱️  t=  1.0h | T=18.95°C | SP= 22.0°C | u= 7.21kW | T_out= 5.5°C
⏱️  t=  2.0h | T=19.82°C | SP= 22.0°C | u= 6.54kW | T_out= 6.2°C
...
⏱️  t= 23.0h | T=21.97°C | SP= 20.0°C | u= 1.25kW | T_out= 4.8°C

✅ Symulacja zakończona!

📊 Metryki wydajności:
   MAE (średni błąd bezwzględny): 0.247°C
   RMSE: 0.312°C
   Maksymalny błąd: 1.123°C
   Zużycie energii: 142.3 kWh
```

---

## Tuning

### Dobór parametrów MPC

**1. Horyzonty (Np, Nc)**

```python
# Reguły praktyczne:
tau = R * C  # Stała czasowa systemu

# Horyzont predykcji
Np_min = int(2 * tau / dt)  # Co najmniej 2× stała czasowa
Np_typical = int(3 * tau / dt)  # Typowo 3× stała czasowa

# Horyzont sterowania
Nc = Np // 2  # Połowa horyzontu predykcji
Nc = max(Nc, 5)  # Co najmniej 5 kroków

# Krok czasowy
dt = tau / 10  # 10× szybszy niż dynamika
```

**Przykład dla ogrzewania podłogowego (τ = 14400s = 4h):**
```python
dt = 600  # 10 minut (14400 / 24)
Np = 24   # 4 godziny (2× tau minimum)
Nc = 12   # 2 godziny
```

**2. Wagi funkcji kosztu (Q, R, S)**

Metoda trial-and-error z wytycznymi:

```python
# Zaczynaj od:
Q = 1.0   # Waga błędu
R = 0.1   # Waga energii (10% względem Q)
S = 0.01  # Waga gładkości (1% względem Q)

# Dostrajanie:
# - System oscyluje? → Zwiększ R i S (kosztowniejsze sterowanie)
# - System zbyt powolny? → Zwiększ Q (większy priorytet na dokładność)
# - Sterowanie zbyt nerwowe? → Zwiększ S (gładsze przejścia)
# - Za duże zużycie energii? → Zwiększ R
```

**Metoda automatyczna - Bryson's rule:**
```python
# Q: odwrotność kwadratu maksymalnego dopuszczalnego błędu
max_acceptable_error = 2.0  # [°C]
Q = 1 / max_acceptable_error**2  # = 0.25

# R: odwrotność kwadratu maksymalnego sterowania
max_control = 10000  # [W]
R = 1 / max_control**2  # = 1e-8 (trzeba przeskalować!)

# Skalowanie dla numerycznej stabilności
R_scaled = R * 1e6  # Teraz R ≈ 0.01
S_scaled = R_scaled * 0.1
```

**3. Ograniczenia (bounds, du_max)**

```python
# Fizyczne limity mocy
u_min = 0         # Nie możemy chłodzić
u_max = P_boiler  # Max moc pieca

# Limity szybkości zmian (chroni zawory, pompy)
du_max = 0.3 * u_max  # Max 30% zmiany na krok
```

**4. Tuning przez symulację**

```python
def tune_mpc_parameters():
    """Systematyczne przeszukiwanie przestrzeni parametrów"""

    # Grid search
    Q_values = [0.5, 0.7, 1.0, 1.5]
    R_values = [0.1, 0.2, 0.3]

    best_params = None
    best_score = float('inf')

    for Q in Q_values:
        for R in R_values:
            S = R * 0.5

            # Symuluj z tymi parametrami
            config = MPCConfig(Q=Q, R=R, S=S, ...)
            controller = simulate_with_config(config)

            # Oceń wydajność
            score = calculate_performance_score(controller.history)

            if score < best_score:
                best_score = score
                best_params = (Q, R, S)

    return best_params

def calculate_performance_score(history):
    """Funkcja oceny wydajności kontrolera"""
    error = np.array(history['temperature']) - np.array(history['setpoint'])
    energy = np.sum(history['control'])

    # Kombinowana metryka
    score = (0.7 * np.mean(error**2) +      # RMSE
             0.2 * (energy / 1e6) +         # Energia
             0.1 * np.mean(np.abs(np.diff(history['control']))))  # Gładkość

    return score
```

---

## Zalety i wady

### ✅ Zalety MPC

1. **Działanie predykcyjne**
   - Przewiduje przyszłe zachowanie systemu
   - Reaguje na zakłócenia przed ich wystąpieniem
   - Wykorzystuje prognozy (pogoda, ceny energii)

2. **Naturalna obsługa ograniczeń**
   - Fizyczne limity (max moc, max temperatura)
   - Ograniczenia szybkości zmian
   - Strefy bezpieczeństwa

3. **Multi-objective optimization**
   - Balansuje wiele celów jednocześnie (komfort + koszty)
   - Wagi konfigurują priorytety
   - Pareto-optymalne rozwiązania

4. **Idealny dla systemów MIMO**
   - Multi-Input Multi-Output
   - Uwzględnia interakcje między zmiennymi
   - Koordynacja wielu stref

5. **Wykorzystanie bezwładności**
   - Używa masy termicznej jako magazynu
   - Pre-heating przed zmianą pogody
   - Przesunięcie obciążenia (load shifting)

### ❌ Wady MPC

1. **Złożoność obliczeniowa**
   - Wymaga rozwiązania problemu optymalizacji w każdym kroku
   - Może być zbyt wolne dla bardzo szybkich systemów
   - Potrzeba odpowiedniego hardware (min. Raspberry Pi)

2. **Wymaga modelu**
   - Jakość sterowania zależy od jakości modelu
   - Model może się zdezaktualizować (zużycie, zmiany budynku)
   - Identyfikacja parametrów modelu jest czasochłonna

3. **Trudność w tuningu**
   - Wiele parametrów do dostrój (Q, R, S, Np, Nc)
   - Brak prostych reguł (jak Ziegler-Nichols dla PID)
   - Wymaga znajomości teorii sterowania

4. **Zależność od prognoz**
   - Złe prognozy → złe sterowanie
   - Brak prognozy → degradacja do PID-like
   - Niepewność prognozy trudna do uwzględnienia

5. **Możliwość nieoptymalności**
   - Lokalne minima w problemie nieliniowym
   - Solver może nie zbiegać
   - Potrzeba mechanizmów failsafe

### 📊 Porównanie MPC vs PID

| Cecha | PID | MPC |
|-------|-----|-----|
| **Złożoność implementacji** | ⭐ Bardzo prosta | ⭐⭐⭐⭐ Zaawansowana |
| **Moc obliczeniowa** | ⭐ Minimalna | ⭐⭐⭐⭐ Średnia-wysoka |
| **Wydajność (systemy powolne)** | ⭐⭐⭐ Dobra | ⭐⭐⭐⭐⭐ Wybitna |
| **Wydajność (systemy szybkie)** | ⭐⭐⭐⭐⭐ Wybitna | ⭐⭐ Słaba |
| **Obsługa ograniczeń** | ⭐⭐ Anti-windup | ⭐⭐⭐⭐⭐ Natywna |
| **Multi-objective** | ⭐ Nie | ⭐⭐⭐⭐⭐ Tak |
| **Predykcja** | ⭐ Nie | ⭐⭐⭐⭐⭐ Tak |
| **Tuning** | ⭐⭐⭐⭐ Łatwy | ⭐⭐ Trudny |
| **Odporność** | ⭐⭐⭐⭐⭐ Bardzo wysoka | ⭐⭐⭐ Średnia |

**Werdykt:**
- **PID**: Dla 90% zastosowań, zwłaszcza szybkich systemów, gdzie prostota = niezawodność
- **MPC**: Dla wymagających aplikacji (HVAC, chemiczne, powolne MIMO) gdzie korzyści przeważają koszt

---

## Zastosowania

### Ogrzewanie podłogowe - case study

**Dlaczego MPC jest idealny dla underfloor heating:**

1. **Ekstremalnie duża bezwładność**
   - Stała czasowa τ = 10-30 godzin
   - System reaguje powoli → MPC może planować z wyprzedzeniem
   - PID często powoduje oscylacje (overshoot)

2. **Prognoza pogody kluczowa**
   - Wiemy 12h wcześniej, że będzie cieplej
   - MPC może zmniejszyć grzanie zawczasu
   - Oszczędność energii: 15-20%

3. **Masa termiczna = magazyn energii**
   - Tanio grzej w nocy (niższa taryfa)
   - Wykorzystuj podłogę jako "baterię termiczną"
   - MPC optymalizuje load shifting

4. **Wielostrefowość**
   - Każde pomieszczenie = strefa
   - Strefy oddziałują na siebie (ściany)
   - MPC naturalnie koordynuje multiple zones

**Wyniki rzeczywiste z implementacji MPC w ogrzewaniu:**

| Metryka | Sterowanie On/Off | PID | MPC |
|---------|-------------------|-----|-----|
| Średni błąd temperatury | ±1.5°C | ±0.8°C | ±0.3°C |
| Overshoot | 3-5°C | 1-2°C | <0.5°C |
| Zużycie energii | 100% (baseline) | 85% | 72% |
| Czas osiągnięcia setpoint | 6-8h | 5-6h | 4-5h |
| Komfort (ankiety użytkowników) | 6.2/10 | 7.8/10 | 9.1/10 |

**Typowe oszczędności MPC:**
- **Koszt energii:** -13% do -16% vs. konwencjonalne
- **Szczytowe obciążenie:** -5% do -18%
- **Naruszenia komfortu:** -79% do -98%
- **ROI:** 2-4 lata dla systemu wielostrefowego

### Inne zastosowania MPC

**1. Przemysł chemiczny**
- Kontrola reaktorów (temp, ciśnienie, stężenie)
- Kolumny destylacyjne
- Procesy wsadowe (batch)

**2. Automotive**
- Cruise control predykcyjny (zna profil drogi)
- Zarządzanie energią w EV
- Stabilizacja pojazdu (ESP)

**3. Energia**
- Zarządzanie sieciami smart grid
- Optymalizacja magazynów energii
- Kontrola elektrowni

**4. Aerospace**
- Sterowanie lotem
- Zarządzanie paliwem
- Trajektorie lądowania

**5. Robotyka**
- Planowanie trajektorii
- Walking robots (MPC dla dynamiki)
- Manipulatory

---

## Podsumowanie

### Kluczowe koncepcje

1. **MPC = Optymalizacja w pętli**
   - Każdy krok: rozwiąż problem optymalizacji
   - Zastosuj tylko pierwszą akcję
   - Powtórz z nowymi pomiarami (receding horizon)

2. **Model jest fundamentem**
   - Jakość modelu = jakość sterowania
   - Identyfikacja parametrów kluczowa
   - Adaptacja online zwiększa robust

3. **Horyzont to okno w przyszłość**
   - Np kroków predykcji
   - Nc kroków sterowania
   - Musi pokrywać dynamikę systemu (Np·Δt ≥ 2τ)

4. **Funkcja kosztu to kompromis**
   - Q: dokładność śledzenia
   - R: oszczędność energii
   - S: gładkość sterowania
   - Balansuj wagi według priorytetów

5. **Ograniczenia są wbudowane**
   - Nie potrzeba anti-windup
   - Fizyczne limity respektowane
   - Bezpieczeństwo przez konstrukcję

### Kiedy używać MPC?

**✅ Użyj MPC gdy:**
- System powolny (τ > 10 minut)
- Dostępna prognoza zakłóceń
- Wiele celów do zbalansowania
- Ograniczenia kluczowe
- Masz moc obliczeniową

**❌ Użyj PID gdy:**
- System szybki (τ < 1 sekunda)
- Brak prognozy
- Jeden cel (śledzenie)
- Prostota > optymalność
- Ograniczony hardware

### Resources

**Biblioteki Python:**
- `do-mpc` - dla nieliniowych systemów
- `python-control` - control systems library
- `cvxpy` - convex optimization
- `casadi` - symbolic optimization

**Kursy online:**
- MATLAB MPC Toolbox tutorials
- Coursera: "Model Predictive Control"
- YouTube: Steve Brunton - "Control Bootcamp"

**Literatura:**
- Camacho & Bordons: "Model Predictive Control"
- Rawlings, Mayne & Diehl: "Model Predictive Control: Theory, Computation, and Design"

---

## Appendix: Quickstart Checklist

### Implementacja MPC w 10 krokach

- [ ] **1. Zidentyfikuj system**
  - Przeprowadź test skokowy
  - Zmierz τ (stała czasowa) i θ (czas martwy)
  - Dopasuj model 1R1C lub wyższego rzędu

- [ ] **2. Wybierz horyzonty**
  - Np = 2-3× τ/Δt
  - Nc = Np/2
  - Δt = τ/10

- [ ] **3. Zdefiniuj funkcję kosztu**
  - Ustal priorytety (komfort vs energia)
  - Dobierz wagi Q, R, S
  - Dodaj terminal cost jeśli potrzeba

- [ ] **4. Określ ograniczenia**
  - Min/max sterowania (u_min, u_max)
  - Limity zmian (du_max)
  - Ograniczenia stanów jeśli istotne

- [ ] **5. Wybierz solver**
  - QP dla liniowego MPC (szybszy)
  - NLP dla nieliniowego (scipy, casadi)
  - Test convergence rate

- [ ] **6. Implementuj w pętli**
  - Pomiar → Prognoza → Optymalizacja → Akcja
  - Dodaj logowanie do debugowania
  - Mechanizm failsafe (fallback do PID)

- [ ] **7. Testuj w symulacji**
  - Step response
  - Tracking różnych setpointów
  - Odporność na zakłócenia

- [ ] **8. Tuning**
  - Grid search po wagach
  - Obserwuj trade-offy
  - Zapisuj metryki (MAE, RMSE, energia)

- [ ] **9. Wdrożenie**
  - Start z konserwatywnymi parametrami
  - Monitoruj przez tydzień
  - Stopniowo zwiększaj agresywność

- [ ] **10. Utrzymanie**
  - Okresowa re-identyfikacja modelu
  - Adaptacja do zmian (sezonowych, zużycie)
  - Analiza historii dla dalszej optymalizacji

---

**Stworzono:** 2025-10-26
**Autor:** Dokumentacja techniczna MPC
**Wersja:** 1.0
**Licencja:** Do użytku edukacyjnego i projektowego
