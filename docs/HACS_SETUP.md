# HACS Setup Guide

Instrukcje przygotowania i publikacji integracji Adaptive Thermal Control w HACS.

## Wymagania przed publikacją

### 1. Repozytorium GitLab

- [x] Repozytorium publiczne na GitLab
- [ ] Zaktualizować placeholder URLs (`YOUR_USERNAME`) w plikach:
  - `custom_components/adaptive_thermal_control/manifest.json`
  - `README.md`
  - `info.md`

### 2. Wymagane pliki (obecne w projekcie)

- [x] `hacs.json` - Konfiguracja HACS
- [x] `LICENSE` - Licencja MIT
- [x] `README.md` - Dokumentacja użytkownika
- [x] `info.md` - Krótki opis dla HACS
- [x] `custom_components/adaptive_thermal_control/manifest.json` - Manifest integracji
- [x] `.gitlab-ci.yml` - Pipeline CI/CD

### 3. Manifest.json - Wymagane pola

Plik `manifest.json` zawiera wszystkie wymagane pola:

```json
{
  "domain": "adaptive_thermal_control",
  "name": "Adaptive Thermal Control",
  "codeowners": ["@jurek"],
  "config_flow": true,
  "documentation": "https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control",
  "iot_class": "local_polling",
  "issue_tracker": "https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control/-/issues",
  "requirements": ["numpy>=1.21.0", "scipy>=1.7.0"],
  "version": "0.1.0"
}
```

### 4. Home Assistant Brands (opcjonalne, ale zalecane)

Aby integracja wyglądała profesjonalnie w Home Assistant, należy dodać ją do [home-assistant/brands](https://github.com/home-assistant/brands):

1. Fork repozytorium `home-assistant/brands`
2. Dodaj logo integracji do `custom_integrations/adaptive_thermal_control/`
3. Utwórz `icon.png` (256x256 px) i `logo.png` (512x512 px)
4. Utwórz Pull Request

## Konfiguracja GitLab

### 1. Utworzenie repozytorium

```bash
# Inicjalizacja git (jeśli jeszcze nie zrobione)
git init
git add .
git commit -m "feat: initial commit with HACS support"

# Dodanie remote GitLab (zamień YOUR_USERNAME i nazwa_repo)
git remote add origin https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control.git
git push -u origin main
```

### 2. Konfiguracja CI/CD Schedule (opcjonalne)

Aby pipeline uruchamiał się codziennie:

1. Idź do **Settings → CI/CD → Schedules**
2. Kliknij **New schedule**
3. Ustaw:
   - **Description**: Daily HACS validation
   - **Interval Pattern**: `0 0 * * *` (codziennie o północy)
   - **Target Branch**: `main`
4. Kliknij **Save pipeline schedule**

### 3. Tagi i Releases

HACS preferuje używanie tagów i releases:

```bash
# Utworzenie pierwszego release
git tag -a v0.1.0 -m "Initial release with HACS support"
git push origin v0.1.0
```

W GitLab:
1. Idź do **Deployments → Releases**
2. Kliknij **New release**
3. Wybierz tag `v0.1.0`
4. Dodaj opis zmian
5. Kliknij **Create release**

## Instalacja przez użytkowników

### Przed dodaniem do default HACS store

Użytkownicy mogą dodać integrację jako **Custom Repository**:

1. Otwórz **HACS** w Home Assistant
2. Przejdź do **Integrations**
3. Kliknij **3 kropki** w prawym górnym rogu
4. Wybierz **Custom repositories**
5. Dodaj URL: `https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control`
6. Wybierz kategorię: **Integration**
7. Kliknij **Add**
8. Znajdź **Adaptive Thermal Control** w HACS
9. Kliknij **Download**
10. Zrestartuj Home Assistant

### Po dodaniu do default HACS store (Phase 6)

1. Otwórz **HACS**
2. Przejdź do **Integrations**
3. Kliknij **Explore & Download Repositories**
4. Wyszukaj **Adaptive Thermal Control**
5. Kliknij **Download**
6. Zrestartuj Home Assistant

## Dodanie do domyślnego HACS store (Phase 6)

Kiedy integracja będzie gotowa (po Phase 5), można ją zgłosić do domyślnego HACS store:

1. **Przygotowanie**:
   - Upewnij się, że wszystkie testy przechodzą
   - Masz co najmniej jeden release (tag)
   - Dokumentacja jest kompletna
   - Wszystkie URLe są zaktualizowane

2. **Zgłoszenie**:
   - Idź do [HACS/default](https://github.com/hacs/default)
   - Kliknij **Issues** → **New Issue**
   - Wybierz szablon **"Add integration"**
   - Wypełnij formularz:
     - Repository URL: `https://gitlab.com/YOUR_USERNAME/adaptive-thermal-control`
     - Category: Integration
     - Description: Advanced predictive heating control for floor heating systems

3. **Review**:
   - HACS team sprawdzi repozytorium
   - Mogą poprosić o zmiany
   - Po zatwierdzeniu integracja pojawi się w HACS

## Walidacja lokalna

Przed push do GitLab, można lokalnie zwalidować integrację:

### HACS Validation

```bash
# Sklonuj HACS action
git clone https://github.com/hacs/action.git /tmp/hacs-action
cd /tmp/hacs-action

# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom walidację
python -m hacs_action.validate \
  --category integration \
  --repository /path/to/adaptive-thermal-control
```

### Hassfest Validation

Wymaga środowiska Home Assistant:

```bash
# W środowisku Home Assistant
python -m script.hassfest \
  --integration-path custom_components/adaptive_thermal_control
```

## Checklist przed publikacją

- [ ] Wszystkie pliki HACS są obecne i poprawne
- [ ] Zaktualizowano wszystkie URLe (zmieniono `YOUR_USERNAME`)
- [ ] Utworzono repozytorium GitLab
- [ ] Pipeline CI/CD działa poprawnie
- [ ] Utworzono pierwszy release (tag v0.1.0)
- [ ] Przetestowano instalację jako Custom Repository
- [ ] Dokumentacja jest kompletna
- [ ] Logo dodane do home-assistant/brands (opcjonalne)

## Utrzymanie i aktualizacje

### Tworzenie nowych wersji

```bash
# Zaktualizuj version w manifest.json
# Commit zmian
git add .
git commit -m "feat(T3.4.5): add MPC controller"

# Utwórz tag
git tag -a v0.2.0 -m "Added MPC controller and weather integration"
git push origin v0.2.0

# Utwórz release w GitLab UI
```

### Semantic Versioning

Projekt używa [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): Nowe funkcje, kompatybilne wstecz
- **PATCH** (0.0.1): Bug fixes

### Changelog

Utrzymuj `CHANGELOG.md` z opisem zmian w każdej wersji.

## Wsparcie

- **HACS Documentation**: https://hacs.xyz/docs/publish/integration
- **Home Assistant Developers**: https://developers.home-assistant.io/
- **GitLab CI/CD Docs**: https://docs.gitlab.com/ee/ci/

## Status HACS

**Current Status**: ✅ HACS-ready (Phase 1 complete)
**Default Store**: 🔴 Not yet (planned for Phase 6)
**Last Updated**: 2025-10-27
