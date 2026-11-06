# Konwencja: formularze i walidacja

Stack-agnostic w warstwie zasad, z przykładami w TypeScript. Zakres:
**jeden schemat jako źródło typów i walidacji po obu stronach, moment
walidacji, mapowanie błędów na pola, dostępność komunikatów i bezpieczna
wysyłka.**

Rozdział ról:

- [`typescript-javascript.md`](typescript-javascript.md) — dane z granicy
  zaufania jako `unknown` i walidacja runtime **w ogóle**; ta konwencja opisuje
  szczególny, najczęstszy przypadek: dane od użytkownika przez formularz.
- [`api-contract-design.md`](api-contract-design.md) — kontrakt między usługami.
- [`design-system-foundations.md`](design-system-foundations.md) — wygląd i
  stany kontrolek; tu chodzi o zachowanie i treść komunikatu.
- [`frontend-architecture.md`](frontend-architecture.md) — stan formularza jako
  jeden z czterech rodzajów stanu.

---

## 1. Jeden schemat, dwie strony

Formularz i endpoint, który go przyjmuje, MUSZĄ wywodzić się z **jednej
definicji schematu**. Nie z dwóch zgodnych — z jednej.

- Typy formularza są **wywnioskowane ze schematu**, nie pisane obok niego.
  Ręcznie utrzymywany typ obok schematu rozjeżdża się przy pierwszej zmianie,
  a kompilator tego nie wykryje, bo oba są poprawne osobno.
- Schemat współdzielony przez klienta i serwer MUSI mieszkać w module
  neutralnym runtime'owo — bez importów bazy, sekretów i API środowiska
  serwerowego (patrz [`runtime-boundaries.md`](runtime-boundaries.md)).
- Reguły, których klient nie może sprawdzić (unikalność, limity konta, stan
  zasobu), pozostają **wyłącznie po stronie serwera**. Schemat wspólny opisuje
  kształt i format; reguły domenowe należą do warstwy aplikacyjnej.

```ts
// shared/contracts/create-order.ts
export const CreateOrderSchema = z.object({
  customerId: z.string().uuid(),
  quantity: z.coerce.number().int().positive().max(100),
  note: z.string().trim().max(500).optional(),
});

export type CreateOrderInput = z.input<typeof CreateOrderSchema>;   // to, co wpisuje użytkownik
export type CreateOrderOutput = z.output<typeof CreateOrderSchema>; // to, co dostaje domena
```

Biblioteka jest wyborem projektu. Warunek konieczny: **wnioskowanie typów ze
schematu, walidacja runtime i możliwość eksportu schematu do kontraktu API.**
Wspólny interfejs schematów pozwala dziś podmienić bibliotekę bez przepisywania
formularzy — jeśli wasza go implementuje, korzystajcie z niego zamiast wiązać
kod z konkretnym dostawcą.

## 2. Walidacja klienta to UX, walidacja serwera to bramka

- Klient waliduje, **żeby użytkownik nie czekał** na odpowiedź, by dowiedzieć
  się o literówce.
- Serwer waliduje, **żeby system był poprawny**. Serwer NIE MOŻE zakładać, że
  klient cokolwiek sprawdził — patrz
  [`api-contract-design.md`](api-contract-design.md) §10a.
- Pominięcie walidacji na kliencie jest wadą UX. Pominięcie na serwerze jest
  luką bezpieczeństwa. **To nie są dwa warianty tej samej reguły.**

## 3. Typ wejściowy nie równa się wyjściowemu

Pole liczbowe w formularzu jest łańcuchem znaków. Data jest łańcuchem. Pusty
input to `""`, nie `undefined`.

- Konwersje (`coerce`, `transform`, `trim`) MUSZĄ być **częścią schematu**, nie
  rozsypane po komponencie i handlerze — inaczej klient i serwer normalizują
  inaczej.
- Kod korzystający z danych po walidacji używa **typu wyjściowego**; kontrolki
  formularza pracują na **wejściowym**.
- Normalizacja przed walidacją (`trim`, usunięcie spacji z numeru konta) MUSI
  być jawna, bo zmienia to, co użytkownik zobaczy po ponownym renderze.

## 4. Moment walidacji i ujawnianie błędów

Reguła domyślna, odporna na najczęstsze zarzuty z testów użyteczności:

- **przed pierwszym wysłaniem** pole pokazuje błąd dopiero po opuszczeniu go
  (`blur`), nie przy każdym znaku;
- **po pierwszej nieudanej próbie wysłania** pola walidują się na bieżąco, bo
  użytkownik już wie, że coś jest nie tak, i chce natychmiastowego potwierdzenia
  poprawki;
- **nigdy** nie waliduj na każdym znaku pola, którego użytkownik jeszcze nie
  skończył wypełniać — komunikat „to nie jest poprawny adres e-mail" przy
  trzeciej literze jest szumem.

## 5. Stan formularza mieszka w formularzu

- Wartości, `dirty`, `touched` i błędy należą do formularza — **NIE WOLNO**
  trzymać ich w globalnym magazynie stanu tylko dlatego, że „może się
  przydadzą".
- Wartość, którą użytkownik ma móc odtworzyć z linku (filtry, wyszukiwanie),
  należy do URL, nie do formularza — patrz
  [`frontend-architecture.md`](frontend-architecture.md).
- Formularz wieloetapowy MUSI mieć jawnie zdefiniowane, gdzie żyje stan między
  krokami i co się dzieje po odświeżeniu strony. „Zniknie" jest dopuszczalną
  odpowiedzią, jeśli jest **decyzją**, a nie skutkiem ubocznym.

## 6. Błędy serwera wracają na pola

Odpowiedź błędu walidacji MUSI dać się zmapować na konkretne pola. Bez tego
użytkownik dostaje komunikat „popraw dane" nad formularzem z dwudziestoma
polami.

- Błąd walidacji z serwera MUSI nieść **ścieżkę pola** i **stabilny kod**;
  format odpowiedzi opisuje [`api-contract-design.md`](api-contract-design.md)
  (rozszerzenie problem details o listę błędów pól).
- Błąd niedotyczący pojedynczego pola (konflikt, brak uprawnień, reguła
  międzypolowa) trafia na **poziom formularza**, nie do losowego pola.
- **NIE WOLNO czyścić formularza po błędzie.** Dane użytkownika są jego pracą;
  utrata dziesięciu wypełnionych pól z powodu jednej pomyłki jest wadą, nie
  „bezpiecznym resetem".

## 7. Dostępność komunikatów

To jest część, która najczęściej wypada z implementacji i najczęściej wraca
jako zgłoszenie.

- Pole z błędem MUSI mieć `aria-invalid` oraz powiązanie komunikatu przez
  `aria-describedby`.
- Komunikat MUSI być **widoczny tekstowo**, nie tylko czerwoną ramką —
  kolor nie może być jedynym nośnikiem informacji
  ([`design-system-foundations.md`](design-system-foundations.md)).
- Po nieudanej próbie wysłania fokus MUSI trafić na **pierwsze błędne pole**
  albo na podsumowanie błędów; użytkownik klawiatury nie może być zostawiony
  na przycisku wysyłki.
- Formularz dłuższy niż jeden ekran POWINIEN mieć **podsumowanie błędów** na
  górze, z odnośnikami do pól.
- Zmiana liczby błędów POWINNA być ogłaszana w regionie live, jeśli nie
  towarzyszy jej przeniesienie fokusu.
- Każde pole MUSI mieć trwale widoczną etykietę. Placeholder **nie jest**
  etykietą — znika po rozpoczęciu pisania.

## 8. Wysyłka

- Przycisk wysyłki MUSI być zabezpieczony przed **podwójnym kliknięciem**
  (blokada na czas żądania), a nie tylko wyszarzony po sukcesie.
- Operacja tworząca skutek zewnętrzny (płatność, zamówienie, wiadomość) MUSI
  używać **klucza idempotencji** generowanego raz na próbę wysyłki, nie na
  każde żądanie — szczegóły w [`api-contract-design.md`](api-contract-design.md).
- Ponowienie po timeoucie NIE MOŻE zakładać, że pierwsze żądanie nie doszło.
  Wynik niepewny jest niepewny — patrz
  [`reliability-and-observability.md`](reliability-and-observability.md).
- Stan `pending`, `success` i `error` wysyłki jest częścią kontraktu
  komponentu, tak samo jak `loading`/`error`/`empty` dla odczytu.

## 9. Walidacja asynchroniczna

- Sprawdzenie wymagające serwera (zajętość nazwy, poprawność kodu rabatowego)
  MUSI być **odroczone** (debounce) i odporne na wyścig — liczy się odpowiedź
  dla ostatniego zapytania, nie ostatnia, która wróciła.
- Wynik asynchroniczny jest **wskazówką**, nie gwarancją. Ostateczne
  rozstrzygnięcie należy do wysyłki, bo stan mógł się zmienić między
  sprawdzeniem a zapisem.
- Pole czekające na odpowiedź MUSI mieć stan pośredni; „brak błędu" nie znaczy
  „sprawdzono".

## 10. Treść komunikatów

- Schemat niesie **kod błędu**, warstwa prezentacji niesie **tekst**. Komunikat
  wpisany w schemat blokuje tłumaczenia i wycieka język techniczny do
  interfejsu.
- Komunikat MUSI mówić, **co zrobić**, a nie tylko co jest źle: „Hasło musi mieć
  co najmniej 12 znaków" zamiast „Nieprawidłowa wartość".
- Komunikat NIE MOŻE ujawniać istnienia zasobu ani danych innego użytkownika
  (np. rozróżnienia „konto nie istnieje" od „złe hasło").

## 11. Bezpieczeństwo i prywatność

- Pola wrażliwe (hasła, tokeny, numery kart) NIE MOGĄ trafiać do logów, do
  telemetrii ani do stanu utrwalanego w przeglądarce.
- Automatyczne uzupełnianie i typ pola MUSZĄ być ustawione zgodnie z
  przeznaczeniem — to jednocześnie dostępność, wygoda i mniejsze ryzyko
  wklejenia danych w złe miejsce.
- Uploady MUSZĄ mieć ograniczenia typu i rozmiaru sprawdzane **po stronie
  serwera**; sprawdzenie w przeglądarce jest wyłącznie UX.
- Formularz publiczny MUSI mieć ochronę przed nadużyciem (limit częstotliwości)
  — patrz [`api-contract-design.md`](api-contract-design.md) §10a.

## 12. Testy

- Test formularza MUSI obejmować **ścieżkę błędu**, nie tylko poprawne
  wypełnienie: wartość niepoprawną, błąd zwrócony przez serwer i zachowanie
  danych po tym błędzie.
- Test MUSI sprawdzać **komunikat widziany przez użytkownika**, nie stan
  wewnętrzny biblioteki formularza.
- Schemat współdzielony MUSI mieć własne testy przypadków granicznych; są
  tańsze i szybsze niż testy przez interfejs.
- Dostępność błędów (powiązanie komunikatu z polem, przeniesienie fokusu) MUSI
  być testowana automatycznie tam, gdzie się da.

## 13. Egzekwowanie

**Blokują:**

- brak walidacji serwerowej na endpoincie przyjmującym dane z formularza;
- typ formularza pisany ręcznie zamiast wywnioskowany ze schematu, gdy schemat
  istnieje;
- import klienta HTTP lub modułu serwerowego do modułu schematu współdzielonego;
- pole bez etykiety i pole z błędem bez powiązania komunikatu.

**Raportują:**

- schemat zdefiniowany po stronie klienta bez odpowiednika w kontrakcie API;
- komunikat błędu wpisany na stałe w schemacie zamiast kodu;
- formularz bez testu ścieżki błędu.

## 14. Sygnały maszynowe (tryb raportowy)

1. Dwa schematy o tej samej nazwie po stronie klienta i serwera.
2. Ręcznie zadeklarowany typ obok istniejącego schematu tego samego kształtu.
3. Handler wysyłki bez blokady na czas żądania.
4. Operacja o skutku zewnętrznym bez klucza idempotencji.
5. Reset wartości formularza w gałęzi obsługi błędu.
6. `placeholder` bez towarzyszącej etykiety.
7. Pole wrażliwe w ładunku telemetrii lub w logu.

Powiązane: [`typescript-javascript.md`](typescript-javascript.md),
[`api-contract-design.md`](api-contract-design.md),
[`frontend-architecture.md`](frontend-architecture.md),
[`design-system-foundations.md`](design-system-foundations.md),
[`reliability-and-observability.md`](reliability-and-observability.md),
[`rules-as-gates.md`](rules-as-gates.md).
