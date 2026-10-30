# adfc-nc Dokumentation

`adfc-nc` ist ein Kommandozeilen-Werkzeug für wiederkehrende administrative
Aufgaben der ADFC-Nextcloud-Instanz. Die aktuelle Version spricht
ausschließlich die OCS-API über HTTPS an – kein SSH, kein `occ`.

Die Instanz läuft auf Nextcloud 34. Zugangsdaten werden über
Umgebungsvariablen beziehungsweise eine lokale `.env`-Datei bereitgestellt.

## Funktionsumfang

- `users list`: listet Benutzer mit Kennung, Typ, Anzeigename, E-Mail-Adresse,
  letzter Anmeldung, Gruppen und Aktivierungsstatus.
- `users stale`: findet alte, inaktive Benutzer anhand von Mindestalter und
  Inaktivität. Ressourcenbenutzer mit `OC*`-Kennung sind standardmäßig
  ausgeschlossen.
- `groups search`: durchsucht Gruppen nach Namen oder Teilstring und wertet die
  Mitglieder samt letzter Anmeldung aus.
- `groups stale`: zeigt Deaktivierungs-Kandidaten in gefundenen Gruppen nach
  derselben Logik wie `users stale`.
- `inventory sync`: aktualisiert das lokale Inventar für Altersabfragen.
- Ausgabe als Tabelle für die Administration oder als JSON für Skripte.
- Filter nach Suchbegriff und Status, Sortierung nach Kennung, letztem Login,
  Alter oder Inaktivität.
- Fehlerabbildung für Authentifizierung, OCS-Fehler, Rate Limits und
  Netzwerkprobleme.
- Paging über die OCS-API mit Schutz gegen wiederholte Seiten.
- Keine Ausgabe von Passwörtern oder Tokens in Meldungen.

## Schnellstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
Copy-Item .env.example .env
```

Werte in `.env` eintragen, danach:

```powershell
adfc-nc users list
```

## Dokumentation

- [Installation](installation.md)
- [Konfiguration](configuration.md)
- [Befehle und Ausgabe](usage.md)
- [Architektur](architecture.md)
- [Entwicklung und Tests](development.md)

## Aktuelle Grenzen

- Es gibt noch keine schreibenden Befehle wie `users create` oder
  `users disable`.
- Die OCS-API liefert kein exaktes Anlagedatum. Altersabfragen nutzen ein
  lokales Inventar und Login-Untergrenzen; Details stehen unter
  [Architektur](architecture.md).
- Die OCS-API liefert nur einen kombinierten Login-Zeitstempel. Eine
  getrennte Auswertung „nur Nextcloud-Client“ oder einzelner Geräte ist damit
  nicht möglich.
