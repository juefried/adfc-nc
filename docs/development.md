# Entwicklung und Tests

## Umgebung

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

## Qualitätsprüfungen

Vor jedem Abschluss müssen alle Prüfungen fehlerfrei laufen:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
```

Zum automatischen Formatieren:

```powershell
python -m ruff format .
```

## Tests

- Unit-Tests liegen unter `tests/unit/`.
- HTTP-Aufrufe werden mit `respx` gemockt; Unit-Tests sprechen nie mit der
  echten Nextcloud-Instanz.
- Abgedeckt sind unter anderem:
  - Paging und Abbruch bei wiederholten Seiten,
  - Login-Werte in Sekunden und Millisekunden,
  - `0` als „nie angemeldet“ und `-1` als `pre_nc31`,
  - Altersableitung aus exaktem Datum, Erst-/Letztlogin und first_seen,
  - Baseline-Verhalten des Inventars,
  - Auflösung von Gruppen-Anzeigenamen,
  - deaktivierte Benutzer,
  - Erkennung und Filterung von Ressourcenbenutzern (`OC*`),
  - Stale-Filter inklusive unbekanntem Alter,
  - OCS-Fehler, Authentifizierungsfehler und Rate Limits,
  - JSON- und Tabellenausgabe der CLI.
- Integrationstests gegen eine echte Instanz sind nicht Teil der
  Standard-Testausführung.

## Neuen Befehl ergänzen

1. Fachlogik in `src/adfc_nc/nextcloud/<ressource>.py` implementieren.
2. Nur die für die CLI nötigen Felder in eine Dataclass übernehmen.
3. Fehler über die Typen in `nextcloud/errors.py` melden.
4. Ein dünnes Typer-Kommando unter `src/adfc_nc/commands/` anlegen.
5. Die Befehlsgruppe in `src/adfc_nc/cli.py` registrieren.
6. Ausgabe in `src/adfc_nc/output.py` ergänzen, inklusive `--json`.
7. Mindestens einen Erfolgs- und einen Fehlerfall testen.
8. Hilfe-Ausgabe prüfen und README sowie `docs/` aktualisieren.
9. Bei destruktiven Befehlen `--dry-run` und eine Bestätigung vorsehen.

## Code-Konventionen

- Vollständige Typannotationen, auch für Rückgabewerte.
- Docstrings an öffentlichen Funktionen und Klassen.
- Keine Kommentare im Code; sprechende Namen verwenden.
- Keine stillen `except`-Blöcke.
- Fehler nicht verschlucken, sondern in eigene Ausnahmen abbilden.
- Menschenlesbare Ausgabe als Standard, `--json` für Skripte.
- Befehle sollen idempotent sein, wo es fachlich möglich ist.
- Keine Secrets, App-Passwörter oder Tokens loggen oder committen.

## Abhängigkeiten

- Laufzeitbibliotheken: `requirements.txt`
- Entwicklungsbibliotheken: `requirements-dev.txt` mit `-r requirements.txt`
- Versionen exakt pinnen (`==`).
- Neue Bibliotheken nur aufnehmen, wenn sie tatsächlich gebraucht werden.
- Keine Bibliothek ad hoc installieren, ohne sie in der passenden
  Requirements-Datei zu pflegen.

## Paketierung

`pyproject.toml` enthält Metadaten, den Konsolenbefehl und die Konfiguration für
Ruff, Mypy und pytest. Die Laufzeitabhängigkeiten werden dynamisch aus
`requirements.txt` gelesen:

```toml
[project.scripts]
adfc-nc = "adfc_nc.cli:main"
```

## Manueller Smoke-Test

Ein lesender Test gegen die echte Instanz ist optional. Dabei keine
personenbezogenen Daten ausgeben. Beispiel für reine Zählwerte:

```powershell
python -c "from adfc_nc.config import load_settings; from adfc_nc.nextcloud.users import load_users; users = load_users(load_settings()); print(f'users={len(users)} with_last_login={sum(u.last_login is not None for u in users)}')"
```

## Projektstruktur

```text
src/adfc_nc/
  cli.py
  config.py
  inventory.py
  output.py
  commands/common.py
  commands/users.py
  commands/inventory.py
  nextcloud/client.py
  nextcloud/users.py
  nextcloud/errors.py
tests/
  conftest.py
  unit/test_client.py
  unit/test_inventory.py
  unit/test_users.py
  unit/test_cli_users.py
docs/
```

Das Inventar wird in Tests immer über `tmp_path` isoliert; Tests schreiben nie
in das echte `.adfc-nc/`.
