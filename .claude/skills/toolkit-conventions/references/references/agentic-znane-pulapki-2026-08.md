# Migawka: znane, nienaprawione pułapki stosu agentowego, sierpień 2026

| | |
|---|---|
| **Data zebrania** | 2026-08-22 |
| **Data przeglądu** | 2026-11-22 (3 miesiące — część tych pozycji zniknie wraz z wersją biblioteki) |
| **Zebrał** | przegląd publikacji ekosystemu, sierpień 2026 |
| **Weryfikacja niezależna** | **częściowa** — pozycje 1, 2 i 6 potwierdzone w kodzie trzech realnych projektów; pozycje 3, 4, 5 i 7 pochodzą z publikacji ekosystemu i **nie były odtworzone** |
| **Zasada grounding** | to nie jest lista błędów bibliotek do zgłoszenia u autorów. To lista **znanych, powtarzalnych sposobów, w jakie te systemy się psują** — do sprawdzenia w audycie, zanim zacznie się szukać przyczyny od zera |

**Ta migawka nie zastępuje konwencji.** Zasady projektowania systemów
agentowych opisuje skill `agentic-apps` i jego bank; tutaj są wyłącznie
konkretne pułapki z konkretnym objawem.

---

## Po co osobny plik na pułapki

Audyt, który za każdym razem zaczyna od zera, znajduje to, co łatwe. Objawy
w systemach agentowych są mylące — „agent nie widzi kontekstu" ma co najmniej
pięć różnych przyczyn, z których każda wymaga innego dowodu. Lista znanych
pułapek zamienia diagnozę w **odhaczanie hipotez w kolejności taniości**.

Zasada użycia: dla każdego objawu przejdź listę **zanim** postawisz własną
hipotezę. Twoja jest prawdopodobnie trafna, ale kosztuje więcej.

---

## 1. Dwa runtime'y agenta = dwa magazyny stanu

**Objaw:** agent raz widzi kontekst, raz nie; to samo pytanie działa w jednym
widoku, w drugim nie.

**Przyczyna:** produkt ma graf w dwóch technologiach — na przykład część
w Pythonie, część w TypeScript — a każdy runtime ma własny checkpointer i własny
wątek. Zachowanie jest wtedy **poprawne**: pytanie trafiło do drugiego runtime'u,
który nigdy nie widział tamtego stanu.

**Dowód:** wypisz wszystkie miejsca, które kompilują graf albo tworzą
checkpointer. Więcej niż jedno bez zapisanej decyzji o właścicielu stanu = ta
pułapka.

**Potwierdzone w kodzie floty:** tak, w jednym projekcie.

## 2. Własna implementacja interfejsu frameworka

**Objaw:** przy podbiciu wersji biblioteki coś przestaje działać bez zmiany
w kodzie produktu.

**Przyczyna:** klasa dziedzicząca po klasie bazowej frameworka
(`BaseCheckpointSaver` i pokrewne) bierze kontrakt tej klasy **na zawsze**.
Gdy zależność jest zadeklarowana bez górnej granicy, kontrakt może się zmienić
przy zwykłej instalacji.

**Dowód:** `grep` po klasach dziedziczących z przestrzeni frameworka; sprawdzenie
w dokumentacji przez serwer dokumentacji, czy dla tego magazynu nie ma gotowego
adaptera.

**Potwierdzone w kodzie floty:** tak — 235 linii własnego checkpointera przy
zależności bez górnej granicy, w projekcie po migracji na inny magazyn.

## 3. Checkpointer w pamięci procesu na produkcji

**Objaw:** restart procesu kasuje wszystkie trwające wątki agenta.

**Przyczyna:** magazyn stanu trzymany w pamięci przechodzi testy i wdrożenie,
a rozjeżdża się dopiero przy pierwszym restarcie poda. To najczęściej opisywany
błąd pierwszego wdrożenia w publikacjach ekosystemu 2026.

**Dowód:** `grep` po nazwie klasy magazynu w kodzie produkcyjnym, nie w testach.

**Potwierdzone w kodzie floty:** nie — we flocie występuje wyłącznie w testach,
co jest użyciem poprawnym.

## 4. Pomylenie magazynu wątku z pamięcią długoterminową

**Objaw:** agent „zapomina" rzeczy między rozmowami albo przeciwnie — ciągnie
do nowej rozmowy stan starej.

**Przyczyna:** checkpointer daje pamięć **w obrębie wątku**, kluczowaną
identyfikatorem wątku. Pamięć przekrojowa to osobny mechanizm. Publikacje
ekosystemu wskazują to jako najczęstsze pomylenie pojęć w tej klasie systemów.

**Dowód:** czy istnieje magazyn pamięci długoterminowej osobny od checkpointera;
jeśli nie, a produkt obiecuje pamiętanie między rozmowami — to ta pułapka.

**Potwierdzone w kodzie floty:** nie sprawdzano.

## 5. Ewolucja schematu stanu bez migracji

**Objaw:** po wdrożeniu część trwających wątków przestaje się wznawiać.

**Przyczyna:** dopisanie pola do schematu stanu wymaga jawnej migracji
zapisanych checkpointów. Stare wątki nie deserializują się i **giną cicho**.

**Dowód:** czy zmianie schematu stanu towarzyszy migracja; czy istnieje
wersjonowanie schematu w zapisanym checkpoincie.

**Potwierdzone w kodzie floty:** nie sprawdzano.

## 6. Rozdęcie stanu przez artefakty binarne

**Objaw:** magazyn checkpointów rośnie nieproporcjonalnie do liczby rozmów.

**Przyczyna:** duży plik trzymany w stanie grafu jest **zapisywany przy każdym
kroku**. Dziesięć kroków z załącznikiem w stanie to dziesięć kopii załącznika.

**Dowód:** rozmiar tabeli checkpointów wobec liczby wątków; typy pól stanu.

**Potwierdzone w kodzie floty:** częściowo — jeden projekt ma to zaadresowane
regułą „bajty poza rozmową", inny nie był sprawdzany.

## 7. Przeciek kontekstu przy częściowej aktualizacji stanu

**Objaw:** wznowiony wątek widzi wartości, których w tamtym momencie nie było.

**Przyczyna:** przy częściowej aktualizacji pola mogą odziedziczyć wartość
z bieżącej głowy wątku zamiast z zamierzonej migawki. Opisane w analizie
ekosystemu z lutego 2026.

**Dowód:** wznowienie z historycznego checkpointu i porównanie pól z zapisem.

**Potwierdzone w kodzie floty:** nie sprawdzano.

## 8. Warstwa dostarczania do interfejsu jako osobna klasa awarii

**Objaw:** przebieg w wątku grafu jest **kompletny**, narzędzie zawołane,
odpowiedź poprawna — a interfejs nie pokazuje nic albo pokazuje część.

**Przyczyna:** to nie jest problem agenta ani kontraktu domeny. To warstwa
dostarczania zdarzeń do widoku. Mylenie tych dwóch klas kosztuje najwięcej
czasu w diagnozie, bo objaw jest identyczny z brakiem kontekstu.

**Dowód rozstrzygający:** asercja na stanie wątku grafu (twardo) osobno od
asercji na tym, co widać w interfejsie (miękko). Jeśli wątek jest kompletny,
a widok pusty — to ta klasa.

**Potwierdzone w kodzie floty:** tak, udokumentowane w rejestrze wad jednego
z projektów wraz z testem rozdzielającym obie asercje.

---

## Świadome luki tej migawki

- **Pozycje 3, 4, 5 i 7 nie zostały odtworzone** — pochodzą z publikacji
  ekosystemu i mają status hipotezy do sprawdzenia, nie faktu o flocie.
- **Brak numerów wersji.** Część tych pułapek zniknie wraz z wydaniem
  biblioteki; wersję sprawdza się w dokumentacji, nie tutaj
  (`dependency-currency.md` §5).
- **Lista nie jest kompletna** i nie może być. Rośnie z każdego postmortemu —
  tak samo jak checklista audytu (`rules-as-gates.md`, sekcja o zapadce).

## Źródła

Pozycje 3–7 pochodzą z przeglądu publikacji ekosystemu z sierpnia 2026,
w szczególności materiałów o warstwie trwałości i postmortemów wdrożeń.
Pozycje 1, 2, 6 i 8 pochodzą z bezpośredniego przeglądu kodu trzech projektów
i są w tych repozytoriach udokumentowane.
