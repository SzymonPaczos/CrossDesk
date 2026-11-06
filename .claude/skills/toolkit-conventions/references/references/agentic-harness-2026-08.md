# Migawka: co harness agentowy już ma, sierpień 2026

Uzupełnienie 2026-11-05: domyślny LangGraph w tabelach nie jest regułą
obowiązującą każdy projekt. Dobór runtime'u i obecne punkty odniesienia
opisuje [materiał z listopada](agentic-runtime-2026-11.md). Pozostała treść
jest historyczną listą do sprawdzenia przed wyborem narzędzia.

| | |
|---|---|
| **Data zebrania** | 2026-08-21 |
| **Data przeglądu** | 2026-11-21 (3 miesiące — biblioteki tej klasy zmieniają API szybciej niż stack ogólny) |
| **Zebrał** | właściciel repozytorium, jako przegląd ekosystemu |
| **Weryfikacja niezależna** | **nie przeprowadzono** — nazwy pakietów, numery wersji i statusy integracji nie były sprawdzane w dokumentacji przy wnoszeniu do toolkitu |
| **Zasada grounding** | ta migawka służy **jednemu celowi**: żeby przed napisaniem własnej infrastruktury agentowej dało się sprawdzić, czy nie istnieje ona już w harnessie. Nie jest rekomendacją zakupu ani listą rzeczy do wdrożenia |

**Ta migawka nie zastępuje konwencji.** Reguły składania stacku opisuje
`stack-composition.md`, dopuszczanie narzędzi — `tool-adoption-and-measurement.md`.
Gdy migawka i konwencja się rozjeżdżają, obowiązuje konwencja.

---

## Po co ta lista istnieje

Systemy agentowe mają wąską, powtarzalną infrastrukturę: trzeba gdzieś trzymać
stan wątku, gdzieś pamięć długoterminową, jakoś dowieźć zdarzenia do interfejsu,
jakoś podłączyć narzędzia, jakoś zobaczyć, co się stało. Każdą z tych rzeczy da
się napisać samemu w dwieście linii — i właśnie dlatego się je pisze, zamiast
sprawdzić, że są.

Koszt własnej implementacji nie jest jednorazowy. Pisząc checkpointer, bierzesz
na siebie kontrakt interfejsu biblioteki na zawsze: przy każdym podbiciu wersji
musisz sprawdzić, czy klasa bazowa nie zmieniła sygnatur. Adapter utrzymywany
u źródła robi to za Ciebie.

## Warstwy i co w nich już jest

| Warstwa | Odpowiedzialność | Gotowe elementy |
|---|---|---|
| Orkiestracja | graf, stan, pętle, równoległość, punkty wstrzymania | LangGraph — `StateGraph`, przerwania, wznawianie |
| Trwałość stanu wątku | checkpointy, wznowienie po restarcie | `langgraph-checkpoint-postgres`, `langgraph-checkpoint-sqlite` |
| Pamięć długoterminowa | wiedza przeżywająca wątek | store po stronie orkiestratora, osobno od checkpointera |
| Harness długich zadań | planowanie, podagenci, kompresja kontekstu, filesystem | Deep Agents |
| Wzorce wieloagentowe | delegacja, przekazywanie sterowania | `langgraph-supervisor`, `langgraph-swarm` |
| Narzędzia | dostęp do API, baz, systemu plików | MCP + adaptery MCP dla frameworka |
| Agent ↔ interfejs | zdarzenia, stan współdzielony, zatwierdzanie akcji | AG-UI jako protokół, CopilotKit jako implementacja |
| Interfejs generowany | tabele, formularze, dashboardy opisane przez agenta | OpenUI (deklaratywnie), A2UI, Open Generative UI (swobodnie, w piaskownicy) |
| Obserwowalność | ślady, koszty, opóźnienia, ewaluacja | LangSmith, Langfuse |

**Obserwowalność jest sugestią, nie wymogiem.** Postawienie serwera śladów
kosztuje czas i zwykle konto u dostawcy, więc jej brak nie jest usterką —
jest **decyzją**, która ma być zapisana. Audyt raportuje brak tej warstwy
i nie blokuje na nim. Tani punkt pośredni, gdy nie ma na co postawić serwera:
strukturalne logi z identyfikatorem przebiegu, po którym da się złożyć ślad
z plików. To wystarcza do diagnozy i nie wymaga niczego poza biblioteką,
którą projekt i tak ma.

## Zalecenia wprost

Poprzednia tabela mówi, **co istnieje**. Ta mówi, **czego używać** — jednym
zdaniem na warstwę, bez kodów i skrótów. Audyt raportuje odchylenia zdaniem
w tej samej formie, nie identyfikatorem.

| Warstwa | Używaj | Zamiast | Dlaczego |
|---|---|---|---|
| Warstwa widoku | **React** | własnych komponentów od zera | dojrzała biblioteka, komponenty przenoszą się między frameworkami bez przepisywania |
| Framework aplikacji | **Next** | dwóch frameworków obok siebie | dwie warstwy widoku w jednym produkcie to dwa razy tyle utrzymania i dwa razy tyle miejsc na rozjazd |
| Baza danych | **Postgres** | pliku SQLite w produkcji | jeden magazyn dla domeny i dla stanu agenta; SQLite zostaje do testów |
| Trwałość stanu agenta | **gotowy checkpointer z biblioteki** | własnej klasy dziedziczącej po bazowej | własna implementacja bierze kontrakt frameworka na zawsze — przy każdym podbiciu wersji trzeba sprawdzać sygnatury |
| Narzędzia agenta | **MCP** | własnego rejestru narzędzi | standard, po którym narzędzie da się podłączyć do innego agenta bez przepisywania |
| Orkiestracja | **LangGraph** | własnej pętli sterowania | stan, przerwania i wznawianie są tam rozwiązane; własna pętla kończy się na checkpointach |
| Most agent ↔ interfejs | **AG-UI** (np. CopilotKit) | własnego kanału zdarzeń | protokół przeżywa wymianę frameworka, bezpośrednie wywołanie nie |
| Obserwowalność | **strukturalne logi z identyfikatorem przebiegu** | niczego | to sugestia, nie wymóg — serwer śladów kosztuje czas i konto, a logi z identyfikatorem wystarczą do diagnozy |
| Wzorce wieloagentowe | **jeden agent z narzędziami** | supervisora i podagentów „na zapas" | wprowadza się je, gdy ślady pokażą potrzebę, nie na podstawie diagramu |

Odchylenie od tej tabeli **nie jest błędem** — jest decyzją, która ma być
zapisana w rejestrze decyzji projektu. Audyt zgłasza odchylenie bez zapisanej
decyzji; odchylenie z decyzją przechodzi bez uwagi.

## Wzorce wieloagentowe — kiedy który

| Wzorzec | Kiedy | Koszt |
|---|---|---|
| **Pojedynczy agent + narzędzia** | problem nie wymaga separacji kontekstu | najniższy; kontekst rośnie z rozmową |
| **Router** | rozłączne domeny, zadania niezależne | najtańszy przy wielu domenach; słaby przy wnioskowaniu wieloetapowym |
| **Supervisor + podagenci** | 2–5 wyspecjalizowanych ról, potrzebna kontrola | narzut wywołań modelu; **domyślny wybór produkcyjny** |
| **Handoff / swarm** | dynamiczne przekazywanie sterowania | najdroższy tokenowo przy zapytaniach wielodomenowych |
| **Workflow deterministyczny z agentem w węzłach** | krytyczne przejścia mają być w kodzie | najniższe ryzyko; **najbardziej produkcyjny** |
| **Hierarchiczny supervisor** | duże systemy, wiele domen | rośnie koszt, opóźnienie i trudność diagnozy |

Kolejność wprowadzania jest odwrotna do atrakcyjności: zacznij od workflow
deterministycznego z agentem tylko tam, gdzie potrzebne jest rozumowanie, potem
supervisor z kilkoma workerami. Swarm i hierarchię dodaje się dopiero wtedy, gdy
**ślady pokażą realną potrzebę**, a nie na podstawie diagramu.

## Reguły projektowe, które wychodzą z tych wzorców

- podagent dostaje **fragment kontekstu, nie całą rozmowę**;
- każdy podagent ma własny kontrakt wejścia i wyjścia;
- supervisor przekazuje cele i ograniczenia, nie surowe transkrypty;
- każdy przebieg ma limit kroków, kosztu, czasu i liczby delegacji;
- stan sesji w checkpointerze, pamięć długoterminowa w osobnym store;
- **walidacja danych i uprawnień zostaje po stronie serwera**, nawet gdy
  interfejs wygenerował agent.

## Dwa różne „OpenUI" — nazwy mylą

| Nazwa | Czym jest |
|---|---|
| OpenUI (deklaratywny) | agent opisuje interfejs strukturalnie, renderer zamienia opis w drzewo komponentów |
| Open Generative UI (CopilotKit) | agent generuje kod interfejsu, uruchamiany w izolowanej ramce |

To dwa mechanizmy o różnym profilu ryzyka. Do operacji biznesowych używa się
**kontrolowanych komponentów**, do raportów i dashboardów — opisu
deklaratywnego, a generowanie swobodne zostaje dla eksploracji. Uruchamianie
wszystkich trzech dla każdego komunikatu jest wyborem, nie brakiem wyboru.

## Protokoły warte więcej niż kolejny framework

| Protokół | Granica, którą trzyma |
|---|---|
| MCP | agent ↔ narzędzia i dane |
| A2A | agent ↔ agent, między runtime'ami |
| AG-UI | agent ↔ aplikacja użytkownika |
| A2UI / opis UI | agent ↔ opis interfejsu |

Framework wymienia się co kilkanaście miesięcy; granica utrzymana protokołem
przeżywa tę wymianę. To jest argument za trzymaniem się protokołu nawet wtedy,
gdy bezpośrednie wywołanie byłoby o dwie linie krótsze.

## Świadome luki tej migawki

- **Numery wersji celowo pominięte.** Zmieniają się szybciej niż cykl przeglądu
  tego pliku, a nieaktualna wersja w dokumencie jest gorsza niż jej brak —
  patrz `dependency-currency.md` §5. Wersję sprawdza się w dokumentacji przez
  serwer dokumentacji, nie tutaj.
- **Brak porównań wydajności.** Liczby krążące w materiałach producentów
  pochodzą z jednego kontekstu i nie zostały tu zweryfikowane.
- **Brak rekomendacji chmurowych.** Orientacja jak w migawce stacku ogólnego:
  uruchamialne lokalnie albo w kontenerze.
- **Alternatywne runtime'y wymienione bez oceny** — istnieją, mają integracje,
  ale wybór między nimi wymaga kontekstu projektu, którego migawka nie zna.
