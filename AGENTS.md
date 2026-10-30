# AGENTS.md

Leitfaden für KI-Agenten und Mitentwickler in diesem Repository.
Diese Datei ist ein Review-Entwurf. Mit `[Vorschlag]` markierte Punkte sind
noch nicht bestätigt.

## Projekt

Kommandozeilen-Werkzeug (CLI) für wiederkehrende administrative Aufgaben der
ADFC-Nextcloud-Instanz, z. B. Benutzer, Gruppen, Quotas, Shares und Apps.
Die CLI soll Administration reproduzierbar, skriptbar und weniger
fehleranfällig machen als manuelle Klicks in der Weboberfläche.

## Technische Leitentscheidungen

- Sprache: Python >= 3.13 (lokal verfügbar: 3.13.14 und 3.14.7)
- Zielinstanz: ADFC-Nextcloud, aktuell Version 34
- CLI-Framework: Typer `[Vorschlag]`
- HTTP-Client: httpx `[Vorschlag]` (die Alt-Skripte nutzen `requests`)
- Konfiguration: `pydantic-settings`, Werte aus Umgebungsvariablen und `.env`
- Tests: pytest, HTTP-Mocking mit respx `[Vorschlag]`
- Lint/Format: ruff; Typen: mypy (strict) `[Vorschlag]`
- Paket-/Umgebungsverwaltung: uv `[Vorschlag]` (aktuell nicht installiert;
  Alternative: venv + pip)
- Abhängigkeiten: `requirements.txt` (Laufzeit) und `requirements-dev.txt`
  (Entwicklung, Tests, Lint, Typen); exakte Pins mit `==`

Referenzimplementierung für API-Aufrufe (nur lesen, nicht importieren):
`C:\Users\jue\IdeaProjects\ADFCByCloud`. Die dortigen Skripte nutzen die OCS
Provisioning API und die Files-Sharing API bereits erfolgreich.

Begründung Typer: gute Typprüfung, automatische Hilfe, Unterbefehle passen zur
ressourcenorientierten Struktur (`users`, `groups`, ...). Falls das Team Click
oder argparse bevorzugt, hier anpassen.

## Projektstruktur

```
adfc-nc/
├─ AGENTS.md
├─ README.md
├─ docs/                   # Nutzer- und Entwicklerdokumentation
├─ pyproject.toml
├─ requirements.txt        # Laufzeitabhängigkeiten
├─ requirements-dev.txt    # -r requirements.txt + Tests/Lint/Typen
├─ .env.example            # dokumentiert benötigte Variablen, keine Secrets
├─ .gitignore
├─ src/adfc_nc/
│  ├─ __init__.py
│  ├─ __main__.py          # python -m adfc_nc
│  ├─ cli.py               # Typer-App, Registrierung der Befehlsgruppen
│  ├─ config.py            # Settings, Validierung, Env-Mapping
│  ├─ inventory.py         # lokales SQLite-Inventar
│  ├─ output.py            # Ausgabe als Tabelle / JSON
│  ├─ nextcloud/
│  │  ├─ client.py         # HTTP-Client, Auth, Retries, Fehlerabbildung
│  │  ├─ users.py
│  │  ├─ groups.py
│  │  └─ errors.py
│  └─ commands/            # dünne CLI-Schicht je Ressource
│     ├─ common.py         # gemeinsame Fehler-/Exit-Code-Behandlung
│     ├─ users.py
│     └─ inventory.py
└─ tests/
   ├─ unit/
   └─ integration/         # nur mit gesetzten Env-Variablen, nie standardmäßig
```

Neue Fachlogik gehört unter `src/adfc_nc/nextcloud/`, nicht in die
CLI-Befehle. CLI-Befehle bleiben dünn: Argumente prüfen, Fachfunktion
aufrufen, Ergebnis ausgeben.

## Abhängigkeiten

- Laufzeitbibliotheken stehen in `requirements.txt`,
  Entwicklungsabhängigkeiten in `requirements-dev.txt` (dort wird
  `requirements.txt` per `-r` eingebunden).
- Versionen exakt pinnen (`==`), damit Installationen reproduzierbar sind.
- Neue Libraries nur aufnehmen, wenn sie tatsächlich benötigt werden, und
  immer in der passenden Requirements-Datei pflegen.
- Installation der Entwicklungsumgebung:
  `python -m pip install -r requirements-dev.txt`
- Keine Bibliothek ad hoc installieren, ohne sie vorher in der passenden
  Requirements-Datei einzutragen.

## Nextcloud-Zugriff

Bestätigt aus `ADFCByCloud`. Die CLI spricht ausschließlich per HTTPS mit der
OCS-API; kein `occ` und kein SSH.

- Instanz/Basis-URL: `https://by.adfc-clouds.de`
- Provisioning-Basis: `https://by.adfc-clouds.de/ocs/v2.php/cloud`
- Benutzerdetails (empfohlen für Listen):
  `GET /cloud/users/details` liefert alle Benutzer mit `id`, `displayname`,
  `email`, `enabled`, `groups`, `firstLoginTimestamp`, `lastLoginTimestamp`
  und `lastLogin`. Ergänzend: `GET /cloud/users/recent` (sortiert nach letztem
  Login) und `GET /cloud/users/disabled`.
- Gruppendetails: `GET /cloud/groups/details` liefert `id` und `displayname`.
- Files-Sharing:
  `https://by.adfc-clouds.de/ocs/v2.php/apps/files_sharing/api/v1/shares`
- Pflicht-Header bei jedem Request:
  `OCS-APIRequest: true` und `Accept: application/json`
- Query-Parameter `format=json` verwenden (die API liefert sonst XML).
- Authentifizierung: HTTP Basic Auth. Es gibt zwei Identitäten:
  - **Admin**: Provisioning, Benutzer- und Gruppenverwaltung.
  - **Share-Benutzer** (`OCMaster_LV_Nextcloud`): Anlegen von Shares, weil
    Shares im Namen des authentifizierten Benutzers entstehen.
- Zugangsdaten ausschließlich über Umgebungsvariablen/`.env`:
  `ADFC_NC_BASE_URL`, `ADFC_NC_ADMIN_USER`, `ADFC_NC_ADMIN_PASSWORD`,
  `ADFC_NC_SHARE_USER`, `ADFC_NC_SHARE_PASSWORD`, `ADFC_NC_STATE_DIR`,
  `ADFC_NC_RESOURCE_USER_PREFIX`.
  In den Alt-Skripten heißen die Passwörter `admin_password` bzw.
  `share_password`; es sind App-Passwörter, keine Benutzerpasswörter.
- Antwort prüfen: `ocs.meta.status == "ok"` (bzw. Statuscode 100/200), sonst
  Fehler werfen. `ocs.data` ist die Nutzlast.
- Paging: `limit`/`offset` (Referenz nutzt 500). Abbruch bei leerer Seite,
  wiederholter Seite oder `len(batch) < limit`.
- Rate Limit: HTTP 429 respektieren und `Retry-After` abwarten; kein hektisches
  Wiederholen. Timeout 30 s, TLS-Prüfung aktiv.
- `lastLoginTimestamp` ist in Sekunden, `lastLogin` in Millisekunden. Vor der
  Umrechnung normalisieren (Werte >= 10^10 gelten als Millisekunden) und in
  `Europe/Berlin` ausgeben. `0` bedeutet „nie angemeldet“.
- `lastLogin` wird bei Passwort- und Token-/App-Passwort-Logins aktualisiert.
  Client-Anmeldungen (Desktop/Mobile) sind damit enthalten. Die OCS-API liefert
  aber nur einen kombinierten Wert, keine Trennung Web/Client und keine
  Gerätezuordnung. Für „nur Client“ wären `oc_authtoken` (`name`,
  `last_activity`) oder Logs nötig, die nicht über OCS erreichbar sind.
- Die OCS-API liefert **kein Anlagedatum**. `oc_users`/`oc_accounts` haben
  keine `created`-Spalte, `IUser` kennt nur Erst- und Letztlogin. Altersabfragen
  dürfen deshalb keine exakte Schöpfungszeit vortäuschen.
- `firstLoginTimestamp` ist in Sekunden. `-1` bedeutet „vor Nextcloud 31“,
  `0` „nie angemeldet“. Positive Erst-/Letztlogins sind Untergrenzen für das
  Kontalter.
- Das lokale Inventar unter `ADFC_NC_STATE_DIR` (Standard `.adfc-nc/`) speichert
  `first_seen_at`, `first_seen_source`, Login-Zeiten und optional exaktes
  `created_at`. Beim ersten Sync werden bestehende Benutzer als `baseline`
  markiert; ihre erste Sichtung ist keine Alters-Untergrenze.
- `users stale` filtert nach Mindestalter und Inaktivität. Unbekanntes Alter
  wird separat gezählt und nur mit `--include-unknown-age` einbezogen.
- Kennungen mit dem Präfix `ADFC_NC_RESOURCE_USER_PREFIX` (Standard `OC`) sind
  Ressourcen-/Dienstbenutzer. Sie melden sich häufig nie an und sind deshalb
  in `users stale` standardmäßig ausgeschlossen (`--type user`). `--type all`
  nimmt sie auf, `--type resource` prüft nur sie. `users list` zeigt sie mit
  Typ `Ressource`.
- Deaktivierte Benutzer (`enabled == false`) bei allgemeinen Auswertungen
  standardmäßig ausschließen. `users list` zeigt bewusst alle Benutzer inklusive
  Statusspalte, sofern kein `--status`-Filter gesetzt ist.
- GET-Antworten dürfen kurzfristig gecacht werden (Referenz: 1 h), aber nur
  instanz- und benutzergebunden. Schreibende Aufrufe nie cachen.

Aktuell implementiert: `users list`, `users stale`, `inventory sync`.
Nächster Ausbauschritt `[Vorschlag]`: `users create|disable`,
`groups list|create|add-member`, `shares create`, `quota set`.

## Konventionen

### Code

- Vollständige Typannotationen, auch für Rückgabewerte.
- Keine Kommentare im Code; sprechende Namen und Docstrings an öffentlichen
  Funktionen.
- Fehler als eigene Exceptions in `nextcloud/errors.py`, in der CLI in
  verständliche Meldungen und definierte Exit-Codes übersetzen.
- Keine stillen `except`-Blöcke; Fehler nicht verschlucken.
- Ausgabe: menschenlesbar per Default, `--json` für Skripte.
- Destruktive Befehle (`delete`, `disable`, `quota set`) unterstützen
  `--dry-run` und verlangen ohne `--yes` eine Bestätigung. `[Vorschlag]`
- Befehle sollen idempotent sein, wo fachlich möglich.

### Sicherheit

- Niemals Secrets, App-Passwörter oder Tokens loggen oder committen.
- `.env` ist ignoriert; `.env.example` enthält nur Platzhalter.
- Keine Zugangsdaten in Fehlermeldungen oder Stacktraces ausgeben.
- Das Inventar unter `ADFC_NC_STATE_DIR` enthält personenbezogene Daten
  (Kennungen, Namen, E-Mail-Adressen). Es ist ignoriert, zu schützen und zu
  sichern.
- TLS-Prüfung standardmäßig aktiv; keine pauschale Deaktivierung.
- Vor produktiven Änderungen: `--dry-run` und Testinstanz.

### Tests

- Unit-Tests mocken HTTP, keine echten Nextcloud-Aufrufe.
- Inventar-Tests verwenden ein temporäres Verzeichnis, nie das echte
  `.adfc-nc/`.
- Integrationstests laufen nur, wenn `ADFC_NC_TEST_*`-Variablen gesetzt sind,
  und werden sonst übersprungen.
- Jeder neue Befehl benötigt mindestens einen Erfolgs- und einen Fehlerfall.

### Git

- Kleine, thematisch getrennte Commits.
- Commit-Nachrichten auf Deutsch oder Englisch, aber einheitlich. `[Vorschlag:
  Deutsch, Imperativ]`
- Keine generierten Dateien, Caches oder Secrets committen.

## Definition of Done

Vor Abschluss einer Aufgabe müssen alle Punkte erfüllt sein:

- Neue Abhängigkeiten sind in `requirements.txt` bzw. `requirements-dev.txt`
  eingetragen, und `python -m pip install -r requirements-dev.txt` läuft durch.
- Alle Kommandos im folgenden Block laufen ohne Fehler.

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
```

Zusätzlich: Hilfe-Ausgabe (`--help`) für neue Befehle funktioniert und ist im
README sowie unter `docs/` dokumentiert.

## Offene Review-Punkte

1. CLI-Framework Typer bestätigen oder Click/argparse?
2. uv einführen oder bei venv + pip bleiben?
3. Erster Befehls-Scope (siehe oben)?
4. Dateiname: `AGENTS.md` (Standard für Agenten) oder explizit `agent.md`?
