# Fanboy Cookie Monster → Consent-O-Matic

Konwerter reguł Fanboy Cookie Monster (uBlock Origin) do własnej listy reguł
Consent-O-Matic.

## Zawartość

- `rules-list-01.json` ... `rules-list-08.json` — podzielone pliki z regułami.
- `manifest.json` — lista części i ich rozmiary.
- `fanboy-to-consent-o-matic-aggressive.py` — generator, jeśli został dołączony.

Każda część jest samodzielnym plikiem reguł Consent-O-Matic.

## Ważne: `rules-list.json`

Consent-O-Matic oczekuje listy reguł w postaci JSON zawierającego nazwane reguły
(`detectors` + `methods`). Oficjalna dokumentacja opisuje również możliwość
dodania własnej listy przez **More add-on settings → Rule lists** i podania
adresu URL do własnego JSON-a.

Dlatego nie łączymy części przez zwykły JSON-index. Każdy z ośmiu plików jest
osobną listą i można dodać jego adres Raw do Consent-O-Matic.

## GitHub

Załóż repozytorium, np.:

`fanboy-consent-o-matic`

Następnie wrzuć do głównego katalogu wszystkie pliki z tego folderu.

Po publikacji adresy będą miały postać:

`https://raw.githubusercontent.com/TWOJ_LOGIN/fanboy-consent-o-matic/main/rules-list-01.json`

i analogicznie dla `02`–`08`.

### Dodanie listy do Consent-O-Matic

1. Otwórz ustawienia dodatku Consent-O-Matic.
2. Wejdź w **More add-on settings**.
3. Otwórz **Rule lists**.
4. Dodaj URL Raw wybranego pliku JSON.
5. Powtórz dla pozostałych części, jeśli chcesz używać całego zestawu.

## Ostrzeżenie

Reguły zostały wygenerowane automatycznie z reguł kosmetycznych Fanboya.
Heurystyki „Reject/Odrzuć” nie gwarantują poprawnego działania na każdej
stronie. Na części CMP potrzebne są dedykowane reguły z jednoznacznym
selektorem przycisku.

Nie używaj automatycznego odrzucania jako substytutu sprawdzania preferencji
na stronach, na których wybór ma istotne znaczenie.

## Aktualizacja

Generator może ponownie pobrać listę Fanboy Cookie Monster i wygenerować
nowe części. Po każdej aktualizacji należy sprawdzić działanie reguł przed
opublikowaniem nowej wersji.
