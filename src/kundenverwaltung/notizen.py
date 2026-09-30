"""Die Notizen zu Kunden — die Sammlung, nicht ihre Ablage.

Herausgeloest aus persistenz (Woche 12, Mittwoch). Der Grund ist zunaechst
technisch: speicher.py braucht NotizSpeicher, und persistenz.py braucht
speicher.py. Stuende NotizSpeicher weiter in persistenz, waere das ein
Importkreis.

Der technische Zwang deckt sich hier mit der Sache. NotizSpeicher ist ein
Container wie Kundenliste — er haelt Notizen und verteilt sie an Kunden. Dass
er daneben auch noch Dateien schrieb, war P3 in REFACTORING.md.
"""

from typing import TYPE_CHECKING, Any

from .exceptions import DateiInhaltError
from .komponenten import Notiz

if TYPE_CHECKING:
    from .kundenliste import Kundenliste

# ============================================================================
# Notizspeicher (Woche 9, Dienstag)
# Aufgabe: Notizen aufbewahren, getrennt von den Kunden
# ============================================================================
class NotizSpeicher:
    """Notizen zu Kunden, in einer eigenen Datei.

    WARUM GETRENNT
        Eine Notiz sagt nichts darueber aus, WER ein Kunde ist — sie haengt
        an ihm. Technisch sichtbar wird das an der Registry: Die drei
        Fachkomponenten sind dort eingetragen, Notiz ist es bewusst nicht
        (Duck Typing, Woche 5). Dieses Kriterium entscheidet seit Woche 9,
        wo etwas gespeichert wird.

        In der Datenbanksprache von Phase 2: eine 1:n-Beziehung, zweite
        Tabelle, Fremdschluessel auf die Kundennummer.

    DER FREMDSCHLUESSEL
        Genau deshalb musste die Kundennummer den Round-Trip ueberleben
        (Montag). Ohne stabile Nummer koennte nichts auf einen Kunden zeigen.

    DIE FALLE MIT DEN SCHLUESSELN
        JSON kennt nur Strings als Objektschluessel. Schreibt man
        {1000: [...]} hinein, kommt {"1000": [...]} heraus — lautlos. Ein
        Nachschlagen mit der int-Nummer ginge danach ins Leere. Deshalb
        wandelt _laden() die Schluessel beim Lesen zurueck nach int, und
        als_dict() macht die Umwandlung beim Schreiben ausdruecklich statt
        sie json zu ueberlassen.

    WAS NOCH OFFEN IST
        Zwei Dateien koennen auseinanderlaufen. Wird ein Kunde geloescht,
        bleiben seine Notizen als Waisen liegen; auf_kunden_verteilen()
        meldet sie deshalb zurueck, statt sie stillschweigend zu schlucken.
        Und zwei Dateien bedeuten zwei Schreibvorgaenge: Bricht das Programm
        dazwischen ab, passen sie nicht mehr zusammen. Donnerstag macht EINE
        Datei atomar — atomar ueber zwei hinweg ist eine andere Nummer und
        bleibt hier bewusst ungeloest.
    """

    FORMAT_VERSION = 1

    def __init__(self, notizen: dict[int, list[Notiz]] | None = None) -> None:
        self._notizen: dict[int, list[Notiz]] = notizen if notizen is not None else {}

    def __len__(self) -> int:
        """Anzahl der Notizen insgesamt, nicht der Kunden mit Notizen."""
        return sum(len(liste) for liste in self._notizen.values())

    def __repr__(self) -> str:
        return f"NotizSpeicher({len(self)} Notizen zu {len(self._notizen)} Kunden)"

    def fuer(self, nummer: int) -> list[Notiz]:
        """Die Notizen eines Kunden — leere Liste, wenn er keine hat."""
        return list(self._notizen.get(nummer, []))

    @classmethod
    def von_kunden(cls, kunden: "Kundenliste") -> "NotizSpeicher":
        """Sammelt die Notizen aus einer Kundenliste ein.

        Erkennungsmerkmal ist isinstance(Notiz) und nicht "steht nicht in der
        Registry": Ein Objekt, das weder registriert noch eine Notiz ist,
        soll nicht stillschweigend in der Notizdatei landen. Es faellt
        weiterhin heraus — das ist die bekannte Restluecke von
        komponente_hinzufuegen(), und sie soll sichtbar bleiben statt hier
        halb zugedeckt zu werden.
        """
        gesammelt: dict[int, list[Notiz]] = {}
        for kunde in kunden:
            eigene = [k for k in kunde._info_komponenten if isinstance(k, Notiz)]
            if eigene:
                gesammelt[kunde.nummer] = eigene
        return cls(gesammelt)

    def auf_kunden_verteilen(self, kunden: "Kundenliste") -> list[int]:
        """Haengt die Notizen wieder an die passenden Kunden.

        Liefert die Kundennummern zurueck, zu denen es keinen Kunden (mehr)
        gibt — die Waisen aus dem Docstring der Klasse. Bewusst ein
        Rueckgabewert und kein Fehler: Ob Waisen ein Problem sind, weiss nur
        der Aufrufer. Ein Reparaturwerkzeug will sie sehen, ein normaler
        Programmstart darf sie ignorieren. Was diese Klasse nicht tun darf,
        ist so zu tun, als gaebe es sie nicht.
        """
        vorhanden = {kunde.nummer: kunde for kunde in kunden}
        waisen = []
        for nummer, notizen in self._notizen.items():
            kunde = vorhanden.get(nummer)
            if kunde is None:
                waisen.append(nummer)
                continue
            for notiz in notizen:
                kunde.komponente_hinzufuegen(notiz)
        return sorted(waisen)

    def waisen_uebernehmen(self, quelle: "NotizSpeicher", nummern: list[int]) -> None:
        """Holt die Notizen der Waisen aus einem anderen Speicher herueber.

        Review-Fix 15.09.2026: von_kunden() sammelt nur ein, was an Kunden
        haengt. Waisen haengen an niemandem und waeren beim Speichern
        verloren. Diese Methode gibt sie aus dem geladenen Speicher zurueck.

        Hat inzwischen ein Kunde diese Nummer (nur ueber nummer= moeglich,
        weil der Zaehler ueber Waisen-Nummern gezogen wird), werden die
        Notizen zusammengelegt. Es geht in keinem Fall etwas verloren.
        """
        for nummer in nummern:
            self._notizen[nummer] = self._notizen.get(nummer, []) + quelle.fuer(nummer)

    def als_dict(self) -> dict[str, Any]:
        """Wie bei Kundenliste: dict mit Versionsfeld, nicht nackte Daten.

        str(nummer) ist ausdruecklich hingeschrieben, obwohl json dieselbe
        Umwandlung von sich aus vornaehme. Der Grund ist Ehrlichkeit: Beim
        Laden MUSS zurueckgewandelt werden, und das sieht nur, wer weiss,
        dass die Umwandlung stattfindet. Eine lautlose Konvertierung, die man
        beim Lesen von Hand rueckgaengig macht, ist eine Falle.
        """
        return {
            "version": NotizSpeicher.FORMAT_VERSION,
            "notizen": {
                str(nummer): [notiz.als_dict() for notiz in notizen]
                for nummer, notizen in self._notizen.items()
            },
        }

    @classmethod
    def aus_dict(cls, daten: dict[str, Any]) -> "NotizSpeicher":
        if not isinstance(daten, dict):
            raise DateiInhaltError(
                f"Erwartet wird ein JSON-Objekt, gefunden wurde "
                f"{type(daten).__name__}"
            )

        version = daten.get("version")
        if version != cls.FORMAT_VERSION:
            raise DateiInhaltError(
                f"Unbekannte Formatversion {version!r} im Notizspeicher, "
                f"erwartet wird {cls.FORMAT_VERSION}"
            )

        gelesen: dict[int, list[Notiz]] = {}
        for schluessel, eintraege in daten.get("notizen", {}).items():
            try:
                nummer = int(schluessel)
            except ValueError as e:
                raise DateiInhaltError(
                    f"Kundennummer im Notizspeicher ist keine Zahl: {schluessel!r}"
                ) from e
            gelesen[nummer] = [Notiz.aus_dict(eintrag) for eintrag in eintraege]
        return cls(gelesen)
