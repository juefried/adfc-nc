# adfc-nc

Kommandozeilen-Werkzeug für wiederkehrende administrative Aufgaben der
ADFC-Nextcloud-Instanz. Der erste Befehl listet Benutzer mit Kennung, Name,
E-Mail-Adresse, letzter Anmeldung und Gruppen.

Die vollständige Dokumentation liegt unter [`docs/`](docs/index.md):

- [Installation](docs/installation.md)
- [Konfiguration](docs/configuration.md)
- [Befehle und Ausgabe](docs/usage.md)
- [Architektur](docs/architecture.md)
- [Entwicklung und Tests](docs/development.md)

## Voraussetzungen

- Python >= 3.13
- Zugang zur Nextcloud-Instanz `https://by.adfc-clouds.de`
- Admin-App-Passwort für die Provisioning-API

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

## Shell-Completion

PowerShell-Completion dauerhaft installieren:

```powershell
adfc-nc --install-completion
```

Danach die Shell neu starten. Nur anzeigen lässt sich das Skript mit
`adfc-nc --show-completion`.

## Konfiguration

`.env.example` nach `.env` kopieren und die Werte eintragen:

```powershell
Copy-Item .env.example .env
```

| Variable | Bedeutung |
| --- | --- |
| `ADFC_NC_BASE_URL` | Basis-URL der Instanz |
| `ADFC_NC_ADMIN_USER` | Admin-Benutzer für die Provisioning-API |
| `ADFC_NC_ADMIN_PASSWORD` | App-Passwort des Admin-Benutzers |
| `ADFC_NC_SHARE_USER` | Benutzer für Files-Sharing |
| `ADFC_NC_SHARE_PASSWORD` | App-Passwort des Share-Benutzers |
| `ADFC_NC_VERIFY_TLS` | TLS-Prüfung aktivieren (Standard: `true`) |
| `ADFC_NC_TIMEOUT_SECONDS` | HTTP-Timeout (Standard: `30`) |
| `ADFC_NC_CACHE_TTL_SECONDS` | Für künftige Cache-Nutzung reserviert |
| `ADFC_NC_STATE_DIR` | Verzeichnis für das lokale Inventar (Standard: `.adfc-nc`) |
| `ADFC_NC_RESOURCE_USER_PREFIX` | Präfix für Ressourcenbenutzer (Standard: `OC`) |

`.env` wird nicht versioniert. `.adfc-nc/` mit dem Inventar ebenfalls nicht.

## Benutzer auflisten

```powershell
adfc-nc users list
adfc-nc users list --json
adfc-nc users list --status disabled
adfc-nc users list --sort last-login
adfc-nc users list --search jdoe
adfc-nc users list --type resource
```

Alte und inaktive Benutzer finden:

```powershell
adfc-nc users stale --min-age-days 60 --inactive-days 60
adfc-nc users stale --min-age-days 60 --inactive-days 60 --json
adfc-nc users stale --min-age-days 60 --inactive-days 60 --include-unknown-age
adfc-nc users stale --type all
```

Alternativ ohne Installation des Pakets:

```powershell
$env:PYTHONPATH = "src"
python -m adfc_nc users list
```

### Spalten

- **Kennung**: Benutzer-ID
- **Typ**: `Benutzer` oder `Ressource`
- **Name**: Anzeigename
- **E-Mail**: E-Mail-Adresse
- **Letzte Anmeldung**: letzte erfolgreiche Authentifizierung in
  `Europe/Berlin`, sonst `nie`
- **Gruppen**: Anzeigenamen der Gruppen
- **Status**: `aktiv` oder `deaktiviert`

## Letzte Anmeldung und Clients

Der OCS-Wert `lastLogin` wird von Nextcloud bei Passwort- und
Token-/App-Passwort-Logins aktualisiert. Desktop- und Mobile-Clients
authentifizieren sich mit App-Passwörtern, ihre Anmeldungen sind also
enthalten. Die API liefert jedoch nur einen kombinierten Zeitstempel und
keine gerätegenaue Zuordnung. Für „nur Client“ oder einzelne Geräte wäre
zusätzlich ein Read-only-Zugriff auf `oc_authtoken` oder eine
Log-Auswertung nötig.

## Anlagedatum und lokales Inventar

Die OCS-API von Nextcloud 34 liefert kein Anlagedatum. Bekannt sind nur
Erst- und Letztlogin. Deshalb führt die CLI ein lokales Inventar unter
`ADFC_NC_STATE_DIR` (standardmäßig `.adfc-nc/inventory.sqlite3`):

```powershell
adfc-nc inventory sync
```

Das Inventar speichert die erste Sichtung eines Benutzers, Erst- und
Letztlogin sowie optional ein exaktes Anlagedatum aus einem späteren Import.
Für Benutzer, die beim ersten Sync bereits vorhanden waren, ist das Alter
ohne Login-Daten unbekannt. Für danach neu erscheinende Benutzer ist die
erste Sichtung eine belastbare Alters-Untergrenze.

`users stale` aktualisiert das Inventar automatisch. Bei mehreren
Administratoren sollte nur ein Host schreiben oder ein gemeinsames
`ADFC_NC_STATE_DIR` verwendet werden.

## Ressourcenbenutzer (OC*)

Benutzerkennungen mit dem Präfix `OC` gelten als Ressourcen- beziehungsweise
Dienstbenutzer. Sie melden sich häufig nie an und werden deshalb von
`users stale` standardmäßig nicht als inaktive Benutzer gemeldet. Die
Kennungen bleiben in `users list` sichtbar und tragen dort den Typ
`Ressource`.

Mit `--type all` werden Ressourcenbenutzer in die Stale-Abfrage einbezogen,
mit `--type resource` können sie gezielt geprüft werden. Das Präfix ist über
`ADFC_NC_RESOURCE_USER_PREFIX` konfigurierbar und wird
groß-/kleinschreibungssensitiv verglichen.

## Tests

```powershell
python -m pytest
```
