# Konfiguration

## .env-Datei

Die Einstellungen werden aus Umgebungsvariablen und aus einer `.env`-Datei im
aktuellen Arbeitsverzeichnis gelesen. Vorlage kopieren:

```powershell
Copy-Item .env.example .env
```

`.env` ist in `.gitignore` eingetragen und darf niemals versioniert werden.

## Variablen

| Variable | Pflicht | Standard | Bedeutung |
| --- | --- | --- | --- |
| `ADFC_NC_BASE_URL` | nein | `https://by.adfc-clouds.de` | Basis-URL der Instanz |
| `ADFC_NC_ADMIN_USER` | ja | – | Admin-Benutzer für die Provisioning-API |
| `ADFC_NC_ADMIN_PASSWORD` | ja | – | App-Passwort des Admin-Benutzers |
| `ADFC_NC_SHARE_USER` | nein | `OCMaster_LV_Nextcloud` | Benutzer für Files-Sharing |
| `ADFC_NC_SHARE_PASSWORD` | nein | leer | App-Passwort des Share-Benutzers |
| `ADFC_NC_VERIFY_TLS` | nein | `true` | TLS-Zertifikat der Instanz prüfen |
| `ADFC_NC_TIMEOUT_SECONDS` | nein | `30` | Timeout pro HTTP-Request |
| `ADFC_NC_CACHE_TTL_SECONDS` | nein | `3600` | Für künftige Cache-Nutzung reserviert |
| `ADFC_NC_STATE_DIR` | nein | `.adfc-nc` | Verzeichnis für das lokale Inventar |
| `ADFC_NC_RESOURCE_USER_PREFIX` | nein | `OC` | Präfix für Ressourcenbenutzer |

Hinweise:

- `ADFC_NC_ADMIN_PASSWORD` und `ADFC_NC_SHARE_PASSWORD` sind App-Passwörter,
  keine normalen Benutzerpasswörter.
- Die Share-Zugangsdaten werden von `users list` noch nicht verwendet. Sie
  sind für spätere Sharing-Befehle vorbereitet.
- `ADFC_NC_CACHE_TTL_SECONDS` hat derzeit keine Wirkung. Die aktuelle Version
  cached keine Antworten persistent.
- `ADFC_NC_STATE_DIR` enthält das lokale SQLite-Inventar. Das Verzeichnis wird
  beim ersten Zugriff angelegt und ist in `.gitignore` eingetragen. Es enthält
  Benutzerkennungen, Namen und E-Mail-Adressen und sollte entsprechend
  geschützt und gesichert werden.
- `ADFC_NC_RESOURCE_USER_PREFIX` legt fest, welche Kennungen als
  Ressourcenbenutzer gelten. Der Vergleich ist groß-/kleinschreibungssensitiv.
  Standard ist `OC`.

## Vorrangregel

Explizit gesetzte Umgebungsvariablen haben Vorrang vor Werten aus `.env`.
Fehlende optionale Werte werden durch die Standardwerte ersetzt. Unbekannte
Variablen werden ignoriert.

Beispiel für eine lokale `.env`:

```dotenv
ADFC_NC_BASE_URL=https://by.adfc-clouds.de
ADFC_NC_ADMIN_USER=admin
ADFC_NC_ADMIN_PASSWORD=app-passwort
ADFC_NC_VERIFY_TLS=true
ADFC_NC_TIMEOUT_SECONDS=30
ADFC_NC_STATE_DIR=.adfc-nc
ADFC_NC_RESOURCE_USER_PREFIX=OC
```

## Fehlende Pflichtwerte

Fehlt `ADFC_NC_ADMIN_USER` oder `ADFC_NC_ADMIN_PASSWORD`, bricht der Befehl mit
Exit-Code 2 ab:

```text
Konfiguration ungültig: admin_user, admin_password
```

Die Meldung nennt nur die betroffenen Felder, nicht die eingegebenen Werte.

## TLS

Die Zertifikatsprüfung ist standardmäßig aktiv. Ein Abschalten über
`ADFC_NC_VERIFY_TLS=false` ist nur für klar begründete Ausnahmefälle gedacht
und sollte nicht dauerhaft verwendet werden.

## Arbeitsverzeichnis

Die `.env`-Datei wird relativ zum aktuellen Arbeitsverzeichnis gesucht. Die
Befehle deshalb im Projektverzeichnis ausführen oder die Variablen explizit in
der Shell setzen.
