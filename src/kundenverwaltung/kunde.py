"""Die Kunde-Klasse und das ExportierbarMixin."""

from functools import cached_property, total_ordering

from .exceptions import (
    UngueltigeEmailError,
    UngueltigerBetragError,
    UngueltigerNameError,
)
from .komponenten import (
    Adresse,
    GeschaeftsDaten,
    GrosskundenDaten,
    InfoFaehig,
    PrivatDaten,
)
from .validierung import email_gueltig


@total_ordering
class Kunde:

    naechste_nummer = 1000
    GROSSKUNDE_GRENZE = 10000

    def __init__(self, name: str, email: str,
                 geschaefts_daten: "GeschaeftsDaten | None" = None,
                 private_daten: "PrivatDaten | None" = None,
                 großkunden_daten: "GrosskundenDaten | None" = None,
                 adresse: "Adresse | None" = None,
                 tags: list[str] | None = None) -> None:
        if not name or not name.strip():
            raise UngueltigerNameError(f"Name darf nicht leer sein, war: {name!r}")
        self.__name = name
        self.email = email
        self.geschaefts_daten = geschaefts_daten
        self.private_daten = private_daten
        self.großkunden_daten = großkunden_daten
        self.adresse = adresse
        self._umsatz = 0.0
        self._nummer = self.naechste_nummer
        Kunde.naechste_nummer += 1
        self._aktiv = True
        self._tags = tags if tags is not None else []

        # Polymorphe Verarbeitung (Woche 5): alles mit info() landet hier,
        # unabhaengig davon, ob es eine eigene Basisklasse hat oder nicht.
        self._info_komponenten: list[InfoFaehig] = [
            komponente for komponente in (private_daten, geschaefts_daten, großkunden_daten)
            if komponente is not None
        ]



    # ------------------------------------------------------------------
    # Properties (Getter/Setter)
    # ------------------------------------------------------------------
    @property
    def email(self)-> str:
        return self._email

    @email.setter
    def email(self, wert: str) -> None:
        if not email_gueltig(wert):
            raise UngueltigeEmailError(f"Ungültige E-Mail: {wert}")
        self._email = wert

    @property
    def name(self) -> str:
        return self.__name

    @property
    def umsatz(self) -> float:
        return self._umsatz

    @umsatz.setter
    def umsatz(self, wert: float) -> None:
        if wert < 0:
            raise UngueltigerBetragError(f"Umsätze müssen nicht-negativ sein. Wert: {wert}")
        # float(): Die Annotation sagt float, aber Python wandelt nicht von
        # selbst. Ohne den Aufruf haelt umsatz mal ein int, mal einen float —
        # je nachdem, wie zugewiesen wurde. Das schlaegt bis in die
        # CSV-Ausgabe durch ("1500" gegen "1500.0").
        self._umsatz = float(wert)

    @property
    def aktiv(self) -> bool:
        return self._aktiv

    @aktiv.setter
    def aktiv(self, wert: bool) -> None:
        if not isinstance(wert, bool):
            raise TypeError(f"aktiv erwartet bool, bekam {type(wert).__name__}: {wert!r}")
        self._aktiv = wert

    @property
    def tags(self) -> list[str]:
        return self._tags

    @property
    def nummer(self) -> int:
        return self._nummer

    @cached_property
    def risiko_score(self) -> float:
        """Wird beim ersten Zugriff berechnet und danach zwischengespeichert.

        `cached_property` legt das Ergebnis in `self.__dict__` ab. Ab dem
        zweiten Zugriff greift die normale Attributsuche und findet den Wert
        dort, bevor sie ueberhaupt bei der Property landet — die Berechnung
        laeuft also nur einmal.

        Folge: Der Wert altert. Aendert sich der Umsatz nach dem ersten
        Zugriff, bleibt der Score stehen. Belegen laesst sich das Caching
        ueber __dict__ statt ueber eine Stoppuhr.
        """
        score = 0.0
        if not self.aktiv:
            score += 50.0
        if self.umsatz < 100:
            score += 30.0
        elif self.umsatz > self.grosskunde_grenze():
            score -= 20.0

        if "@" in self.email and ".de" in self.email:
            score -= 10.0

        return max(0, score)

    # ------------------------------------------------------------------
    # Großkunden-Logik (delegiert an Komponenten statt an Vererbung)
    # ------------------------------------------------------------------
    def grosskunde_grenze(self) -> int:
        if self.großkunden_daten:
            return self.großkunden_daten.GROSSKUNDE_GRENZE
        if self.geschaefts_daten:
            return self.geschaefts_daten.GROSSKUNDE_GRENZE
        return Kunde.GROSSKUNDE_GRENZE

    def is_grosskunde(self) -> bool:
        return self.umsatz >= self.grosskunde_grenze()

    def status(self) -> str:
        if not self.aktiv:
            return "inaktiv"
        if self.is_grosskunde():
            return "Kunde ist ein Grosskunde"
        return "Kunde ist ein normaler Kunde"

    # ------------------------------------------------------------------
    # Darstellung (Woche 6, Montag)
    # ------------------------------------------------------------------
    def __str__(self) -> str:
        """Fuer Menschen: knappe Einzeiler-Identitaet fuer Logs und Tabellen.

        Bewusst ohne info() — das ist mehrzeilig und wuerde Name und Email
        ein zweites Mal ausgeben. info() bleibt die ausfuehrliche Ansicht,
        __str__ die knappe.
        """
        return f"{self.nummer} {self.name} <{self.email}> — {self.status()}"

    def __repr__(self) -> str:
        """Fuer Entwickler: eval-faehige Form fuer den Konstruktor-Teil.

        Gewaehlt, weil man so die Klasse sieht und die Werte, die ueber den
        Konstruktor vergeben wurden. Die Komponenten gehoeren dazu, weil sie
        selbst Konstruktorparameter sind. Bewusst nicht enthalten sind
        nummer (automatisch vergeben) und umsatz (erst nachtraeglich
        gesetzt) — sie wuerden die eval-Faehigkeit brechen. Damit ist
        eval(repr(k)) rekonstruierbar, aber nicht identisch: neue
        Kundennummer, Umsatz 0. Begruendung in notizen.md, Woche 6 Montag.
        """
        # Nur gesetzte Werte aufnehmen, damit die Zeile bei einfachen Kunden
        # kurz bleibt.
        teile = [repr(self.name), repr(self.email)]
        for feldname, wert in (
            ("geschaefts_daten", self.geschaefts_daten),
            ("private_daten", self.private_daten),
            ("großkunden_daten", self.großkunden_daten),
            ("adresse", self.adresse),
        ):
            if wert is not None:
                teile.append(f"{feldname}={wert!r}")
        if self._tags:
            teile.append(f"tags={self._tags!r}")
        return f"Kunde({', '.join(teile)})"

    # ------------------------------------------------------------------
    # Gleichheit und Hashing (Woche 6, Dienstag)
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        """Gleichheit ueber die Kundennummer.

        Zwei Objekte mit derselben Nummer sind derselbe Kunde, auch wenn sie
        im Speicher getrennt liegen — wie Gleichheit ueber einen
        Primaerschluessel in einer Datenbank.

        Der Parametertyp ist `object`, nicht `Kunde`, weil hier jeder Typ
        ankommen darf. Bei einem Fremdtyp wird `NotImplemented`
        zurueckgegeben (nicht: NotImplementedError geworfen). Python
        versucht daraufhin die gespiegelte Operation und faellt schliesslich
        auf den Identitaetsvergleich zurueck — Ergebnis False statt Absturz.
        """
        if not isinstance(other, Kunde):
            return NotImplemented
        return self.nummer == other.nummer


    def __hash__(self) -> int:
        """Hash konsistent zu __eq__ — beide stuetzen sich auf nummer.

        Regel: Was gleich ist, muss denselben Hash haben. Mengen und Dicts
        ordnen einen Wert anhand seines Hashs einem Fach zu und vergleichen
        per == nur innerhalb dieses Fachs. Bei abweichenden Hashes landen
        zwei gleiche Objekte in verschiedenen Faechern und werden nie
        miteinander verglichen — das Duplikat bliebe unbemerkt.

        Diese Methode ist zwingend, weil Python __hash__ automatisch auf None
        setzt, sobald eine Klasse __eq__ definiert. Ohne sie waere Kunde
        unhashbar.

        Gehasht wird ueber nummer, weil das read-only ist. Ueber umsatz zu
        hashen waere fatal: Nach einer Aenderung gehoerte das Objekt in ein
        anderes Fach, laege aber noch im alten — und waere in seiner eigenen
        Menge nicht mehr auffindbar.
        """
        return hash(self.nummer)

    # ------------------------------------------------------------------
    # Ordnung (Woche 6, Mittwoch)
    # ------------------------------------------------------------------
    def __lt__(self, other: object) -> bool:
        """Ordnung nach Umsatz, bei Gleichstand nach Kundennummer.

        Sortierkriterium ist der Umsatz — deshalb liefert sorted(kunden)
        ohne key-Argument die Umsatzreihenfolge.

        Die Kundennummer als zweites Kriterium ist kein Detail, sondern
        noetig, damit die Klasse widerspruchsfrei bleibt. @total_ordering
        baut die uebrigen Operatoren aus __lt__ UND __eq__ zusammen:

            a <= b   ->   (a < b) or (a == b)
            a >  b   ->   (not a < b) and (a != b)
            a >= b   ->   (not a < b)

        Der Dekorator setzt damit voraus, dass beide Methoden dieselbe
        Ordnung beschreiben. Mit "self.umsatz < other.umsatz" allein war das
        verletzt: Bei gleichem Umsatz sagte < "nicht kleiner", waehrend ==
        ueber die Nummer "nicht gleich" sagte — und aus diesen zwei Neins
        folgte gleichzeitig a > b UND b > a. Zwei Objekte, von denen jedes
        groesser als das andere war.

        Mit dem Tupel entscheidet bei Umsatzgleichstand die Nummer. Da die
        eindeutig ist, gilt zwischen zwei verschiedenen Kunden immer genau
        eines von <, > oder ==.

        Rest-Einschraenkung: Zwei Objekte mit gleicher Nummer, aber
        unterschiedlichem Umsatz waeren weiterhin widerspruechlich. Dieser
        Zustand ist im Modell ausgeschlossen — gleiche Nummer heisst
        derselbe Kunde.
        """
        if not isinstance(other, Kunde):
            return NotImplemented
        return (self.umsatz, self.nummer) < (other.umsatz, other.nummer)

    # ------------------------------------------------------------------
    # Öffentliche Methoden
    # ------------------------------------------------------------------
    def umsatz_hinzufügen(self, betrag:float) -> float:
        self.umsatz += betrag
        return self.umsatz

    def is_aktiv(self) -> bool:
        return self.aktiv

    def deaktivieren(self) -> None:
        self.aktiv = False

    # ------------------------------------------------------------------
    # Woche 5 Donnerstag: drei Haertungsvarianten nebeneinander.
    # info_lbyl() und info_eafp() sind Lern-/Vergleichscode, info() ist
    # die Variante, die bleibt.
    # ------------------------------------------------------------------

    # --- Variante 1: LBYL (Look Before You Leap) ---------------------
    # Fragt vorher, ob die Methode existiert. Faengt NUR den Fall
    # "Methode fehlt". Kracht info() intern, stuerzt es weiterhin ab.
    def info_lbyl(self) -> str:
        meldung = f"{self.name} ({self.email})"
        for komponente in self._info_komponenten:
            if hasattr(komponente, "info"):
                meldung += "\n" + komponente.info()
            else:
                meldung += f"\n[{type(komponente).__name__}: kein info()]"
        return meldung

    # --- Variante 2: EAFP (Easier to Ask Forgiveness than Permission) -
    # Ruft direkt auf und faengt den Fehler. Faengt mehr ab als noetig:
    # ein AttributeError AUS der Methode wird faelschlich als
    # "kein info()" gemeldet und versteckt so einen echten Bug.
    def info_eafp(self) -> str:
        meldung = f"{self.name} ({self.email})"
        for komponente in self._info_komponenten:
            try:
                meldung += "\n" + komponente.info()
            except AttributeError:
                meldung += f"\n[{type(komponente).__name__}: kein info()]"
        return meldung

    # --- Variante 3: Kombination (die bleibt) -------------------------
    # hasattr klaert "gibt es die Methode?", try/except klaert
    # "funktioniert der Aufruf?". Zwei verschiedene Marker, damit in der
    # Ausgabe sichtbar bleibt, welcher Fall vorlag.
    def info(self) -> str:
        meldung = f"{self.name} ({self.email})"
        for komponente in self._info_komponenten:
            name = type(komponente).__name__
            if not hasattr(komponente, "info"):
                meldung += f"\n[{name}: kein info()]"
                continue
            try:
                meldung += "\n" + komponente.info()
            except Exception as e:
                meldung += f"\n[{name}: info() fehlgeschlagen - {type(e).__name__}: {e}]"
        return meldung

    def komponente_hinzufuegen(self, komponente: InfoFaehig) -> None:
        """Duck Typing: jede Komponente mit info() ist willkommen, egal welcher Klasse."""
        self._info_komponenten.append(komponente)
