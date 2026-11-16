# Installation

## Voraussetzungen

- Python 3.13 oder neuer (getestet mit 3.13)
- Netzwerkzugriff auf `https://by.adfc-clouds.de`
- Admin-Zugang mit App-Passwort für die Provisioning-API
- Optional: App-Passwort des Share-Benutzers für spätere Sharing-Befehle

## Empfohlene Installation

Im Projektverzeichnis eine virtuelle Umgebung anlegen und aktivieren:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Danach Laufzeit- und Entwicklungsabhängigkeiten installieren:

```powershell
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` bindet `requirements.txt` per `-r` ein. Damit sind
Typer, httpx, pydantic-settings, python-dotenv und Rich sowie pytest, respx,
Ruff und Mypy installiert. `tzdata` ist ebenfalls enthalten, weil Windows keine
System-Zeitzonendatenbank für `zoneinfo` bereitstellt.

Anschließend das Paket editierbar installieren, damit der Befehl `adfc-nc`
verfügbar ist:

```powershell
python -m pip install -e .
```

## Installation prüfen

```powershell
adfc-nc --help
adfc-nc users list --help
```

Falls der Befehl `adfc-nc` nicht gefunden wird, ist das Skript-Verzeichnis der
Python-Installation nicht im `PATH`. Alternativ funktioniert der Modulaufruf:

```powershell
python -m adfc_nc --help
```

## Shell-Completion

PowerShell-Completion dauerhaft installieren:

```powershell
adfc-nc --install-completion
```

Danach die Shell neu starten. `python -m adfc_nc --install-completion` ist zu
vermeiden: Typer 0.27.3 schreibt dabei einen fehlerhaften Block mit dem
Variablennamen `$Env:_PYTHON _M ADFC_NC_COMPLETE`, der beim Shell-Start einen
Parser-Fehler verursacht. Ein bereits beschädigtes Profil lässt sich mit dem
korrigierten Block aus `scripts/adfc-nc-completion.ps1` reparieren.

Der Completion-Block darf im Profil nur einmal stehen. Mehrfache Einträge
entstehen, wenn `--install-completion` wiederholt ausgeführt wurde; die
Duplikate vor dem erneuten Eintragen entfernen.

## Keine Ausgabe bei Befehlen

Liefert `adfc-nc` plötzlich für alle Befehle – auch `adfc-nc --help` – keine
Ausgabe mehr, sind vermutlich Completion-Variablen aus einer abgebrochenen
Tab-Vervollständigung hängen geblieben. Typer behandelt den Aufruf dann als
Completion-Anfrage. Die aktuelle Session bereinigen:

```powershell
Remove-Item Env:_ADFC_NC_COMPLETE, Env:_TYPER_COMPLETE_ARGS, Env:_TYPER_COMPLETE_WORD_TO_COMPLETE -ErrorAction SilentlyContinue
```

Danach funktioniert `adfc-nc --help` wieder. Ein Neustart der Shell hilft
ebenfalls. `scripts/adfc-nc-completion.ps1` setzt die Variablen in
`try/finally` zurück, damit ein Abbruch sie nicht mehr hinterlässt.

## Ohne Paketinstallation arbeiten

Für Entwicklung und Tests kann das Paket auch direkt aus `src` geladen werden:

```powershell
$env:PYTHONPATH = "src"
python -m adfc_nc users list
```

## Abhängigkeiten aktualisieren

Neue Laufzeitbibliotheken gehören in `requirements.txt`, neue
Entwicklungsbibliotheken in `requirements-dev.txt`. Versionen werden exakt
gepinnt. Nach einer Änderung:

```powershell
python -m pip install -r requirements-dev.txt
```

## Deinstallation

```powershell
python -m pip uninstall adfc-nc
```

Die virtuelle Umgebung kann anschließend durch Löschen des Verzeichnisses
`.venv` entfernt werden.
