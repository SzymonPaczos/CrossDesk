# Konwencja: kontrakt API

Stack-agnostic. Zakres: **kontrakt HTTP/RPC jako artefakt pierwszej klasy** —
kolejność (kontrakt przed kodem), format błędów, idempotencja, paginacja,
kompatybilność wsteczna i bramki, które tego pilnują.

Rozdział ról:

- [`ci-cd.md`](ci-cd.md) — bezpieczeństwo dostawy i release.
- [`progressive-delivery.md`](progressive-delivery.md) — wdrażanie zmian i
  metryki dostawy.
- [`ci-pipeline-architecture.md`](ci-pipeline-architecture.md),
  [`security-verification-gates.md`](security-verification-gates.md) —
  topologia bramek i skanery.

## 1. Kontrakt przed implementacją

Specyfikacja powstaje **przed** kodem i przed nią odbywa się przegląd. Nie
dlatego, że generowanie z kodu jest złe technicznie, tylko dlatego, że
kontrakt jest miejscem, w którym najtaniej wprowadzić zmianę: recenzja
specyfikacji kosztuje minuty, recenzja wdrożonego API kosztuje migrację
klientów.

- Kontrakt żyje w repozytorium jako **jeden samowystarczalny dokument** (bez
  zależności od zewnętrznych `$ref`, których nie kontrolujesz).
- Jest publikowany dla konsumentów, nie tylko dostępny wewnętrznie.
- Zmiana kontraktu przechodzi przegląd tak samo jak zmiana kodu, a najlepiej
  z udziałem osoby po stronie klienta.
- Każdy endpoint lub komunikat MUSI mieć **właściciela, schemat wejścia,
  schemat wyjścia, politykę autoryzacji i katalog błędów**. Endpoint bez
  katalogu błędów jest kontraktem opisanym w połowie.

Sam standard opisu API nie narzuca procesu — design-first i code-first są
technicznie równoważne. **Wybór jest organizacyjny i musi być zapisany**,
razem z odpowiedzią na pytanie, który artefakt jest źródłem prawdy przy
rozjeździe: plik specyfikacji czy adnotacje w kodzie. Dwa źródła prawdy bez
rozstrzygnięcia to gwarancja dryfu.

## 2. Schemat danych jest jeden

Ten sam schemat opisuje dane w kontrakcie i waliduje je w runtime. Biblioteki
walidacyjne, które **emitują** standardowy schemat z definicji użytej w kodzie
(albo odwrotnie — generują walidator ze schematu), eliminują całą klasę
błędów „dokumentacja mówi co innego niż serwer".

Reguła: **walidacja na granicy systemu, zawsze runtime plus typy statyczne.**
Typy chronią przed własnym błędem przy kompilacji; walidacja runtime chroni
przed cudzym wejściem. Jedno nie zastępuje drugiego.

**Walidacja formatu, walidacja reguł domenowych, uwierzytelnienie i
autoryzacja MUSZĄ być osobnymi krokami.** Sklejenie ich w jedną funkcję kończy
się tym, że zmiana reguły biznesowej dotyka kontroli dostępu.

Waliduj **wejście i wyjście**. Walidacja odpowiedzi wychwytuje rozjazd
implementacji z kontraktem w miejscu, w którym jeszcze nie jest incydentem u
klienta — najtaniej włączyć ją w środowisku testowym i w CI, a na produkcji
zostawić jako log zamiast twardego błędu.

## 3. Błędy w jednym maszynowo czytelnym formacie

Wszystkie ścieżki błędu zwracają **ten sam kształt**, zgodny z Problem Details
(RFC 9457, Standards Track, lipiec 2023, zastępuje RFC 7807): typ
`application/problem+json`, pola `type`, `title`, `status`, `detail`,
`instance` plus rozszerzenia własne.

Praktyczne konsekwencje, o których łatwo zapomnieć:

- **Jeden format dla całego API**, łącznie z błędami walidacji, autoryzacji i
  odpowiedziami bramy — klient ma mieć jedną ścieżkę obsługi.
- `type` jest stabilnym identyfikatorem, po którym klient rozgałęzia logikę.
  Komunikat w `title`/`detail` jest dla człowieka i **wolno go zmieniać**;
  `type` nie.
- Błąd MUSI nieść **stabilny kod maszynowy, bezpieczny komunikat, status oraz
  identyfikator korelacyjny** (`traceId`/`requestId`) — bez niego zgłoszenie
  użytkownika jest nie do powiązania z logiem.
- Odpowiedź NIE MOŻE ujawniać SQL, śladu stosu, sekretów ani informacji
  umożliwiających enumerację wrażliwych zasobów (np. rozróżnienia „nie ma
  takiego konta" od „złe hasło").

## 4. Idempotencja operacji zmieniających stan

Metody `OPTIONS`, `HEAD`, `GET`, `PUT` i `DELETE` są idempotentne z definicji;
`POST` i `PATCH` nie są. Dla tych dwóch przyjmij klucz idempotencji przekazywany
w nagłówku żądania:

- klucz jest **unikalny** i nie może zostać użyty ponownie z innym ładunkiem;
- rekomendowany jest identyfikator losowy typu UUID;
- **polityka wygaśnięcia klucza musi być udokumentowana** — bez niej klient nie
  wie, jak długo ponowienie jest bezpieczne;
- klucz MUSI być **związany z aktorem, zakresem operacji i skrótem
  semantycznego ładunku** — sam losowy ciąg bez tego powiązania pozwala jednemu
  klientowi wpłynąć na wynik operacji innego;
- to samo żądanie z tym samym kluczem MUSI **odtworzyć wynik**; inny ładunek z
  tym samym kluczem MUSI zostać **odrzucony**;
- **idempotencja przechowywana wyłącznie w pamięci procesu jest niedopuszczalna
  w systemie wieloinstancyjnym** — to jest najczęstsza wadliwa implementacja
  tego wzorca.

Standaryzacja nagłówka jest na etapie draftu IETF, więc **nazwij to w
kontrakcie wprost** zamiast zakładać, że klient zna konwencję.

Reguła towarzysząca, praktyczna a nie zaczerpnięta ze specyfikacji: **każde
wywołanie sieciowe ma timeout, ponawia się wyłącznie operacje idempotentne, a
backoff jest wykładniczy z losowym rozrzutem.** Ponawianie nieidempotentnego
żądania bez klucza idempotencji to programowanie duplikatów.

## 5. Limity i informowanie o nich

Limity zużycia komunikuj nagłówkami odpowiedzi opisującymi politykę i
pozostały budżet, tak by klient mógł się dostosować **zanim** dostanie
odmowę. Standaryzacja jest w toku (draft IETF), więc w kontrakcie opisz
składnię, której faktycznie używasz.

Poza zakresem takiej sygnalizacji pozostają: autoryzacja, wybór kodu statusu i
konkretny algorytm ograniczania — to są decyzje serwera, nie części
kontraktu z klientem.

## 6. Paginacja od pierwszego dnia

**Dodanie paginacji do istniejącej metody zwracającej kolekcję jest zmianą
niekompatybilną wstecz.** Dlatego każda metoda zwracająca zbiór ma paginację
od początku, nawet gdy dziś zwraca trzy elementy.

Wzorzec tokenowy: rozmiar strony w żądaniu, nieprzezroczysty token następnej
strony w odpowiedzi. Do tego trzy zasady, których pominięcie boli później:

- **domyślny i maksymalny rozmiar strony** są zadeklarowane, a wartości powyżej
  maksimum są przycinane, nie odrzucane;
- **pozostałe parametry muszą się zgadzać** z tymi, przy których token powstał;
- token jest nieprzezroczysty dla klienta — jego zawartość może się zmienić bez
  zmiany wersji API.

## 7. Kompatybilność wsteczna jest bramką, nie intencją

- **REST**: porównanie kontraktu z wersją bazową w każdym PR, z rozróżnieniem
  zmian łamiących od dodających. Zmiana łamiąca albo nie wchodzi, albo wchodzi
  ze świadomą decyzją i wersjonowaniem.
- **Protobuf/RPC**: analogiczna kontrola zgodności schematu wobec wersji
  poprzedniej, wymuszana w CI, a nie tylko przy przeglądzie.
- **Lint kontraktu** według firmowego zestawu reguł — spójność nazewnictwa,
  wymagane opisy, zakazane wzorce. Reguły są kodem w repozytorium.

Kolejność w pipelinie: lint kontraktu → porównanie z bazą → generowanie
klientów → testy kontraktowe. Wszystko przed testami integracyjnymi, bo jest
tańsze i szybciej wskazuje przyczynę.

## 8. Klienci są generowani, nie pisani

Klient pisany ręcznie jest drugą, nieoficjalną implementacją kontraktu i
rozjeżdża się w tempie zmian API. Generuj z kontraktu — dla REST z opisu API,
dla RPC ze schematu.

**Testy kontraktowe konsument–dostawca** zamykają lukę, której nie widzi ani
lint, ani porównanie wersji: sprawdzają, czy dostawca faktycznie spełnia
oczekiwania konkretnego konsumenta, a kontrakt powstaje z wykonania testów
konsumenta.

## 9. Wybór stylu API

| Styl | Kiedy | Koszt, o którym trzeba wiedzieć |
|---|---|---|
| REST + opis kontraktu | API publiczne, integracje zewnętrzne | najbogatszy ekosystem generatorów, lintu i diffowania |
| RPC z kontraktem schematu | komunikacja usługa↔usługa, strumieniowanie | wymusza kompatybilność narzędziowo, ale wprowadza własny łańcuch narzędzi |
| Zapytania o elastycznym kształcie | klient potrzebuje sam dobierać pola | osobna specyfikacja transportu, a subskrypcje bywają poza jej zakresem |

To nie jest wybór ideologiczny. Jedno API może wystawiać REST na zewnątrz i
RPC do wewnątrz — pod warunkiem że **oba mają kontrakt i oba mają bramkę
zgodności**.

Zasada „bądź liberalny w tym, co przyjmujesz" ma swoją cenę: każde ciche
zaakceptowanie niepoprawnego wejścia staje się zachowaniem, na którym ktoś
polega, i którego nie możesz później usunąć. Bądź liberalny świadomie i
zapisuj każde takie odstępstwo, zamiast traktować je jako domyślną uprzejmość.

## 10. Obserwowalność jako część kontraktu

Nazwy i atrybuty spanów oraz metryk HTTP mają standardowe konwencje
semantyczne — użyj ich zamiast własnego nazewnictwa. Zysk jest natychmiastowy:
pulpity i alerty przenoszą się między usługami bez przepisywania, a korelacja
między usługami działa bez tłumaczenia pól.

Instrumentacja jest **częścią definicji gotowości** endpointu, nie
dodatkiem po incydencie.

## 10a. Bezpieczeństwo granicy

Reguły, których złamanie nie objawia się w testach funkcjonalnych, tylko w
incydencie:

- Serwer **NIE MOŻE ufać** przesłanym przez klienta rolom, tenantowi,
  właścicielowi zasobu ani cenie. Wszystkie pochodzą z sesji i z bazy.
- Kontrola dostępu MUSI obejmować **ownership i izolację tenantów**, nie tylko
  rolę. „Zalogowany" nie znaczy „uprawniony do tego zasobu".
- Publiczne granice MUSZĄ mieć limity **rozmiaru ciała żądania, czasu,
  paginacji i częstotliwości**.
- Uploady i pobieranie zewnętrznych adresów MUSZĄ ograniczać typy, rozmiary,
  lokalizacje oraz **ryzyko SSRF**.
- Sekrety NIE MOGĄ znajdować się w repozytorium, logach ani bundlu klienta —
  szczegóły w [`ci-cd.md`](ci-cd.md) i [`runtime-boundaries.md`](runtime-boundaries.md).

Bramki dla tej sekcji: testy cross-tenant, testy równoległej idempotencji,
skan sekretów oraz krytyczne wyniki SAST/SCA — wszystkie blokujące.

## 11. Lista kontrolna przeglądu API

- kontrakt w repozytorium, samowystarczalny, opublikowany;
- lint kontraktu bez błędów wobec firmowego zestawu reguł;
- porównanie z bazą: brak zmian łamiących albo świadoma decyzja z wersjonowaniem;
- schematy żądań i odpowiedzi zgodne z przyjętą wersją standardu schematów;
- walidacja wejścia **i** wyjścia po stronie serwera;
- wszystkie ścieżki błędu zwracają jeden format problem details;
- operacje nieidempotentne mają klucz idempotencji i test ponowienia;
- kolekcje paginowane od początku, z domyślnym i maksymalnym rozmiarem strony;
- limity komunikowane nagłówkami, polityka zdefiniowana;
- spany i metryki zgodne z konwencjami semantycznymi;
- klient generowany, nie pisany ręcznie;
- testy kontraktowe konsumenta w CI;
- dla schematów RPC: lint i kontrola zgodności w CI;
- endpoint ma właściciela i katalog błędów;
- kontrola dostępu obejmuje ownership i izolację tenantów, z testem cross-tenant;
- limity rozmiaru, czasu, paginacji i częstotliwości na publicznej granicy.

## 12. Sygnały maszynowe (tryb raportowy)

1. Endpoint w kodzie bez odpowiadającej mu ścieżki w kontrakcie (i odwrotnie).
2. Odpowiedź błędu o typie innym niż uzgodniony format problem details.
3. Metoda zwracająca kolekcję bez parametrów paginacji.
4. Kontrakt niezmieniony w PR, który zmienia sygnatury handlerów.
5. Brak kroku porównania kontraktu z bazą w pipelinie PR.
6. Klient wygenerowany starszy niż kontrakt (rozjazd sum kontrolnych).
7. Ręcznie edytowany plik oznaczony jako wygenerowany.

## 13. Kolejność wdrożenia w istniejącym API

1. **Wyeksportuj stan faktyczny** do kontraktu i zacommituj go — nawet jeśli
   jest brzydki. Bez punktu odniesienia nie ma czego porównywać.
2. **Włącz porównanie z bazą w trybie raportowym**, policz, ile zmian łamiących
   robicie nieświadomie. To zwykle jest moment, w którym dyskusja się kończy.
3. **Ujednolić błędy** do jednego formatu — najbardziej odczuwalna zmiana dla
   klientów przy najmniejszym ryzyku.
4. **Dodaj lint kontraktu**, najpierw ostrzegawczo.
5. **Paginacja i idempotencja** dla nowych endpointów; istniejące migruj przez
   nową wersję, nie przez zmianę zachowania.
6. **Generowani klienci** i testy kontraktowe.

## Źródła referencyjne

- IETF: [RFC 9457 — Problem Details for HTTP
  APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- IETF: [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
- IETF: [Idempotency-Key Header
  (draft)](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)
- IETF: [RateLimit header fields
  (draft)](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/)
- [OpenAPI Specification](https://spec.openapis.org/)
- [JSON Schema](https://json-schema.org/specification)
- [Zalando RESTful API
  Guidelines](https://opensource.zalando.com/restful-api-guidelines/) — wzorzec
  organizacyjny „API first"
- [Google AIP-158 — Pagination](https://google.aip.dev/158),
  [AIP-121 — Resource-oriented design](https://google.aip.dev/121)
- [OpenTelemetry — semantic conventions for
  HTTP](https://opentelemetry.io/docs/specs/semconv/http/http-spans/)
- Narzędzia: [Spectral](https://github.com/stoplightio/spectral) (lint),
  [oasdiff](https://github.com/oasdiff/oasdiff) (diff REST),
  [Buf](https://buf.build/docs/) (lint i breaking dla Protobuf),
  [Pact](https://docs.pact.io/) (testy kontraktowe)

Powiązane: [`ci-cd.md`](ci-cd.md), [`progressive-delivery.md`](progressive-delivery.md),
[`rules-as-gates.md`](rules-as-gates.md).
