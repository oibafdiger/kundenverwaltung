"""Kundenliste: ein Container, der sich wie ein eingebauter anfuehlt."""

from collections.abc import Iterator
from typing import overload

from .kunde import Kunde


class Kundenliste:
    """Eine Sammlung von Kunden, die sich wie ein eingebauter Container anfuehlt.

    Komposition, nicht Vererbung: Die Kunden liegen in einem Feld, die Klasse
    erbt NICHT von list. Dieselbe Entscheidung wie in Woche 4 — beim Erben
    kaemen saemtliche list-Methoden mit, auch die, die hier nichts zu suchen
    haben (sort, clear, insert, __iadd__ ...). So bleibt hinzufuegen() der
    einzige Schreibzugriff.

    Vier Dunder machen den Container aus: __len__, __getitem__, __contains__
    und __iter__. Die letzten beiden waeren nicht zwingend noetig — was sie
    trotzdem beitragen, steht bei ihnen.
    """

    def __init__(self, kunden: "list[Kunde] | None" = None) -> None:
        # list(...) macht eine flache Kopie: die Liste ist neu, die Kunden
        # darin sind dieselben Objekte. Ohne die Kopie zeigten Aufrufer und
        # Kundenliste auf dasselbe Listenobjekt — wer die uebergebene Liste
        # anfasst, veraenderte sonst die Kundenliste gleich mit.
        self._kunden: list[Kunde] = list(kunden) if kunden is not None else []


    def hinzufuegen(self, kunde: Kunde) -> None:
        """Haengt einen Kunden hinten an.

        Bewusst der einzige Schreibzugriff: Wer Kunden aufnehmen will, geht
        hier durch. Beim Erben von list waeren daneben append, extend,
        insert, __iadd__ und Konsorten offen — genau das sollte die
        Komposition verhindern.
        """
        self._kunden.append(kunde)

    def __len__(self) -> int:
        return len(self._kunden)

    @overload
    def __getitem__(self, index: int) -> Kunde: ...

    @overload
    def __getitem__(self, index: slice) -> "Kundenliste": ...

    def __getitem__(self, index: "int | slice") -> "Kunde | Kundenliste":
        """Einzelzugriff liefert einen Kunden, ein Slice eine neue Kundenliste.

        Variante b: Ein Ausschnitt aus einer Kundenliste ist wieder eine
        Kundenliste — so verhalten sich auch die eingebauten Typen
        (`list[1:3]` ist eine list, `str[1:3]` ein str). Ohne die
        Fallunterscheidung kaeme bei `liste[1:3]` eine nackte list zurueck,
        und am Ausschnitt waere keine Methode dieser Klasse mehr verfuegbar.

        Der IndexError bei zu grossem Index kommt von self._kunden und bleibt
        damit erhalten — er ist das Stoppsignal fuer die for-Schleife, die
        ohne __iter__ ueber das alte Sequenzprotokoll laeuft.
        """
        if isinstance(index, slice):
            return Kundenliste(self._kunden[index])
        return self._kunden[index]


    def __contains__(self, item: object) -> bool:
        """Mitgliedschaft per ==, also ueber die Kundennummer.

        Was bringt ein eigenes __contains__, wenn `in` auch ohne funktioniert?
        Zwei Dinge. Erstens laesst sich die Pruefung frei definieren — etwa
        Sonderfaelle abfangen oder auch eine Kundennummer statt eines Kunden
        annehmen. Zweitens, und gewichtiger: Geschwindigkeit. Der Fallback
        ist immer ein linearer Durchlauf mit == ueber alle Elemente; ein
        eigenes __contains__ koennte intern ein set der Kundennummern pflegen
        und in einem Schritt antworten (dasselbe Fach-Prinzip wie bei
        __hash__). Diese Fassung delegiert noch an list.__contains__ und tut
        damit dasselbe wie der Fallback — als Ausgangspunkt in Ordnung, aber
        noch kein Gewinn.

        Der Parametertyp ist object, weil `x in liste` mit jedem Typ gefragt
        werden darf. Ein isinstance-Wachposten ist dabei nicht noetig:
        list.__contains__ vergleicht mit ==, und Kunde.__eq__ liefert fuer
        Fremdtypen NotImplemented, woraufhin Python auf den
        Identitaetsvergleich zurueckfaellt — Ergebnis False.

        NotImplemented waere hier ausserdem grundsaetzlich falsch: Es gibt
        keinen Spiegelpartner zu __contains__, den Python fragen koennte, und
        der Rueckgabewert laeuft durch bool(). bool(NotImplemented) ist True
        — `"ein String" in liste` haette also True geliefert.
        """
        return item in self._kunden

    def __iter__(self) -> Iterator[Kunde]:
        """Liefert bei jedem Aufruf einen frischen Iterator ueber die Kunden.

        Was bringt __iter__, wenn die for-Schleife auch ohne lief? Zweierlei.
        Erstens Kontrolle: Man bestimmt selbst, was in welcher Reihenfolge
        geliefert wird — etwa nur jeden zweiten Kunden oder nur die aktiven —
        statt an die Integer-Indizes 0, 1, 2, … gebunden zu sein.

        Zweitens Reichweite: Der __getitem__-Fallback funktioniert nur, wenn
        ein Container ueberhaupt sinnvoll ueber ganze Zahlen erreichbar ist.
        Eine mengen- oder dict-artige Sammlung hat das nicht und waere ohne
        __iter__ gar nicht iterierbar.

        Drei Varianten koennen hier stehen und sind alle korrekt:

            a) return iter(self._kunden)                 1 Zeile
            b) return KundenlisteIterator(self._kunden)  1 Zeile + eigene Klasse
            c) yield from self._kunden                   1 Zeile (Generator)

        Geblieben ist (a). Die Iteration dieser Klasse IST die Iteration ihrer
        Liste — dann soll der Code genau das sagen. (b) steht als Lerncode
        unten in der Datei: von Hand gebaut, aber hier nicht verdrahtet, weil
        eine eigene Klasse nur lohnt, wenn der Iterator mehr kann als
        mitzaehlen. (c) waere die Wahl, sobald beim Durchlaufen gefiltert oder
        umgeformt werden soll — dafuer muesste sich an der Signatur nichts
        aendern, nur der Rumpf.
        """
        return iter(self._kunden)


    def __repr__(self) -> str:
        return f"Kundenliste({self._kunden!r})"

class KundenlisteIterator:
    """Haelt die Position beim Durchlaufen einer Kundenliste.

    LERNCODE — nicht verdrahtet. Kundenliste.__iter__ delegiert bewusst an
    iter(self._kunden); diese Klasse baut nach, was dabei intern passiert.
    Eine eigene Iterator-Klasse lohnt erst, wenn der Iterator mehr kann als
    mitzaehlen: eigene Methoden (peek), Filterlogik mit Zustand, oder wenn er
    unabhaengig vom Container weitergereicht werden soll.

    Arbeitsteilung: Die Kundenliste weiss, WAS drin ist. Der Iterator weiss,
    WO man gerade steht. Deshalb sind es zwei Objekte und nicht eines.

    Eine for-Schleife ist im Kern das hier:

        it = iter(liste)          # ruft liste.__iter__()  -> Iterator
        while True:
            try:
                k = next(it)      # ruft it.__next__()
            except StopIteration:
                break
            ...

    __iter__ wird EINMAL aufgerufen, __next__ immer wieder.
    """

    def __init__(self, kunden: list[Kunde]) -> None:
        self._kunden = kunden
        self._position = 0

    def __iter__(self) -> "KundenlisteIterator":
        """Ein Iterator ist selbst iterierbar und gibt sich selbst zurueck.

        Klingt zirkulaer, ist aber noetig: for ruft auf ALLEM zuerst iter()
        auf, auch auf etwas, das bereits ein Iterator ist. Ohne diese Methode
        liesse sich der Iterator nicht direkt in eine for-Schleife stecken.
        """
        return self

    def __next__(self) -> Kunde:
        """Liefert das naechste Element, sonst StopIteration.

        StopIteration ist kein Fehler, sondern das regulaere Ende-Signal —
        die for-Schleife faengt es selbst ab. Dieselbe Rolle wie der
        IndexError beim alten Sequenzprotokoll.

        Geprueft wird per Laengenvergleich (LBYL) statt per
        try/except IndexError (EAFP). Grund: try/except faenge JEDEN
        IndexError, auch einen aus ganz anderer Ursache — der Iterator
        meldete dann "fertig", obwohl in Wirklichkeit ein Bug vorliegt.
        Dasselbe Muster wie bei info_eafp(). Und len() ist billig.

        Die Position wird VOR dem return hochgezaehlt. Danach ginge es nicht:
        return beendet die Methode sofort, der Iterator lieferte ewig
        dasselbe Element.
        """
        if self._position >= len(self._kunden):
            raise StopIteration
        kunde = self._kunden[self._position]
        self._position += 1
        return kunde
