"""Fehlertypen der Nextcloud-Anbindung."""


class NextcloudError(Exception):
    """Basisklasse für Fehler bei der Nextcloud-Kommunikation."""


class AuthenticationError(NextcloudError):
    """Die Zugangsdaten wurden von der Instanz abgelehnt."""


class OCSResponseError(NextcloudError):
    """Die OCS-API meldet einen fachlichen Fehler."""


class RateLimitError(NextcloudError):
    """Die Instanz hat das Rate Limit trotz Wartezeit nicht freigegeben."""


class UnexpectedResponseError(NextcloudError):
    """Die Antwort entspricht nicht dem erwarteten OCS-Format."""
