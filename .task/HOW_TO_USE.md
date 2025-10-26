# Jak korzystać z systemu zarządzania zadaniami?

Ten dokument wyjaśnia jak pracować z plikami w katalogu `.task/`.

---

## 📁 Struktura plików

```
.task/
├── README.md                    # Przegląd projektu i wszystkich faz
├── PROJECT_STATUS.md            # Aktualny status (aktualizuj co tydzień!)
├── HOW_TO_USE.md               # Ten plik - instrukcja obsługi
│
├── phase-1-foundation.md        # Faza 1: Szczegółowe zadania
├── phase-2-thermal-model.md     # Faza 2: Szczegółowe zadania
├── phase-3-mpc-core.md          # Faza 3: Szczegółowe zadania
├── phase-4-advanced-features.md # Faza 4: Szczegółowe zadania
├── phase-5-cost-optimization.md # Faza 5: Szczegółowe zadania
├── phase-6-hacs-publication.md  # Faza 6: Szczegółowe zadania
│
├── backlog.md                   # Pomysły na przyszłość (post v1.0)
├── bugs.md                      # Lista znanych błędów
└── research.md                  # Notatki badawcze, eksperymenty
```

---

## 🚀 Quick Start

### 1. Rozpoczęcie pracy

```bash
# Otwórz aktualną fazę
cat .task/phase-1-foundation.md

# Lub w edytorze
code .task/phase-1-foundation.md
```

### 2. Wybierz zadanie

- Zadania oznaczone jako `- [ ]` są do zrobienia
- Wybierz zadanie z najwyższym priorytetem
- Sprawdź zależności (pole "Zależności")

### 3. Oznacz jako "w trakcie"

Zmień checkbox:
```markdown
- [ ] **T1.1.1:** Opis zadania    →    - [🟡] **T1.1.1:** Opis zadania
      ↑ do zrobienia                            ↑ w trakcie
```

### 4. Pracuj nad zadaniem

```bash
# Stwórz branch dla zadania
git checkout -b feature/T1.1.1-nazwa-zadania

# Commituj regularnie
git add .
git commit -m "feat(T1.1.1): opis zmian"
```

### 5. Oznacz jako ukończone

Po zakończeniu:
```markdown
- [🟡] **T1.1.1:** Opis zadania    →    - [x] **T1.1.1:** Opis zadania
       ↑ w trakcie                              ↑ ukończone
```

### 6. Aktualizuj status projektu

Co tydzień lub po ważnym milestone:

```bash
# Edytuj PROJECT_STATUS.md
code .task/PROJECT_STATUS.md

# Zaktualizuj:
# - Postęp fazy (% zadań ukończonych)
# - Metryki (LOC, coverage, etc.)
# - Kamienie milowe
# - Datę ostatniej aktualizacji
```

---

## 🏷️ Konwencje

### Statusy zadań (checkbox)

| Symbol | Status | Znaczenie |
|--------|--------|-----------|
| `- [ ]` | 🔴 Do zrobienia | Zadanie czeka |
| `- [🟡]` | 🟡 W trakcie | Pracujesz nad tym teraz |
| `- [x]` | 🟢 Ukończone | Zrobione, przetestowane |
| `- [⚠️]` | ⚠️ Zablokowane | Czeka na inną rzecz |
| `- [🔵]` | 🔵 Do weryfikacji | Gotowe, ale wymaga review |

### Priorytety

W nazwach zadań:

- **Wysoki** = musi być zrobione, blokuje inne zadania
- **Średni** = ważne, ale można przesunąć
- **Niski** = nice-to-have, zrób gdy będzie czas

### Nazewnictwo zadań

Format: `T[Faza].[Sekcja].[Numer]`

Przykłady:
- `T1.1.1` = Faza 1, Sekcja 1, Zadanie 1
- `T3.4.2` = Faza 3, Sekcja 4, Zadanie 2

### Commits

Używaj [Conventional Commits](https://www.conventionalcommits.org/):

```bash
feat(T1.1.1): add manifest.json with dependencies
fix(T2.3.2): correct RLS convergence issue
docs: update README with installation instructions
test: add unit tests for ThermalModel
refactor: simplify MPCController initialization
chore: update dependencies to latest versions
```

---

## 📊 Tracking progress

### Codziennie (Daily)

1. Oznacz zadania które zaczynasz (🟡)
2. Commituj zmiany z właściwym message
3. Oznacz zadania które kończysz (✅)

### Co tydzień (Weekly)

1. **Otwórz PROJECT_STATUS.md**
2. Zaktualizuj:
   - Postęp fazy (policz % ukończonych zadań)
   - Metryki kodu (LOC, coverage - z raportu testów)
   - Sekcję "Najbliższe kroki"
   - Datę ostatniej aktualizacji
3. **Review ukończonych zadań**
   - Czy wszystkie kryteria akceptacji spełnione?
   - Czy są testy?
   - Czy dokumentacja aktualna?

### Po zakończeniu fazy (Milestone)

1. Sprawdź czy wszystkie zadania z fazy ukończone
2. Uruchom pełne testy (unit + integration)
3. Zaktualizuj README.md (jeśli potrzeba)
4. Oznacz fazę jako "🟢 Zakończona" w PROJECT_STATUS.md
5. Stwórz tag git: `git tag v0.X.0` (X = numer fazy)

---

## 🐛 Zgłaszanie bugów

### Znalazłeś bug?

1. **Sprawdź czy już nie zgłoszony:**
   ```bash
   grep -r "nazwa-błędu" .task/bugs.md
   ```

2. **Dodaj do bugs.md:**
   ```markdown
   ### 🟠 High (lub inny priorytet)

   - [ ] **BUG-001:** Krótki opis problemu
     - **Priorytet:** 🟠 High
     - **Opis:** Szczegółowy opis co nie działa
     - **Kroki reprodukcji:**
       1. Zrób to
       2. Zrób tamto
       3. Obserwuj błąd
     - **Oczekiwane:** Co powinno się stać
     - **Rzeczywiste:** Co się dzieje
     - **Logowany:** 2025-10-26
     - **Przypisane:** (nazwa osoby lub "unassigned")
   ```

3. **Priorytetyzuj:**
   - 🔴 **Critical** - system nie działa, natychmiast fix
   - 🟠 **High** - poważny problem, fix w ciągu tygodnia
   - 🟡 **Medium** - uciążliwe, fix w ciągu miesiąca
   - 🟢 **Low** - kosmetyczne, fix gdy będzie czas

4. **Po naprawie:**
   ```markdown
   - [x] **BUG-001:** Krótki opis
     - **Naprawione w:** commit abc123, v0.1.1
     - **Fix:** Opis rozwiązania
   ```
   Przenieś do sekcji "Naprawione bugi"

---

## 💡 Dodawanie pomysłów

### Masz pomysł na nową funkcję?

1. **Dodaj do backlog.md:**
   ```markdown
   - [ ] 🔥 **Nazwa funkcji** (priorytet)
     - Opis czego potrzeba
     - Dlaczego przydatne
     - **Effort:** High/Medium/Low (szacunek pracy)
   ```

2. **Gdy zaczniesz implementację:**
   - Stwórz nowe zadanie w odpowiedniej fazie
   - Lub dodaj jako nową sekcję
   - Przenieś z backlogu do aktywnych zadań

---

## 📝 Research notes

### Eksperymenty i badania

Gdy przeprowadzasz eksperyment lub test:

1. **Dodaj do research.md:**
   ```markdown
   ### Eksperyment X: Nazwa

   **Cel:** Co chcesz sprawdzić?

   **Setup:**
   - Dane: jakie
   - Metoda: jak testujesz
   - Metryki: co mierzysz

   **Hipoteza:** Co oczekujesz?

   **Wyniki:** (uzupełnij po eksperymencie)

   **Wnioski:** (co się nauczyłeś)
   ```

2. **Dokumentuj wszystko:**
   - Parametry eksperymentu
   - Wyniki (liczby, wykresy)
   - Wnioski i next steps

3. **Linkuj do commitów:**
   Jeśli eksperyment wymaga kodu, zlinkuj:
   ```markdown
   **Kod:** Zobacz branch `experiment/X-nazwa` commit abc123
   ```

---

## 🔄 Workflow przykładowy

### Typowy dzień pracy:

```bash
# 1. Rano - sprawdź status
cat .task/PROJECT_STATUS.md

# 2. Wybierz zadanie z aktualnej fazy
cat .task/phase-1-foundation.md

# 3. Oznacz jako "w trakcie" w pliku
# (edytuj checkbox na 🟡)

# 4. Stwórz branch
git checkout -b feature/T1.2.1-config-flow

# 5. Pracuj...
# (pisz kod, testy, dokumentację)

# 6. Commituj
git add .
git commit -m "feat(T1.2.1): implement Config Flow step 1"

# 7. Po zakończeniu
git push origin feature/T1.2.1-config-flow

# 8. Oznacz zadanie jako ukończone (✅)
# (edytuj checkbox na [x])

# 9. Jeśli koniec tygodnia - zaktualizuj status
code .task/PROJECT_STATUS.md
```

---

## ⚡ Tips & Tricks

### Szybkie wyszukiwanie

```bash
# Znajdź wszystkie zadania "w trakcie"
grep -r "\[🟡\]" .task/

# Znajdź zadania wysokiego priorytetu
grep -r "Priorytet: Wysoki" .task/phase-*.md

# Pokaż postęp aktualnej fazy
grep -c "\[x\]" .task/phase-1-foundation.md
grep -c "\[ \]" .task/phase-1-foundation.md
```

### Automatyzacja

Stwórz alias w `.bashrc` lub `.zshrc`:

```bash
# Alias do szybkiego otwarcia statusu
alias task-status='code .task/PROJECT_STATUS.md'

# Alias do sprawdzenia aktualnych zadań
alias task-current='grep -A 3 "\[🟡\]" .task/phase-*.md'

# Alias do pokazania najbliższych zadań
alias task-next='head -n 50 .task/phase-1-foundation.md'
```

### Integracja z TODO apps

Możesz wyeksportować zadania do:
- **Todoist:** Użyj parsera markdown → Todoist API
- **Notion:** Import markdown files
- **Trello:** Cards z checklistami
- **GitHub Projects:** Issues + Projects board

---

## 🤝 Współpraca (przyszłość)

### Gdy będzie więcej osób w projekcie:

1. **Przypisywanie zadań:**
   ```markdown
   - [ ] **T1.1.1:** Opis zadania
     - **Przypisane:** @username
   ```

2. **Code review:**
   - Oznacz jako 🔵 "Do weryfikacji"
   - Inny contributor robi review
   - Po akceptacji: oznacz jako ✅

3. **Synchronizacja:**
   - Pull często (git pull)
   - Aktualizuj swoje branch
   - Komunikuj co robisz (Discord/Slack)

---

## 📚 Dodatkowe zasoby

- **GitHub Issues:** Dla publicznych bug reports (po v1.0)
- **GitHub Discussions:** Dla pytań społeczności
- **Project Board:** Dla wizualnego trackingu (opcjonalnie)
- **Changelog:** Automatyczny z commitów (conventional commits)

---

## ❓ FAQ

**Q: Czy muszę używać emoji statusów (🟡, ✅)?**
A: Nie, możesz używać tekstu: `[IN_PROGRESS]`, `[DONE]`. Emoji są bardziej czytelne.

**Q: Co jeśli zadanie jest za duże?**
A: Podziel na mniejsze sub-zadania (T1.1.1.1, T1.1.1.2, ...).

**Q: Jak często aktualizować PROJECT_STATUS.md?**
A: Minimum raz w tygodniu. Więcej jeśli intensywna praca.

**Q: Czy mogę zmienić strukturę plików?**
A: Tak, ale zachowaj główne pliki (README, PROJECT_STATUS, phase-X). Reszta elastyczna.

**Q: Co jeśli odkryję że plan jest zły?**
A: Aktualizuj! Plany to żywe dokumenty. Dodaj "CHANGED" note w fazie.

---

**Powodzenia! 🚀**

Jeśli masz pytania lub sugestie jak ulepszyć ten system, dodaj notatkę w README.md lub stwórz Issue.
