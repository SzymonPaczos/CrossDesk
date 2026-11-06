# Migawka: stack aplikacji agentycznych, sierpień 2026

Uzupełnienie 2026-11-05: dobór runtime'u i uniwersalny nakaz grafu poniżej
zastępuje [porównanie wymagań z listopada](agentic-runtime-2026-11.md).
Sama liczba wywołań modelu nie wymaga frameworka grafowego. Reszta pliku
pozostaje historyczną migawką z opisanymi ograniczeniami źródeł.

| | |
|---|---|
| **Data zebrania** | 2026-08-19 |
| **Data przeglądu** | 2027-02-19 (6 miesięcy) |
| **Zebrał** | właściciel repozytorium, jako destylat własnej praktyki i przeglądu ekosystemu |
| **Weryfikacja niezależna** | **nie przeprowadzono** — nazwy, wersje i statusy nie były sprawdzane ponownie przy wnoszeniu do toolkitu |
| **Zasada grounding** | pozycje pochodzą z pracy nad realnymi systemami tej klasy; deklarowane wielkości („N razy szybciej", progi) są cytatami z materiałów producentów albo obserwacjami z jednego kontekstu i nie zostały niezależnie zweryfikowane |

Orientacja tej migawki: **open source, uruchamialne lokalnie lub w kontenerze**.
Rozwiązania chmurowe pojawiają się wyłącznie jako oznaczone alternatywy, nigdy
jako domyślna rekomendacja.

**Ta migawka nie zastępuje konwencji.** Reguły składania stacku opisuje
`conventions/stack-composition.md`, reguły dopuszczania narzędzi —
`conventions/tool-adoption-and-measurement.md`. Gdy migawka i konwencja się
rozjeżdżają, obowiązuje konwencja. Nazwy narzędzi starzeją się w miesiącach,
zasady w latach.

---

## Wybory z warunkiem stosowalności

Kolumna **warunku** jest obowiązkowa i jest w tej tabeli najważniejsza: żaden
wybór nie jest właściwy zawsze.

| Rola | Wybór | Dlaczego | Warunek stosowalności |
|---|---|---|---|
| język aplikacji | TypeScript w trybie strict, z kontrolą indeksowania | w systemie z modelem językowym dane o nieznanej treści płyną wszędzie; typy pilnują własnego kodu, walidacja runtime cudzych danych — potrzebne są obie warstwy | zawsze, gdy w stacku jest JavaScript |
| kanon kontraktu (TS) | biblioteka schematów dająca typ i walidator z jednej definicji | likwiduje kategorię „typ mówi jedno, runtime przepuszcza drugie"; eksport do schematu neutralnego pozwala generować drugi język | zawsze po stronie TS |
| kanon kontraktu (Python) | biblioteka modeli walidujących + kontrola typów w trybie ścisłym | odpowiednik pary powyżej: model jest typem i walidatorem naraz | zawsze, gdy Python jest w stacku — bez wyjątku dla „skryptów" |
| runtime agenta | framework grafu z checkpointami, przerwaniami i budżetami | pętla agentowa jest maszyną stanów z trwałością; własne implementacje dochodzą do tego samego zestawu braków | każdy agent wykonujący więcej niż jedno wywołanie modelu |
| transport agent↔interfejs | protokół zdarzeń (przebieg, wiadomości, wywołania narzędzi, przyrosty stanu) | zdarzenia zamiast żądanie-odpowiedź dają odtwarzalność: powtórzenie historii plus migawka | agent osadzony w interfejsie produktu |
| generatywny interfejs | render komponentów z **zamkniętego rejestru**, strumieniowo | model komponuje wyłącznie z katalogu o walidowanych propsach — fizycznie nie wyrenderuje niczego spoza niego | gdy agent ma pokazywać wyniki jako żywe komponenty |
| baza | PostgreSQL w kontenerze | transakcyjna skrzynka nadawcza, kolejka na blokadzie z pominięciem zajętych, jeden backup, wieloprocesowość bez żonglerki plikami | więcej niż jeden proces piszący |
| baza (wariant) | SQLite w trybie WAL | zero infrastruktury | narzędzia jednoprocesowe, praca lokalna bez kontenerów |
| brama do modeli | proxy zgodne z jednym API, uruchomione u siebie | aplikacja zna tylko adres i nazwę modelu; wymiana dostawcy jest konfiguracją; limity i budżety w jednym miejscu | więcej niż jeden model albo wymóg nietrzymania kluczy w aplikacji |
| modele lokalne | runtime jednokomendowy (dev) albo serwer wysokoprzepustowy (produkcja) | prywatność danych, koszt, praca offline | zawsze za bramą jako kontraktem; serwer wysokoprzepustowy wymaga jawnego włączenia parsera wywołań narzędzi — bez tego tool calling nie działa mimo poprawnego endpointu |
| kolejka | tabela w bazie z dzierżawą i biciem serca | języko-neutralna, transakcyjna z domeną, zero nowej infrastruktury | do dziesiątek wykonawców; wyżej — broker, ale z pomiaru |
| automatyzacja przeglądarki | biblioteka sterująca przeglądarką w kontenerze z kontrolą zdrowia | przeglądarka jako zasób z limitem kontekstów i przymusowym sprzątaniem | każda automatyzacja przeglądarkowa; zawsze jako zlecenie w kolejce |
| obserwowalność modeli | platforma śladów uruchomiona u siebie | widok „każdy przebieg, każde wywołanie narzędzia, każdy koszt" bez wysyłania treści promptów na zewnątrz | gdy debugowanie przebiegów zaczyna zjadać czas albo robi to więcej niż jedna osoba |
| logowanie | logger strukturalny po obu stronach granicy językowej | wspólny kontrakt pól daje jedną oś czasu przez wszystkie procesy | zawsze; wypisywanie na standardowe wyjście w kodzie produkcyjnym blokowane lintem |

## Odrzucenia z sygnałem powrotu

| Odrzucone | Powód | Co by je przywróciło |
|---|---|---|
| język zapytań dla wielu konsumentów odczytu | rozwiązuje problem wielu różnych konsumentów; aplikacja agentowa ma zwykle jednego, a jej głównym kanałem jest strumień zdarzeń, któremu ten język nic nie daje; schemat obok kanonu to drugie ręczne lustro | realnie wielu zewnętrznych konsumentów o różnych potrzebach odczytu |
| odwzorowanie z własnym językiem schematu | trzeci opis kształtów obok kanonu i SQL-a | nic w tej klasie systemów |
| kolejka wymagająca osobnego brokera w pamięci | kontrakt dostępny tylko z jednego języka; nowa infrastruktura wyłącznie dla kolejki, którą baza obsłuży | zmierzona przepustowość ponad możliwości bazy |
| framework zadań wiążący jeden język | czyni język pomocniczy obywatelem pierwszej kategorii i sabotuje decyzję „ten język tylko jako wykonawca" | architektura, w której ten język **jest** backendem |
| struktury do zbieżności wielu autorów | rozwiązują konwergencję wielu jednoczesnych autorów — problemu nie ma w układzie „jeden człowiek plus agent, który proponuje" | realna współpraca wielu osób na jednym dokumencie w czasie rzeczywistym |
| własna pętla agentowa | zawsze kończy się tym samym zestawem braków: bez checkpointów, wznowień, budżetów i typowanych przerwań | nic — nawet prosty agent ma stan, który trzeba wznowić |
| drugi framework agentowy równolegle | każdy niesie własny model stanu, trwałości i błędów | nic — wielość realizuje się podgrafami jednego |
| telemetria chmurowa bibliotek agentowych | domyślna telemetria wysyła treść promptów, czyli treść dokumentów i danych użytkownika, do cudzej chmury; bywa włączona domyślnie zmienną środowiskową | świadoma decyzja z oceną danych, które wyjdą |
| klucz dostępu w trwałym magazynie przeglądarki | przeżywa zamknięcie przeglądarki — klucz staje się trwały wbrew intencji | nic; magazyn sesyjny albo nic |
| bajty plików w wiadomościach rozmowy | brak wersjonowania i audytu, pełny rozmiar w każdej turze, limity kontekstu | nic — pliki zawsze jako artefakty z referencją |
| przepisanie jako metoda naprawy stabilności | nie adresuje awarii, których przyczyny nie są językowe; kasuje wiedzę wgraną w kod | patrz `conventions/architecture-change.md` §1 |

## Świadome luki tej migawki

- **Progi liczbowe** (przepustowość, przy której baza przestaje wystarczać;
  próg skuteczności wywołań narzędzi) pochodzą z pojedynczych kontekstów
  i wymagają własnego pomiaru przed użyciem jako kryterium.
- **Nazwy konkretnych bibliotek** celowo nie znalazły się w tabelach tam, gdzie
  rola jest stabilna, a dostawca rotuje. Wybór dostawcy jest decyzją projektu
  z zapisanym warunkiem — patrz `conventions/stack-composition.md` §1.
- **Statusy licencyjne** komponentów open-core nie były sprawdzane w dniu
  zebrania; trzy pytania z `conventions/stack-composition.md` §5 zadaje się
  za każdym razem od nowa.
