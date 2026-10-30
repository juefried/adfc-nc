# Befehle und Ausgabe

## Übersicht

```text
adfc-nc users list [OPTIONS]
adfc-nc users stale [OPTIONS]
adfc-nc groups search SUCHBEGRIFF... [OPTIONS]
adfc-nc groups stale SUCHBEGRIFF... [OPTIONS]
adfc-nc inventory sync
```

`users list` ruft alle Benutzer der Instanz ab und zeigt sie als Tabelle.
`users stale` filtert zusätzlich nach Alter und Inaktivität. Mit `--json`
steht jeweils eine maschinenlesbare Ausgabe für Skripte zur Verfügung.
`groups search` durchsucht Gruppen und listet deren Mitglieder. `groups stale`
zeigt nur Mitglieder, die nach derselben Logik wie `users stale`
Deaktivierungs-Kandidaten sind.

## Benutzer auflisten

### Optionen

| Option | Werte | Standard | Bedeutung |
| --- | --- | --- | --- |
| `--json` | – | aus | Ausgabe als JSON statt Tabelle |
| `--search` | Text | leer | Serverseitige Suche nach Kennung oder Name |
| `--sort` | `id`, `last-login` | `id` | Sortierung der Ausgabe |
| `--status` | `all`, `active`, `disabled` | `all` | Filter nach Aktivierungsstatus |
| `--type` | `all`, `user`, `resource` | `all` | Benutzer oder Ressourcenbenutzer |
| `--help` | – | – | Hilfe anzeigen |

## Beispiele

Alle Benutzer als Tabelle:

```powershell
adfc-nc users list
```

Alle Benutzer als JSON:

```powershell
adfc-nc users list --json
```

Nur deaktivierte Benutzer:

```powershell
adfc-nc users list --status disabled
```

Nach letzter Anmeldung sortieren, neueste zuerst:

```powershell
adfc-nc users list --sort last-login
```

Suche nach einem Benutzer:

```powershell
adfc-nc users list --search jdoe
```

Nur Ressourcenbenutzer:

```powershell
adfc-nc users list --type resource
```

Ohne installiertes Paket:

```powershell
$env:PYTHONPATH = "src"
python -m adfc_nc users list
```

## Gruppen durchsuchen und auswerten

`groups search` sucht Gruppen über Kennung und Anzeigename. Ein oder mehrere
Suchbegriffe werden als Argumente übergeben. Jeder Suchbegriff erzeugt einen
eigenen Report.

```powershell
adfc-nc groups search Augsburg
adfc-nc groups search KV_Augsburg --json
adfc-nc groups search Augsburg Muenchen --type all
```

### Optionen: groups search

| Option | Werte | Standard | Bedeutung |
| --- | --- | --- | --- |
| `SUCHBEGRIFF...` | Text | Pflicht | Vollständiger Gruppenname oder Teilstring |
| `--type` | `user`, `all`, `resource` | `user` | Benutzer oder Ressourcenbenutzer |
| `--json` | – | aus | Ausgabe als JSON statt Tabelle |
| `--help` | – | – | Hilfe anzeigen |

Mit dem Standard `--type user` werden technische Benutzer mit dem Präfix `OC`
ausgeblendet. `--type all` nimmt sie auf, `--type resource` zeigt ausschließlich
sie.

### Suchlogik

Die Suche arbeitet lokal auf der vollständigen Gruppenliste. Unterstriche und
Leerzeichen werden normalisiert, Groß-/Kleinschreibung wird ignoriert. Dadurch
findet `Augsburg` alle Gruppen, die den Begriff in der Kennung oder im
Anzeigenamen enthalten:

- `KV_Augsburg_Land`
- `KV_Augsburg_Stadt`
- `LV_Augsburg`

Die Namensbestandteile `LV_` und `KV_` sind dabei keine Sonderfälle, sondern
Teil der normalisierten Kennung. Weitere durch Unterstriche getrennte
Bestandteile werden genauso berücksichtigt. Auch `KV Augsburg` findet die
entsprechenden `KV_Augsburg_*`-Gruppen.

### Tabelle

Die Ausgabe besteht aus einer Benutzertabelle und einer Gruppenübersicht. Jeder
Benutzer erscheint genau einmal. Die Gruppenübersicht referenziert Mitglieder
nur über ihre Kennung:

| Spalte | Inhalt |
| --- | --- |
| Gruppe | Gruppenkennung |
| Anzeigename | Anzeigename der Gruppe |
| Anzahl | Anzahl der enthaltenen Benutzer |
| Mitglieder-Kennungen | Benutzer-IDs, durch Komma getrennt |

Die Benutzertabelle enthält Kennung, Typ, Name, E-Mail, letzte Anmeldung,
`Angemeldet` (`ja`/`nie`) und Status. Gehört ein Benutzer mehreren gefundenen
Gruppen an, wird er nicht mehrfach ausgegeben; die Zuordnung ergibt sich aus den
Mitglieder-Kennungen der Gruppen.

### JSON: groups search

`groups search --json` liefert eine Liste von Report-Objekten, eins pro
Suchbegriff:

```json
[
  {
    "query": "Augsburg",
    "type": "user",
    "groups": [
      {
        "id": "KV_Augsburg_Stadt",
        "display_name": "KV Augsburg Stadt",
        "member_count": 1,
        "member_ids": ["jdoe"]
      }
    ],
    "users": [
      {
        "id": "jdoe",
        "display_name": "Jane Doe",
        "email": "jane@example.org",
        "enabled": true,
        "is_resource": false,
        "type": "user",
        "last_login": "2026-10-01T12:00:00+02:00",
        "never_logged_in": false
      }
    ]
  }
]
```

- `groups` enthält die gefundenen Gruppen samt Mitgliederzahl und Kennungen.
- `users` enthält jeden beteiligten Benutzer genau einmal.
- Die Zuordnung erfolgt ausschließlich über `member_ids` in den Gruppen. Es gibt
  weder eine `memberships`-Liste noch eine erneute Gruppenliste je Benutzer.
- `last_login` ist `null` und `never_logged_in` ist `true`, wenn kein Login
  bekannt ist.

## Deaktivierungs-Kandidaten in Gruppen

`groups stale` verwendet exakt dieselbe Filterlogik wie `users stale`. Es zeigt
nur Benutzer, die als Kandidaten für eine Deaktivierung gelten, und nur Gruppen
mit mindestens einem Kandidaten.

```powershell
adfc-nc groups stale Augsburg
adfc-nc groups stale Augsburg --min-age-days 90 --inactive-days 30
adfc-nc groups stale Augsburg --include-unknown-age --json
adfc-nc groups stale Augsburg --status active --type all
```

### Optionen: groups stale

| Option | Werte | Standard | Bedeutung |
| --- | --- | --- | --- |
| `SUCHBEGRIFF...` | Text | Pflicht | Vollständiger Gruppenname oder Teilstring |
| `--min-age-days` | Ganzzahl >= 1 | `60` | Mindestalter in Tagen |
| `--inactive-days` | Ganzzahl >= 1 | `60` | Mindestinaktivität in Tagen |
| `--include-unknown-age` | – | aus | Benutzer mit unbekanntem Alter einbeziehen |
| `--status` | `all`, `active`, `disabled` | `all` | Filter nach Aktivierungsstatus |
| `--type` | `user`, `all`, `resource` | `user` | Benutzer oder Ressourcenbenutzer |
| `--json` | – | aus | Ausgabe als JSON statt Tabelle |
| `--help` | – | – | Hilfe anzeigen |

Die Tabelle wird um `Angelegt`, `Alter` und `Inaktiv` ergänzt. Die JSON-Ausgabe
enthält zusätzlich ein `criteria`-Objekt mit den verwendeten Schwellwerten sowie
je Benutzer `age_days`, `age_basis`, `age_is_lower_bound`, `age_bound_at`,
`inactive_days` und `first_login`. Die Referenzierung über `member_ids` bleibt
unverändert.

## Help bei unvollständigen Befehlen

Fehlt ein Unterbefehl oder ein Pflichtargument, zeigt die CLI die Hilfe mit
einem zusätzlichen Hinweis auf `--help` und endet mit Exit-Code `2`. Das gilt
auch, wenn nur Optionen ohne den Pflichtparameter angegeben wurden, zum
Beispiel `adfc-nc groups search --json`.

Vollständige Befehle werden normal ausgeführt. Unbekannte Optionen und ungültige
Werte bleiben normale Nutzungsfehler.

## Inventar synchronisieren

Das lokale Inventar speichert die erste Sichtung eines Benutzers und die
Login-Zeiten. Es wird für Altersabfragen benötigt:

```powershell
adfc-nc inventory sync
```

`users stale` und `groups stale` aktualisieren das Inventar ebenfalls
automatisch. Der Ablageort ist über `ADFC_NC_STATE_DIR` konfigurierbar,
Standard ist `.adfc-nc/inventory.sqlite3`.

## Alte und inaktive Benutzer

```powershell
adfc-nc users stale --min-age-days 60 --inactive-days 60
adfc-nc users stale --min-age-days 90 --inactive-days 30 --status active
adfc-nc users stale --min-age-days 60 --inactive-days 60 --json
adfc-nc users stale --min-age-days 60 --inactive-days 60 --include-unknown-age
```

### Optionen

| Option | Werte | Standard | Bedeutung |
| --- | --- | --- | --- |
| `--min-age-days` | Ganzzahl >= 1 | `60` | Mindestalter in Tagen |
| `--inactive-days` | Ganzzahl >= 1 | `60` | Mindestinaktivität in Tagen |
| `--include-unknown-age` | – | aus | Benutzer mit unbekanntem Alter einbeziehen |
| `--status` | `all`, `active`, `disabled` | `all` | Filter nach Aktivierungsstatus |
| `--type` | `all`, `user`, `resource` | `user` | Ressourcenbenutzer einbeziehen oder nur diese prüfen |
| `--sort` | `inactive`, `age`, `id` | `inactive` | Sortierung |
| `--search` | Text | leer | Suche nach Kennung, Name oder E-Mail (lokal) |
| `--json` | – | aus | Ausgabe als JSON |

### Filterlogik

Ein Benutzer erscheint, wenn beide Bedingungen erfüllt sind:

- **Alter**: `age_days >= min-age-days` oder das Konto existierte bereits vor
  Nextcloud 31 (`pre_nc31`).
- **Inaktivität**: `inactive_days >= inactive-days` oder der Benutzer hat sich
  nie angemeldet.

Benutzer mit unbekanntem Alter werden standardmäßig nicht ausgegeben. Die CLI
nennt am Ende die Anzahl der ausgeschlossenen Benutzer. Mit
`--include-unknown-age` erscheinen sie mit `age_basis = unknown`.

Ressourcenbenutzer mit dem Präfix `OC` werden standardmäßig nicht in die
Stale-Abfrage einbezogen, weil sie sich häufig nie anmelden. `--type all`
nimmt sie auf, `--type resource` prüft ausschließlich Ressourcenbenutzer.

Das Alter kann exakt, eine Untergrenze oder unbekannt sein:

| `age_basis` | Bedeutung |
| --- | --- |
| `exact` | Exaktes Anlagedatum aus dem Inventar |
| `first_seen` | Erste Sichtung durch die CLI |
| `first_login` | Konto existierte mindestens seit dem Erstlogin |
| `last_login` | Konto existierte mindestens seit dem Letztlogin |
| `pre_nc31` | Konto existierte bereits vor Nextcloud 31 |
| `unknown` | Kein belastbarer Alterswert |

### Tabellenausgabe

| Spalte | Inhalt |
| --- | --- |
| Kennung | Benutzer-ID |
| Typ | `Benutzer` oder `Ressource` |
| Name | Anzeigename |
| E-Mail | E-Mail-Adresse oder `-` |
| Angelegt | Exaktes Datum, `≤ Datum` oder `unbekannt` |
| Alter | `≥ 60 T`, `vor NC31` oder `unbekannt` |
| Letzte Anmeldung | Zeitpunkt in `Europe/Berlin` oder `nie` |
| Inaktiv | Tage seit der letzten Anmeldung oder `nie` |
| Gruppen | Anzeigenamen, durch Komma getrennt, oder `-` |
| Status | `aktiv` oder `deaktiviert` |

### JSON-Ausgabe

```json
[
  {
    "id": "jdoe",
    "display_name": "Jane Doe",
    "email": "jane@example.org",
    "enabled": true,
    "is_resource": false,
    "type": "user",
    "created_at": null,
    "first_seen_at": "2026-08-01T10:00:00+00:00",
    "first_seen_source": "first_seen",
    "age_days": 75,
    "age_basis": "first_login",
    "age_is_lower_bound": true,
    "age_bound_at": "2026-08-15T12:00:00+02:00",
    "first_login": "2026-08-15T12:00:00+02:00",
    "last_login": "2026-08-20T12:00:00+02:00",
    "inactive_days": 70,
    "never_logged_in": false,
    "groups": []
  }
]
```

`created_at` ist nur bei einem exakten Import gesetzt. `age_is_lower_bound`
zeigt an, dass der Wert eine Untergrenze ist. `age_bound_at` ist der Zeitpunkt,
aus dem die Untergrenze abgeleitet wurde.

## Ressourcenbenutzer

Kennungen mit dem Präfix `OC` gelten als Ressourcen- beziehungsweise
Dienstbenutzer. Sie werden in `users list` mit dem Typ `Ressource` angezeigt.
In `users stale` sind sie standardmäßig ausgeschlossen, weil fehlende Logins
bei diesen Konten erwartbar sind.

```powershell
adfc-nc users list --type resource
adfc-nc users stale --type all
adfc-nc users stale --type resource
```

Das Präfix ist über `ADFC_NC_RESOURCE_USER_PREFIX` konfigurierbar und wird
groß-/kleinschreibungssensitiv geprüft.

## Shell-Completion

Die CLI unterstützt Completion für PowerShell und andere Shells:

```powershell
adfc-nc --install-completion
```

Das Skript wird in die Shell-Konfiguration eingetragen; danach die Shell neu
starten. `adfc-nc --show-completion` gibt das Skript nur aus, ohne es zu
installieren.

## Listentabelle

| Spalte | Inhalt |
| --- | --- |
| Kennung | Benutzer-ID |
| Typ | `Benutzer` oder `Ressource` |
| Name | Anzeigename |
| E-Mail | E-Mail-Adresse oder `-` |
| Letzte Anmeldung | Zeitpunkt in `Europe/Berlin` oder `nie` |
| Gruppen | Anzeigenamen, durch Komma getrennt, oder `-` |
| Status | `aktiv` oder `deaktiviert` |

Beispiel mit fiktiven Daten:

```text
┌─────────┬────────────┬───────────────────┬─────────────────────┬────────────────┬─────────────┐
│ Kennung │ Name       │ E-Mail            │ Letzte Anmeldung    │ Gruppen        │ Status      │
├─────────┼────────────┼───────────────────┼─────────────────────┼────────────────┼─────────────┤
│ jdoe    │ Jane Doe   │ jane@example.org  │ 2026-10-01 12:00:00 │ Administratoren│ aktiv       │
│ msmith  │ Max Smith  │ max@example.org   │ nie                 │ Mitglieder     │ deaktiviert │
└─────────┴────────────┴───────────────────┴─────────────────────┴────────────────┴─────────────┘
```

## JSON-Ausgabe

Die Ausgabe ist eine Liste von Objekten:

```json
[
  {
    "id": "jdoe",
    "display_name": "Jane Doe",
    "email": "jane@example.org",
    "enabled": true,
    "is_resource": false,
    "type": "user",
    "last_login": "2026-10-01T12:00:00+02:00",
    "groups": [
      {
        "id": "admins",
        "display_name": "Administratoren"
      }
    ]
  }
]
```

Feldbedeutung:

| Feld | Typ | Bedeutung |
| --- | --- | --- |
| `id` | String | Benutzerkennung |
| `display_name` | String | Anzeigename |
| `email` | String oder `null` | E-Mail-Adresse |
| `enabled` | Boolean | Benutzer ist aktiviert |
| `is_resource` | Boolean | Kennung beginnt mit dem Ressourcenpräfix |
| `type` | String | `user` oder `resource` |
| `last_login` | String oder `null` | ISO-8601-Zeitpunkt mit Zeitzone; `null` = nie angemeldet |
| `groups` | Liste | Gruppen mit Kennung und Anzeigename |

## Liste: Filter und Sortierung

- `--search` wird an die OCS-API übergeben. Die Suche erfolgt damit
  serverseitig.
- `--status` wird nach dem Abruf lokal angewendet.
- `--sort id` sortiert aufsteigend nach Kennung, Groß-/Kleinschreibung wird
  ignoriert.
- `--sort last-login` sortiert absteigend nach letzter Anmeldung. Benutzer
  ohne Anmeldung stehen am Ende.

## Exit-Codes

| Code | Bedeutung |
| --- | --- |
| `0` | Erfolg |
| `1` | OCS-, Netzwerk- oder Antwortfehler |
| `2` | Ungültige Konfiguration oder ungültige CLI-Nutzung |
| `3` | Authentifizierung abgelehnt |
| `4` | Rate Limit wurde nicht rechtzeitig aufgehoben |

Fehlermeldungen gehen auf `stderr` und enthalten keine Passwörter oder Tokens.

## Grenzen

- Die Liste wird vollständig abgerufen; eine Begrenzung der Trefferzahl gibt es
  noch nicht.
- Schreibende Befehle wie Anlegen, Deaktivieren oder Löschen sind noch nicht
  implementiert.
- Die OCS-API liefert kein exaktes Anlagedatum. `users stale` arbeitet deshalb
  mit exakten Inventarwerten, Untergrenzen oder `unbekannt`.
- Beim ersten Inventar-Sync vorhandene Benutzer ohne Login-Daten haben
  unbekanntes Alter. Erst danach neu erscheinende Benutzer erhalten eine
  Alters-Untergrenze aus der ersten Sichtung.
- Der Login-Zeitpunkt ist ein kombinierter Wert für Web- und Client-Anmeldungen.
  Eine gerätegenaue Client-Auswertung ist über OCS nicht möglich.
