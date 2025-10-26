# Wymagania i specyfikacja projektu - Adaptive Thermal Control

Wypełnij poniższe pytania aby określić pełną specyfikację systemu adaptacyjnego sterowania ogrzewaniem podłogowym.

---

## 1. Architektura integracji Home Assistant

### 1.1 Podstawowa struktura
**Pytanie:** Czy to będzie custom component w `custom_components/`?
**Odpowiedź:**
Tak. Oraz dostępny przez HACS.

**Pytanie:** Jaka będzie nazwa integracji (folder w custom_components)?
**Odpowiedź:**
adaptive_thermal_control

**Pytanie:** Czy integracja będzie konfigurowalna przez UI (config flow) czy przez YAML?
**Odpowiedź:**
UI

**Pytanie:** Czy potrzebujemy osobnego manifestu z zależnościami zewnętrznymi (np. biblioteki ML)?
**Odpowiedź:**
Jeśli okażą się potrzebne, to tak.

---

## 2. Model danych i encje

### 2.1 Termostaty pokojowe
**Pytanie:** Ile termostatów/pokoi planujemy obsługiwać?
**Odpowiedź:**
Od 1. Bez ograniczenia górnego limitu, ale z przyjęciem że na Raspberry Pi 5 powinno spokojnie być obsługiwane do 20.

**Pytanie:** Jakie parametry będzie miał każdy termostat (temperatura zadana, tryb, preset, etc.)?
**Odpowiedź:**
Temperaturę zadaną (a najlepiej z histerezą), schedule (w jakich godzinach jaki tryb), tryby (home, away, sleep, manual override, etc.),
sąsiadujące pomieszczenia (do uwzględnienia migracji cieplnej między pomieszczeniami), powierzchnia, orientacja okna

**Pytanie:** Czy termostaty będą miały tryby działania (home, away, sleep, manual override)?
**Odpowiedź:**
Tak, patrz punkt 2.1 odpowiedź na drugie pytanie.

### 2.2 Sensory wymagane dla każdego pokoju
**Pytanie:** Skąd bierzemy aktualną temperaturę pokoju?
**Odpowiedź:**
Z encji podanej przy konfiguracji termostatu.

**Pytanie:** Czy to będą istniejące encje Home Assistant czy nowe sensory?
**Odpowiedź:**
Istniejące.

**Pytanie:** Jakie dodatkowe sensory są potrzebne (wilgotność, obecność ludzi)?
**Odpowiedź:**
Opcjonalnie: 
- temperatura wejścia i wyjścia na obiegu/obiegach (jedno pomieszczenie może mieć więcej niż jeden obieg)
- temperatura na zewnątrz
- prognoza pogody 
- prognoza energii solarnej (do uwzględnienia ciepła od słońca przez okna)

### 2.3 Obiegi grzewcze
**Pytanie:** Ile obiegów grzewczych obsługujemy?
**Odpowiedź:**
Na jeden pokój może być 1 lub więcej

**Pytanie:** Jak mapujemy pokoje do obiegów (jeden pokój = jeden obieg czy wiele pokoi na obieg)?
**Odpowiedź:**
jeden pokój = jeden lub więcej obiegów

**Pytanie:** Skąd bierzemy temperaturę wejścia i wyjścia wody dla każdego obiegu?
**Odpowiedź:**
Z encji podanych przy konfiguracji termostatu.

**Pytanie:** Jak sterujemy obiegiem - przez switch, climate czy inaczej?
**Odpowiedź:**
Przez podane encje, które mogą być switch, valve, etc. Trzeba uwzględnić, że przy zaworach można regulować otwarciem, 
ale niektóre mogą tego nie obsługiwać (a także switch) i wtedy trzeba zastosować PWM i to taki dłuugi. Potrzebujemy więc też
wiedzieć jaki jest czas otwarcia i zamknięcia zaworów.

---

## 3. Algorytm predykcyjny i uczenie maszynowe

### 3.1 Model uczenia
**Pytanie:** Jaki rodzaj modelu ML planujemy (regresja liniowa, sieci neuronowe, gradient boosting, inne)?
**Odpowiedź:**
Na podstawie dokumentacji z ZAAWANSOWANE SYSTEMY STEROWANIA OGRZEWANIEM PODŁOGOWYM.md oraz CHAT.md. 

**Pytanie:** Jakiej biblioteki ML użyjemy (scikit-learn, TensorFlow, PyTorch, Prophet, inne)?
**Odpowiedź:**
j.w.

**Pytanie:** Jak często model będzie się uczył (co godzinę, dziennie, na żądanie)?
**Odpowiedź:**
adaptacyjnie, raz dziennie

**Pytanie:** Gdzie przechowamy wytrenowany model (plik pickle, baza danych, inne)?
**Odpowiedź:**
W zależności od przyjętego rozwiązania.

### 3.2 Dane historyczne
**Pytanie:** Ile dni historii potrzebujemy do uczenia (7, 30, 90 dni)?
**Odpowiedź:**
To jest już ustawienie w konfiguracji Home Assistant.

**Pytanie:** Skąd pobieramy dane historyczne (Home Assistant recorder/history)?
**Odpowiedź:**
Home Assistant recorder

**Pytanie:** W jakiej formie przechowujemy przetworzone dane treningowe?
**Odpowiedź:**
Na podstawie tego jaką decyzję podejmiemy przy wybraniu modelu.

**Pytanie:** Czy mamy minimum danych do rozpoczęcia działania? Jaki fallback jeśli danych jest za mało (prosty algorytm ON/OFF)?
**Odpowiedź:**
W taki sposób, żeby szybko ograniczyć wahania temperatury.

### 3.3 Parametry wejściowe modelu (features)
**Pytanie:** Jakie dokładnie features wchodzą do modelu? Wymień wszystkie:
- [x] Temperatura zewnętrzna (aktualna, trend, prognoza)
- [x] Temperatury sąsiednich pokoi
- [x] Czas doby, dzień tygodnia, sezon
- [x] Nasłonecznienie (aktualne, prognoza)
- [x] Temperatura wody w obiegu
- [x] Historia poprzednich stanów grzania
- [ ] Obecność ludzi w pomieszczeniu
- [ ] Inne (wymień):

**Odpowiedź:**


---

## 4. Integracje zewnętrzne

### 4.1 Pogoda
**Pytanie:** Z jakiej integracji pobieramy temperaturę zewnętrzną i prognozę (Met.no, OpenWeatherMap, AccuWeather, inna)?
**Odpowiedź:**
Z podanych encji przy konfiguracji termostatu z Home Assistant. 

**Pytanie:** Które encje dokładnie wykorzystamy (podaj nazwy entity_id)?
**Odpowiedź:**
To będzie podawane w konfiguracji termostatu z Home Assistant.

**Pytanie:** Jak daleko w przyszłość potrzebujemy prognozy (6h, 24h, 48h)?
**Odpowiedź:**
Ile będzie w encji Home Assistant. Myślę, że nie więcej niż doba.

### 4.2 Panele solarne
**Pytanie:** Z jakiej integracji pobieramy dane o nasłonecznieniu?
**Odpowiedź:**
Z encji z prognozą dla fotowoltaiki. Na podstawie ilości energii w danej godzinie, pozycji słońca i orientacji względem stron świata,
będziemy mogli wyliczyć ile energii będzie "wytworzone" w postaci ciepła przez słońce. 

**Pytanie:** Czy to produkcja energii czy bezpośredni pomiar nasłonecznienia (W/m²)?
**Odpowiedź:**
Produkcja energii.

**Pytanie:** Jak modelujemy rozmieszczenie pokoi względem stron świata?
**Odpowiedź:**
Przy konfiguracji termostatu z Home Assistant powinniśmy dodawać informacje o orientacji okien. (Może być ich wiele)

**Pytanie:** Czy to będzie konfigurowane per pokój (orientacja okien)?
**Odpowiedź:**
Tak

### 4.3 Ceny energii
**Pytanie:** Z jakiej integracji pobieramy ceny (Energa, Tauron, EPEX Spot, inna)?
**Odpowiedź:**
Z encji wskazanej przy konfiguracji termostatu w Home Assistant.

**Pytanie:** Czy cena będzie wpływać na decision making (preferować tańsze godziny)?
**Odpowiedź:**
Tak. Ale korzystanie z ceny energii jest opcjonalne.

**Pytanie:** Czy chcemy strategię "podgrzej teraz bo później drożej" czy tylko logowanie kosztów?
**Odpowiedź:**
Chcemy strategii "podgrzej teraz bo później drożej"

---

## 5. Sterowanie obiegami grzewczymi

### 5.1 Piec i moc maksymalna
**Pytanie:** Jak określamy maksymalną moc pieca?
**Odpowiedź:**
Podane w konfiguracji integracji w Home Assistant.

**Pytanie:** Czy to stała wartość czy dynamiczna (zależy od temperatury zewnętrznej)?
**Odpowiedź:**
Przyjmijmy, że stała

**Pytanie:** Jak algorytm decyduje, które obiegi włączyć gdy wszystkie "chcą" ciepła?
- [ ] Priorytet pokojów
- [x] Rotacja fair-share 
- [ ] Optymalizacja kosztowa
- [ ] Inne (opisz):

**Odpowiedź:**


### 5.2 Logika sterowania
**Pytanie:** Jak często algorytm podejmuje decyzje (co 1 min, 5 min, 15 min)?
**Odpowiedź:**
Tak jak często będzie wynikało z algorytmu który wykorzystamy

**Pytanie:** Czy używamy PWM/modulacji (% czasu włączenia w oknie czasowym)?
**Odpowiedź:**
Jeśli zawór nie ma położenia, to tak.

**Pytanie:** Jakie są minimalne czasy włączenia/wyłączenia obiegu (zabezpieczenie sprzętu)?
**Odpowiedź:**
Będą wynikać z czasu otwarcia i zamknięcia zaworu. Do konfiguracji przy termostatach.

**Pytanie:** Czy są ograniczenia ile obiegów może działać jednocześnie?
**Odpowiedź:**
Na podstawie konfiguracji termostatów, w tym powierzchni obiegów grzewczych, powinna być wyliczana moc i algorytm sterowania, 
powinien dobierać otwieranie zaworów tak by optymalizować koszt.

---

## 6. Tryby pracy i bezpieczeństwo

### 6.1 Tryby awaryjne
**Pytanie:** Fallback gdy model się nie nauczył - jaki prosty algorytm użyjemy (ON/OFF z histerezą)?
**Odpowiedź:**
To zależy od konfiguracji.

**Pytanie:** Co jeśli brak danych z sensorów (zewnętrznych, wewnętrznych)?
**Odpowiedź:**
W przypadki zewnętrznego to dajemy ostrzeżenie, że brakuje danych. W przypadku wewnętrzenego to błąd, który uniemożliwia grzanie pomieszczenia.

**Pytanie:** Jak działa tryb ręczny (wyłączenie automatyki)?
**Odpowiedź:**
Dobre pytanie. Zostawmy na później.

**Pytanie:** Czy mogę wymusić grzanie/nie grzanie konkretnego pokoju? Jak?
**Odpowiedź:**
Wyłączająć termostat w HA.

### 6.2 Limity bezpieczeństwa
**Pytanie:** Maksymalna temperatura pokoju (wyłączenie awaryjne)?
**Odpowiedź:**
Do konfiguracji.

**Pytanie:** Minimalna temperatura (ochrona przed zamarznięciem)?
**Odpowiedź:**
Do konfiguracji.

**Pytanie:** Timeout braku odczytu z sensora (ile sekund/minut)?
**Odpowiedź:**
30 minut.

**Pytanie:** Maksymalny czas ciągłego grzania (jeśli taki limit istnieje)?
**Odpowiedź:**
Nie ma.

---

## 7. Konfiguracja i UI

### 7.1 Setup początkowy
**Pytanie:** Jakie parametry użytkownik musi podać przy pierwszym uruchomieniu?
Lista parametrów do skonfigurowania:
- [ ] Lista pokoi i ich charakterystyki (powierzchnia, orientacja, sąsiedzi)
- [ ] Mapowanie pokoi do obiegów grzewczych
- [ ] Encje sensorów temperatury (entity_id dla każdego pokoju)
- [ ] Encje sterujące obiegami (entity_id dla każdego obiegu)
- [ ] Encja pogody
- [ ] Encja cen energii
- [ ] Encja nasłonecznienia
- [ ] Parametry pieca (moc, limity)
- [ ] Inne (wymień):

**Odpowiedź:**
Dla całej integracji:
- encja temperatury zewnętrznej (opcjonalne)
- encja załączania ogrzewania CO (opcjonalne)
- encja bieżącej ceny za jednostkę ogrzewania (kWh lub kcal, opcjonalne)
- encja pogody (opcjonalne)
- encja nasłonecznienia (moc na m2) (opcjonalne)
- encja bieżącego zużycia energii (kWh lub kcal, opcjonalne)
- moc maksymalna pieca (opcjonalnie)
Dla termostatu (pomieszczenia):
- encje sterujące zaworami obiegu (wymagane) 
- encja temperatury w pokoju (wymagane)
- czas otwarcia i zamknięcia obiegu (opcjonalne)
- sąsiadujące pomieszczenia (opcjonalne)
- orientacja okien (opcjonalne)
- encje otwarcia okien (opcjonalne)

### 7.2 Dashboardy i karty
**Pytanie:** Jakie informacje chcemy wyświetlać w UI?
- [x] Aktualny stan każdego pokoju (temperatura, tryb, grzanie ON/OFF)
- [x] Prognoza grzania
- [ ] Historia temperatur
- [ ] Koszty grzania
- [x] Wydajność algorytmu (błędy predykcji)
- [x] Diagnostyka (dlaczego grzeje/nie grzeje)
- [ ] Inne (wymień):

**Odpowiedź:**


---

## 8. Persystencja i diagnostyka

### 8.1 Zapisywanie stanu
**Pytanie:** Gdzie zapisujemy parametry nauczone (ścieżka pliku, baza danych)?
**Odpowiedź:**
Zgodnie z wybranym rozwiązaniem.

**Pytanie:** Jak często zapisujemy stan modelu?
**Odpowiedź:**
Zgodnie z wybranym rozwiązaniem.

**Pytanie:** Czy logujemy decyzje algorytmu do późniejszej analizy? W jakim formacie?
**Odpowiedź:**
Zgodnie z wybranym rozwiązaniem.

### 8.2 Debugowanie
**Pytanie:** Jakie logi/metryki potrzebujemy (poziom szczegółowości)?
**Odpowiedź:**
Potrzebne do debugowania.

**Pytanie:** Czy chcemy dashboard z metrykami wydajności modelu?
**Odpowiedź:**
Tak.

**Pytanie:** Jak użytkownik może zdiagnozować problemy (logi, sensory diagnostyczne, inne)?
**Odpowiedź:**
Logi, dane diagnostyczne.

---

## 9. Rozwój i testowanie

### 9.1 Środowisko testowe
**Pytanie:** Jak będziemy testować bez fizycznego systemu grzewczego?
**Odpowiedź:**
Mockowanie.

**Pytanie:** Czy potrzebujemy symulator/mock Home Assistant?
**Odpowiedź:**
Nie

**Pytanie:** Jak walidujemy poprawność algorytmu przed wdrożeniem (testy jednostkowe, integracyjne, backtesting na danych historycznych)?
**Odpowiedź:**
Testujemy na danych historycznych.

---

## 10. Dodatkowe uwagi

**Pytanie:** Czy są jakieś dodatkowe wymagania, funkcje lub ograniczenia, które nie zostały tutaj wymienione?
**Odpowiedź:**
