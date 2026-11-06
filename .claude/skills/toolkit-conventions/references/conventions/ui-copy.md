# Konwencja: teksty w interfejsie i dane, których nie wolno wymyślić

Stack-agnostic. Zakres: **co wolno napisać w interfejsie, czego nie wolno
zmyślić, i jak jedno i drugie sprawdzić maszynowo.**

Rozdział ról:

- [`naming-conventions.md`](naming-conventions.md) §4 — leksykon projektu,
  „jedno pojęcie, jedno słowo". Ta konwencja go nie powtarza; dokłada regułę
  o tym, jak słowo brzmi **dla użytkownika**, nie w kodzie.
- [`design-system-foundations.md`](design-system-foundations.md) — typografia,
  kontrast, tokeny. Tu chodzi o treść napisu, nie o jego wygląd.
- [`third-party-assets-privacy.md`](third-party-assets-privacy.md) — zasoby
  z zewnątrz i prawa do nich. Tu chodzi o dane **wymyślone**, nie pożyczone.

## 1. Problem

Model językowy proszony o interfejs produkuje dwie rzeczy naraz: prozę
marketingową, która nic nie znaczy, i **dane, które wyglądają jak prawdziwe**.
Drugie jest groźniejsze. Pusty nagłówek widać od razu; „99,9% uptime" i cytat
zadowolonego klienta z imieniem i stanowiskiem przechodzą przez review, bo
wyglądają jak coś, co ktoś kiedyś ustalił.

Reguła nadrzędna dla danych brzmi:

> Dane w interfejsie są albo prawdziwe, albo **widocznie** nieprawdziwe.
> Nigdy pośrodku.

## 2. Zakazane słowa mają wagę i zamiennik, nie samą listę

Płaska lista zakazów nie działa z dwóch powodów: każda pozycja jest tak samo
pilna (a nie jest), i autor zostaje bez wyjścia, więc wraca tym samym w innej
formie. Katalog projektu ma trzy kolumny.

| Waga | Znaczenie |
|---|---|
| **3** | usuwamy bezwarunkowo — słowo nie niesie żadnej informacji |
| **2** | usuwamy, chyba że da się je obronić konkretem w tym samym zdaniu |
| **1** | sygnał do przeczytania zdania, nie werdykt |

Przykład wiersza katalogu:

| Waga | Słowo | Dlaczego razi | Zamiennik |
|---|---|---|---|
| 3 | kluczowy | puste, pasuje do wszystkiego | decydujący / najważniejszy / [usuń] |
| 3 | kompleksowy | nadużyty w każdej branży | pełny / obejmujący wszystko |
| 3 | skuteczny | chwali, nie opisuje | działa / przynosi X wyników |

Rdzeń katalogu — do skopiowania i rozszerzenia w projekcie:

**Czasowniki-wydmuszki (waga 3):** elevate, unlock, unleash, harness, empower,
supercharge, revolutionize, transform, streamline, delve, embark, leverage,
foster, unveil · „odblokuj potencjał", „wykorzystaj moc", „przenieś na wyższy
poziom".

**Przymiotniki-wydmuszki (waga 3):** seamless, robust, powerful, cutting-edge,
next-gen, state-of-the-art, world-class, game-changing, effortless, intuitive,
stunning, blazing fast, enterprise-grade · kluczowy, kompleksowy, holistyczny,
innowacyjny, potężny, rewolucyjny, intuicyjny, bezproblemowy.

**Rzeczowniki-wytrychy (waga 2):** solution, platform (gdy to nie platforma),
experience, journey, ecosystem, suite, powerhouse · „kompleksowe rozwiązanie",
„szyte na miarę".

**Przysłówki bez liczby (waga 2):** realnie, znacząco, istotnie, dynamicznie,
bezproblemowo — każdy z nich albo dostaje liczbę, albo znika.

**Konstrukcje (waga 3):** „To nie tylko X, to Y" · „Bez X. Bez Y. Po prostu Z."
· „W dzisiejszych czasach…" · „Niezależnie czy jesteś X czy Y…" · „Zapomnij
o X" · triady rytmiczne („Szybko. Prosto. Bezpiecznie.") · nagłówek pytający,
o który nikt nie pytał.

## 3. Wyjątki dziedzinowe są obowiązkowe

To jest reguła wyprowadzona z awarii, nie z ostrożności. W jednym z projektów
floty słowo `seamless` występuje w 22 commitach — i **ani razu** nie jest
marketingiem. Siedzi w konfiguracji generowania obrazów:

```yaml
seamless muted sage-green background
matte steel-blue seamless surface
```

To termin fotograficzny: bezszwowe tło z rolki. Bramka bez wyjątków zgłosiłaby
tam kilkadziesiąt fałszywych trafień, zostałaby wyłączona przy pierwszym
przeglądzie i przestała chronić przed czymkolwiek.

Dlatego katalog projektu ma **drugi plik**: listę słów zwolnionych, każde
z zakresem ścieżek i jednozdaniowym powodem. Zwolnienie bez powodu jest
nieodróżnialne od kapitulacji.

## 4. Przycisk i nagłówek

**Etykieta przycisku = czasownik + obiekt**, dokładnie ta czynność, która
nastąpi.

| Zamiast | Napisz |
|---|---|
| Get Started, Rozpocznij | Utwórz konto · Dodaj pierwszy projekt |
| Learn More, Dowiedz się więcej | Zobacz cennik · Przeczytaj dokumentację API |
| Submit | Wyślij zgłoszenie · Zapisz zmiany |
| Continue | Przejdź do płatności · Potwierdź adres |

Nagłówek mówi **co to jest**, nie **jakie to wspaniałe**. „Faktury cykliczne"
bije „Potężne narzędzie do fakturowania" na każdym wymiarze poza próżnością.

Pusty stan mówi, co zrobić: „Nie masz jeszcze żadnych klientów. Dodaj
pierwszego." — nie „Tu jest jeszcze pusto 👻". Błąd mówi, co się stało i co
zrobić: „Hasło musi mieć min. 8 znaków" — nie „Ups! Coś poszło nie tak".

Zero wykrzykników. Zero emoji, jeśli nie ma ich w systemie designu. Jeden język
w całym produkcie — żadnego „Dashboard Overview" w polskiej aplikacji.

## 5. Napis o postępie jest twierdzeniem o stanie systemu

Reguła wyprowadzona z realnej awarii. W jednym z projektów przycisk zostawał na
napisie „Uczę…", bo funkcja czekała na załadowanie katalogu, zanim otworzyła
czat — błąd ładowania zostawiał martwy komunikat i widok, który nie reagował.

Napis „Zapisuję…", „Uczę…", „Trwa analiza" **twierdzi, że coś się dzieje**.
Jeśli nie da się tego twierdzenia cofnąć przy błędzie, napis kłamie tak samo
jak wymyślona liczba. Konsekwencja praktyczna: stan „w trakcie" musi mieć
ścieżkę wyjścia dla błędu i dla przekroczenia czasu, ustawioną w tym samym
miejscu, w którym się go włącza.

## 6. Nazwa czynności obiecuje mechanizm

Ten sam projekt zmienił w całej warstwie słowo „ucz" na „dodaj" — nagłówki,
tytuły przycisków, opis strony, nazwę modułu promptu, nazwę funkcji i komentarze.
Powód: „ucz" sugerowało uczenie maszynowe, a operacja tylko dopisywała regułę
do pola. Słowo obiecywało mechanizm, którego nie ma.

Sprawdzian jest jednozdaniowy: **czy użytkownik, czytając tę etykietę, oczekuje
czegoś, czego system nie robi?** Jeśli tak, zmiana idzie przez wszystkie
warstwy naraz, razem z nazwami w kodzie — inaczej za miesiąc kod i interfejs
mówią co innego o tej samej rzeczy ([`naming-conventions.md`](naming-conventions.md) §4).

## 7. Tekst zwijamy, nie tniemy

Skracanie długiej treści w interfejsie robi się **klamrą wizualną**
(`max-height`, gradient, przełącznik), nie cięciem łańcucha znaków. Ucięty
string psuje tekst jako dane: znika z kopiowania i z wyszukiwania w stronie.

Wielokropek dopisany do obciętego zdania jest gorszy niż brak skracania,
bo wygląda na świadomą decyzję redakcyjną.

## 8. Czego model nie ma prawa wymyślić

1. **Liczby dowodowe** — „10 000+ klientów", „99,9% uptime", „4,9/5 z 2 341
   opinii", „oszczędzasz 12 godzin tygodniowo".
2. **Opinie i cytaty** — testimonial z imieniem, stanowiskiem i firmą to nie
   placeholder, to sfabrykowany dowód społeczny.
3. **Logotypy klientów** i sekcje „zaufali nam".
4. **Certyfikaty i zgodności** — SOC 2, ISO 27001, HIPAA, „nagroda X 2026".
5. **Ceny, terminy, SLA, warunki gwarancji.**
6. **Dane osobowe wyglądające na prawdziwe** — nazwiska, e-maile w istniejących
   domenach, telefony, adresy, numery identyfikacyjne.
7. **Wartości na wykresach** — słupki bez źródła.
8. **Endpointy, klucze, nazwy bibliotek i wersje** niepotwierdzone
   w dokumentacji albo w kodzie ([`dependency-currency.md`](dependency-currency.md) §5).

## 9. Co robić zamiast

Brakuje treści → **jawny znacznik**: `[TODO: prawdziwa liczba klientów]`,
`{{ customer_count }}`. Nigdy liczba wzięta z powietrza.

Potrzebne dane demonstracyjne → wyłącznie **pule zarezerwowane**, żeby nikt
nigdy nie wziął ich za prawdziwe:

| Rodzaj | Pula |
|---|---|
| domeny | `example.com`, `example.org`, `example.net` (RFC 2606), `.test`, `.invalid`, `.localhost` |
| telefon | `800-555-0100`–`800-555-0199`; w Polsce `+48 000 000 000` |
| IPv4 | `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` (RFC 5737) |
| IPv6 | `2001:db8::/32` (RFC 3849) |
| osoby | Alex, Dana, Kai, Quinn, Taylor, Charlie; `Jan Przykładowy` |
| firma | „Example Organization", „Firma Przykładowa Sp. z o.o." |

Sekcja wymagająca dowodu, którego nie ma → **nie generuj jej**. Zostaw
komentarz: `<!-- sekcja opinii: wstaw prawdziwe cytaty albo usuń -->`.

Dane demonstracyjne oznacz w interfejsie — baner „Dane demonstracyjne", szare
tło, seria wykresu nazwana „Przykładowe dane", nigdy „Przychód Q3 2026".
Nie mieszaj jawnego placeholdera z prawdziwą treścią w jednym widoku.

Nie podnoś wiarygodności grafiką: wygenerowany awatar przy zmyślonym cytacie
zamienia niedbałość w fałszerstwo.

## 10. Meldunek na koniec

Po zbudowaniu albo zmianie widoku wypisz **wszystko, co zostało zmyślone albo
jest zaślepką**:

```text
UI_FABRICATED: <n pozycji>
- hero: liczba klientów → [TODO]
- cennik: kwoty 49/99/199 → placeholder, do potwierdzenia
- wykres: dane losowe, seria oznaczona „Przykładowe dane"
```

Bez tego meldunku fikcja wchodzi do produkcji, bo nikt nie wie, czego szukać.
Meldunek pusty (`UI_FABRICATED: 0`) też jest wynikiem i też się go wypisuje.

## 11. Egzekwowanie

**Blokują:**

- słowo z wagą 3 w tekście widocznym dla użytkownika, poza plikami zwolnionymi;
- liczba dowodowa, cytat, logotyp albo certyfikat bez źródła w repozytorium;
- dane osobowe albo domena spoza pul zarezerwowanych w danych demonstracyjnych;
- brak meldunku `UI_FABRICATED` przy zmianie dotykającej widoku.

**Raportują:**

- słowa z wagą 2 i 1 — do przeczytania, nie do odrzucenia;
- wykrzyknik i emoji w napisie, gdy system designu ich nie ma;
- angielska wstawka w interfejsie prowadzonym w innym języku;
- etykieta przycisku bez czasownika.

Narzędzie: [`templates/ui-copy-lint.sh`](../templates/ui-copy-lint.sh) —
katalog i plik zwolnień są projektowe, skrypt działa bez konfiguracji z pustym
katalogiem domyślnym.

## 12. Sygnały maszynowe

| Sygnał | Znaczenie |
|---|---|
| `UI_COPY_BLOCKING` | trafienia z wagą 3; niezerowe blokuje |
| `UI_COPY_REVIEW` | trafienia z wagą 2 i 1 |
| `UI_COPY_EXEMPT` | trafienia pominięte przez zwolnienia dziedzinowe; rosnące szybko = katalog jest źle dobrany |
| `UI_FABRICATED` | pozycje wymyślone albo zaślepki, z meldunku |
| `UI_LANG_MIX` | wstawki w obcym języku |

Powiązane: [`naming-conventions.md`](naming-conventions.md),
[`design-system-foundations.md`](design-system-foundations.md),
[`forms-and-validation.md`](forms-and-validation.md),
[`third-party-assets-privacy.md`](third-party-assets-privacy.md),
[`rules-as-gates.md`](rules-as-gates.md).
