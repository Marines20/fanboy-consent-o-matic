#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fanboy-to-consent-o-matic-reject.py

Konwertuje reguły kosmetyczne EasyList/Fanboy Cookie Monster
(uBlock Origin / Adblock Plus) do reguł Consent-O-Matic.

Ważne:
- reguły CSS służą do wykrycia obecności banera,
- DO_CONSENT próbuje wybrać "odrzuć" dla wszystkich opcjonalnych zgód,
- SAVE_CONSENT próbuje kliknąć przycisk zapisania/zatwierdzenia,
- reguły sieciowe, proceduralne i wyjątki wymagające logiki uBO są pomijane,
- ponieważ lista źródłowa nie opisuje przycisków CMP, kliknięcia są
  oparte na tekstach przycisków; na części stron może być potrzebna
  dedykowana reguła dla konkretnego CMP.

Użycie:
    python fanboy-to-consent-o-matic-reject.py
lub:
    python fanboy-to-consent-o-matic-reject.py wejscie.txt wyjscie.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


SCHEMA_URL = (
    "https://raw.githubusercontent.com/cavi-au/Consent-O-Matic/"
    "master/rules.schema.json"
)

# Proceduralne rozszerzenia uBO, których nie można bezpośrednio
# zamienić na zwykły matcher CSS Consent-O-Matic.
PROCEDURAL_MARKERS = (
    "+js(",
    ":has-text(",
    ":matches-css",
    ":matches-attr",
    ":xpath(",
    ":remove(",
    ":style(",
    ":upward(",
    ":watch-attr(",
    ":matches-path(",
    ":min-text-length(",
    ":nth-ancestor(",
    ":is-procedural(",
)

# Teksty spotykane przy przyciskach odmowy.
REJECT_TEXTS = [
    "Reject all",
    "Reject All",
    "Reject",
    "Decline all",
    "Decline All",
    "Decline",
    "Deny all",
    "Deny All",
    "Deny",
    "Refuse all",
    "Refuse All",
    "Refuse",
    "Disallow all",
    "Disallow All",
    "Do not accept",
    "Do Not Accept",
    "Do not consent",
    "Do Not Consent",
    "No, thanks",
    "No thanks",
    "Odrzuć wszystko",
    "Odrzuć Wszystko",
    "Odrzuć",
    "Odmów wszystkim",
    "Odmów Wszystkim",
    "Odmów",
    "Nie akceptuję",
    "Nie Akceptuję",
    "Nie wyrażam zgody",
    "Nie Wyrażam Zgody",
    "Nie zgadzam się",
    "Nie Zgadzam się",
    "Nie, dziękuję",
    "Nie dzięki",
    "Tout refuser",
    "Refuser tout",
    "Refuser",
    "Alle ablehnen",
    "Ablehnen",
    "Rechazar todo",
    "Rechazar",
    "Rifiuta tutto",
    "Rifiuta",
    "Recusar tudo",
    "Recusar",
    "Afwijzen",
    "Alles afwijzen",
    "Avvis",
    "Avvisa alla",
]

# Teksty spotykane przy przyciskach zapisu/zaakceptowania ustawień.
SAVE_TEXTS = [
    "Save preferences",
    "Save Preference",
    "Save settings",
    "Save Settings",
    "Save choices",
    "Save Choices",
    "Save",
    "Confirm choices",
    "Confirm Choices",
    "Confirm selection",
    "Confirm Selection",
    "Confirm",
    "Apply choices",
    "Apply Choices",
    "Apply",
    "Submit choices",
    "Submit Choices",
    "Done",
    "Finish",
    "Zapisz preferencje",
    "Zapisz ustawienia",
    "Zapisz wybór",
    "Zapisz wybory",
    "Zapisz",
    "Potwierdź wybór",
    "Potwierdź wybory",
    "Potwierdź",
    "Zastosuj",
    "Gotowe",
    "Zakończ",
    "Speichern",
    "Einstellungen speichern",
    "Auswahl bestätigen",
    "Guardar preferencias",
    "Guardar configuración",
    "Confirmar selección",
    "Guardar",
    "Salva preferenze",
    "Salva impostazioni",
    "Conferma selezione",
    "Salva",
]

# Kolejność metod jest istotna w Consent-O-Matic.
# HIDE_CMP jest celowo wykonywane na końcu przez mechanizm metod,
# a DO_CONSENT i SAVE_CONSENT odpowiadają za interakcję.
BUTTON_SELECTOR = (
    "button, [role=\"button\"], input[type=\"button\"], "
    "input[type=\"submit\"], a"
)


def split_domains_prefix(line: str):
    """
    Rozdziela:
        example.com,example.org##.cookie
    na domeny i selektor.
    """
    if "##" not in line:
        return None, None

    prefix, selector = line.split("##", 1)
    prefix = prefix.strip()
    selector = selector.strip()

    if not selector:
        return None, None

    domains = []
    for raw in prefix.split(","):
        raw = raw.strip()
        if not raw:
            continue

        # Pomijamy negowane domeny, bo prosty matcher URL nie odwzoruje
        # ich semantyki bez dodatkowej logiki.
        if raw.startswith("~"):
            return None, None

        # uBO może mieć opcjonalne wildcardy; nie są bezpiecznym
        # odpowiednikiem prostego URL matcher.
        if "*" in raw:
            return None, None

        # Usuń ewentualne protokoły.
        raw = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", raw)
        raw = raw.split("/", 1)[0]
        raw = raw.split(":", 1)[0]

        # Walidacja w stylu domenowym.
        if not re.match(
            r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$|^[A-Za-z0-9-]+$",
            raw,
        ):
            return None, None

        domains.append(raw.lower())

    if not domains:
        return None, None

    return domains, selector


def css_matcher(selector: str):
    return {
        "type": "css",
        "target": {
            "selector": selector
        }
    }


def url_matcher(domain: str):
    # Dopasowanie do domeny i jej subdomen.
    return {
        "type": "url",
        "url": rf"^https?://([^/]+\.)?{re.escape(domain)}(?:/|$)"
    }


def click_by_text(texts):
    """
    Agresywny selektor odmowy.

    Consent-O-Matic textFilter działa na wybranym elemencie, więc zamiast
    ograniczać się wyłącznie do tekstu buttona, wybieramy typowe elementy
    interaktywne i przepuszczamy wiele wariantów językowych.

    Dodatkowo osobna lista NEGATIVE_WORDS jest używana przez akcję JS? Nie:
    Consent-O-Matic nie wykonuje arbitralnego JS w regułach. Dlatego cała
    heurystyka musi być wyrażona przez jego DOM selection/textFilter.
    """
    return {
        "type": "click",
        "target": {
            "selector": (
                "button, [role=\"button\"], input[type=\"button\"], "
                "input[type=\"submit\"], a, "
                "[aria-label], [title], [data-testid], "
                "[class*=\"reject\" i], [id*=\"reject\" i], "
                "[class*=\"decline\" i], [id*=\"decline\" i], "
                "[class*=\"deny\" i], [id*=\"deny\" i], "
                "[class*=\"refuse\" i], [id*=\"refuse\" i], "
                "[class*=\"disallow\" i], [id*=\"disallow\" i], "
                "[class*=\"optout\" i], [id*=\"optout\" i], "
                "[class*=\"opt-out\" i], [id*=\"opt-out\" i], "
                "[class*=\"reject-all\" i], [id*=\"reject-all\" i], "
                "[class*=\"reject_all\" i], [id*=\"reject_all\" i]"
            ),
            "textFilter": texts,
            "displayFilter": True,
        },
        "openInTab": False,
    }


def click_reject_by_attribute():
    """
    Fallback: element może nie mieć widocznego tekstu, ale może mieć
    aria-label/title/klasę/ID wskazujące na odmowę.

    Consent-O-Matic nie pozwala na OR pomiędzy niezależnymi matcherami
    w jednym target, dlatego generujemy kilka alternatywnych akcji.
    """
    selectors = [
        '[aria-label*="reject" i]',
        '[aria-label*="decline" i]',
        '[aria-label*="deny" i]',
        '[aria-label*="refuse" i]',
        '[aria-label*="disallow" i]',
        '[title*="reject" i]',
        '[title*="decline" i]',
        '[title*="deny" i]',
        '[title*="refuse" i]',
        '[title*="disallow" i]',
        '[id*="reject" i]',
        '[id*="reject-all" i]',
        '[id*="decline" i]',
        '[id*="deny" i]',
        '[id*="refuse" i]',
        '[id*="disallow" i]',
        '[class*="reject" i]',
        '[class*="reject-all" i]',
        '[class*="reject_all" i]',
        '[class*="decline" i]',
        '[class*="deny" i]',
        '[class*="refuse" i]',
        '[class*="disallow" i]',
        '[data-testid*="reject" i]',
        '[data-testid*="decline" i]',
        '[data-testid*="deny" i]',
        '[data-testid*="refuse" i]',
    ]

    actions = []
    for selector in selectors:
        actions.append({
            "type": "click",
            "target": {
                "selector": selector,
                "displayFilter": True,
            },
            "openInTab": False,
        })

    return actions


def make_reject_consent_action():
    """
    Najpierw próba standardowego "Reject/Odrzuć", potem fallbacki po
    aria-label/title/id/class/data-testid. Consent-O-Matic wykonuje akcje
    listy po kolei; jeśli wcześniejszy selektor niczego nie znajdzie,
    następny może zadziałać.
    """
    actions = [
        click_by_text(REJECT_TEXTS),
    ]

    actions.extend(click_reject_by_attribute())

    return {
        "type": "list",
        "actions": actions,
    }


def make_save_action():
    """
    Po odmowie szukamy szeroko przycisku zapisania/konfirmacji.
    Fallbacki po nazwach atrybutów pomagają przy przyciskach bez tekstu.
    """
    actions = [
        click_by_text(SAVE_TEXTS),
    ]

    save_selectors = [
        '[aria-label*="save" i]',
        '[aria-label*="confirm" i]',
        '[aria-label*="apply" i]',
        '[aria-label*="done" i]',
        '[title*="save" i]',
        '[title*="confirm" i]',
        '[title*="apply" i]',
        '[title*="done" i]',
        '[id*="save" i]',
        '[id*="confirm" i]',
        '[id*="apply" i]',
        '[id*="done" i]',
        '[class*="save" i]',
        '[class*="confirm" i]',
        '[class*="apply" i]',
        '[class*="done" i]',
    ]

    for selector in save_selectors:
        actions.append({
            "type": "click",
            "target": {
                "selector": selector,
                "displayFilter": True,
            },
            "openInTab": False,
        })

    return {
        "type": "list",
        "actions": actions,
    }


def rule_name(domains, selector, index):
    if domains:
        base = domains[0].replace(".", "_")
        return f"Cookie CMP reject - {base} - {index}"
    return f"Cookie CMP reject - generic - {index}"


def convert(input_path: Path, output_path: Path):
    lines = input_path.read_text(encoding="utf-8", errors="replace").splitlines()

    # Exact cosmetic exceptions:
    # example.com#@#.selector
    exceptions = set()

    # (domains tuple, selector)
    candidates = []

    skipped = 0

    for raw_line in lines:
        line = raw_line.strip()

        if not line or line.startswith("!"):
            continue

        # Pomijamy reguły element hiding exception:
        # example.com#@#.foo
        if "#@#" in line:
            prefix, selector = line.split("#@#", 1)
            if selector.strip():
                domains, selector = split_domains_prefix(
                    prefix + "##" + selector
                )
                if domains and selector:
                    exceptions.add(
                        (tuple(sorted(domains)), selector)
                    )
            continue

        # Tylko reguły kosmetyczne z ##.
        if "##" not in line:
            skipped += 1
            continue

        domains, selector = split_domains_prefix(line)

        if not selector:
            skipped += 1
            continue

        # Pomijamy reguły proceduralne.
        if any(marker in selector for marker in PROCEDURAL_MARKERS):
            skipped += 1
            continue

        # Zbyt złożone selektory mogą być nieakceptowane przez parser CSS.
        if selector.count("{") or selector.count("}"):
            skipped += 1
            continue

        candidates.append((domains, selector))

    # Usuń wyjątki exact.
    filtered = []
    for domains, selector in candidates:
        key = (tuple(sorted(domains)), selector)
        if key in exceptions:
            continue
        filtered.append((domains, selector))

    # Deduplikacja.
    unique = []
    seen = set()

    for domains, selector in filtered:
        key = (
            tuple(sorted(domains)),
            selector,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append((domains, selector))

    result = {
        "$schema": SCHEMA_URL
    }

    for index, (domains, selector) in enumerate(unique, start=1):
        present = [css_matcher(selector)]
        showing = [css_matcher(selector)]

        # Dla reguł domenowych dodajemy URL matcher jako ograniczenie.
        if domains:
            for domain in domains:
                present.append(url_matcher(domain))
                showing.append(url_matcher(domain))

        name = rule_name(domains, selector, index)

        result[name] = {
            "detectors": [
                {
                    "presentMatcher": present,
                    "showingMatcher": showing,
                }
            ],
            "methods": [
                {
                    "name": "DO_CONSENT",
                    "action": make_reject_consent_action(),
                },
                {
                    "name": "SAVE_CONSENT",
                    "action": make_save_action(),
                },
                {
                    "name": "HIDE_CMP",
                },
            ],
        }

    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Gotowe: {output_path}")
    print(f"Przekonwertowane reguły: {len(unique):,}")
    print(f"Pominięte reguły: {skipped:,}")
    print(f"Rozmiar: {output_path.stat().st_size / 1024 / 1024:.2f} MiB")


def main():
    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path("fanboy-cookiemonster_ubo.txt")

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = Path("rules-list-reject.json")

    if not input_path.exists():
        print(
            f"Nie znaleziono pliku wejściowego: {input_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    convert(input_path, output_path)


if __name__ == "__main__":
    main()
