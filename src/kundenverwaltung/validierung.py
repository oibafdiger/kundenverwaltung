"""Pruefungen, die kein Objekt brauchen.

Herausgeloest aus Kunde (SRP): email_gueltig war eine @staticmethod,
die `self` nie angefasst hat — ein ablesbares Zeichen dafuer, dass sie
in der falschen Klasse stand."""


# ============================================================================
# Validierung (Woche 8, Kuer: SRP)
# Aufgabe: Eingaben pruefen, ohne ein Objekt dafuer zu brauchen
# ============================================================================
def email_gueltig(email: str) -> bool:
    """Prueft, ob eine Adresse die noetigen Bestandteile hat.

    Frueher Kunde.email_gueltig als @staticmethod. Sie hat `self` nie
    angefasst — ein ablesbares Zeichen, dass sie in der falschen Klasse
    stand: Sie braucht keinen Kunden, sondern einen String.

    Bewusst eine Modulfunktion und keine Klasse mit einer einzigen statischen
    Methode. Eine solche Klasse waere eine Funktion mit Zeremonie drumherum.

    Auch bewusst kein Mixin: Ein Mixin nutzt die Daten des Gastes, die
    Pruefung laeuft aber im Setter — also BEVOR der Wert gespeichert wird.
    Zu dem Zeitpunkt gibt es noch kein self.email. Und danach ist die Frage
    sinnlos, weil eine ungueltige Adresse gar nicht erst hineinkommt.
    Dieselbe Ueberlegung, an der in Woche 7 das ValidierbarMixin gescheitert
    ist.
    """
    if "@" not in email:
        return False

    teile = email.split("@")
    if len(teile) != 2:
        return False

    lokaler_teil, domain = teile

    if len(lokaler_teil) < 1:
        return False

    if "." not in domain:
        return False

    if len(domain.split(".")[-1]) < 2:
        return False

    return True
