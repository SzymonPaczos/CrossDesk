# Konwencja: bramki weryfikacji bezpieczeństwa kodu

Stack-agnostic. Zakres: **klasy automatycznej weryfikacji bezpieczeństwa
treści kodu, ich miejsce w pipelinie i to, które z nich blokują scalenie.**

Rozdział ról między konwencjami:

- [`ci-cd.md`](ci-cd.md) — hardening samego pipeline'u i dostawy: uprawnienia,
  pinowanie, lockfile, sekrety w CI, OIDC, provenance, vulnerability response.
  **Nie duplikuj tego tutaj.**
- [`rules-as-gates.md`](rules-as-gates.md) — procedura awansu sygnału
  raportowego na gate blokujący.
- [`multi-agent-delivery.md`](multi-agent-delivery.md) — rola Security
  Reviewera i red-team dla zmian wysokiego ryzyka.
- [`ci-pipeline-architecture.md`](ci-pipeline-architecture.md) — topologia i
  kryterium twarde/miękkie.

## 1. Pięć klas weryfikacji i to, czego każda wymaga

| Klasa | Co znajduje | Czego wymaga | Gdzie w pipelinie | Referencja OSS |
|---|---|---|---|---|
| SAST | podatne wzorce w kodzie: wstrzyknięcia SQL, XSS, brak walidacji, niebezpieczne użycie API | samego kodu | na PR | Semgrep CE |
| SCA | znane podatności w zależnościach | manifestu i pliku lock | na PR | Trivy, OSV-Scanner |
| Sekrety | hasła, tokeny, klucze w plikach **i w historii** | repozytorium | pre-push, PR, push protection | Gitleaks |
| IaC i obrazy | błędna konfiguracja infrastruktury, podatności warstw obrazu | plików konfiguracyjnych, obrazu | na PR i przed publikacją | Trivy, Checkov |
| DAST | podatności działającej aplikacji | **uruchomionej aplikacji** | po wdrożeniu na środowisko testowe | OWASP ZAP |

Rozróżnienie, które trzeba wypowiedzieć wprost, bo z niego wynika cała reszta:
**cztery pierwsze klasy działają na artefakcie statycznym, DAST wymaga
uruchomionego środowiska.** DAST nie jest więc bramką pull requesta — jest
bramką promocji ze środowiska testowego dalej. Wymaganie „każda zmiana
przechodzi DAST" przy weryfikacji pojedynczego fragmentu kodu jest niewykonalne
i albo zostanie ominięte, albo zablokuje dostawę.

Narzędzia w ostatniej kolumnie są **referencyjne, nie obowiązkowe**. Konwencja
mówi, która klasa musi być pokryta; wybór implementacji należy do projektu i
zapisuje się w jego decyzjach.

## 2. Minimalny zestaw

Dla projektu z hosted CI: SAST + SCA + skan sekretów na PR, DAST na środowisku
testowym, bot aktualizacji zależności, obowiązkowe zatwierdzenie przez osobę
inną niż autor.

**Jedno narzędzie na klasę.** Dwa nakładające się skanery bez rozstrzygnięcia,
który jest źródłem prawdy, dają podwójny szum i zero dodatkowego pokrycia —
a przy rozbieżnym wyniku nikt nie wie, który zignorować.

## 3. Co blokuje scalenie, a co tylko raportuje

Blokuje:

- **nowe** ustalenie SAST o poziomie wysokim lub krytycznym;
- **każdy** znaleziony sekret, niezależnie od pozornej ważności;
- podatność krytyczna w zależności **bezpośredniej**;
- podatność krytyczna w obrazie wdrażanym na produkcję;
- brak zatwierdzenia przeglądu przez osobę inną niż autor zmiany.

Raportuje bez zatrzymywania:

- ustalenia średnie i niskie;
- podatności w zależnościach tranzytywnych bez wykazanej ścieżki wykorzystania;
- ustalenia informacyjne DAST.

Podział wynika z tego samego kryterium, co każda inna bramka: sygnał musi być
deterministyczny, tani w rozpoznaniu fałszywego alarmu i naprawialny przez
autora bez cudzej infrastruktury. Klasa, która tego nie spełnia, zaczyna jako
raport i awansuje procedurą z [`rules-as-gates.md`](rules-as-gates.md).

## 4. Bez różnicy względem bazy gate blokuje wszystko

To jest najczęstsza przyczyna wyłączenia skanera w tydzień po wdrożeniu.

„Nowe" musi znaczyć **różnicowo względem gałęzi bazowej**, nie „obecne w
repozytorium". Włączenie SAST-a na dojrzałej bazie kodu bez tego rozróżnienia
daje setki ustaleń na pierwszym PR-ze, z których żadne nie dotyczy zmiany — i
kończy się wyłączeniem gate'a albo hurtowym wyciszeniem.

Procedura dla zastanego długu:

1. Zamroź obecny zbiór ustaleń jako **baseline** i zapisz go w repozytorium.
2. Blokuj wyłącznie **przyrost** względem baseline'u.
3. Obniżaj baseline w rytmie (ratchet): raz na sprint/miesiąc zdejmij ustaloną
   liczbę pozycji, nigdy nie pozwalając mu urosnąć.
4. Baseline ma właściciela i datę przeglądu, inaczej zamarza na zawsze.

## 5. Znaleziony sekret oznacza rotację, nie tylko usunięcie

Usunięcie poświadczenia z kodu — nawet z przepisaniem historii — **nie
unieważnia go**. Dopóki nie zostało odwołane, jest ważne dla każdego, kto
zdążył je odczytać.

- Skanuj **historię**, nie tylko drzewo robocze. Sekret usunięty commitem
  naprawczym zostaje w obiektach repozytorium.
- Traktuj każde trafienie jako ujawnione, dopóki nie udowodnisz, że nigdy nie
  opuściło maszyny. Repozytorium prywatne nie jest dowodem.
- Kolejność działań przy rotacji, w tym pułapkę wrogiego obserwatora
  traktującego odwołanie tokenu jako sygnał wyzwalający, opisuje
  [`ci-cd.md`](ci-cd.md) §5.
- Sekret nie może trafić do logów przebiegu ani do artefaktów. Krok
  publikujący artefakt z joba mającego dostęp do sekretów wymaga przeglądu
  zawartości.

## 6. Fałszywe alarmy mają budżet

Mierz odsetek fałszywych trafień per skaner i per reguła. Powyżej ustalonego
progu gate **wraca do trybu raportowego** i reguła jest strojona — alternatywą
jest to, że zespół uczy się przeklikiwać ostrzeżenia, co znosi wartość
wszystkich pozostałych.

Wyciszenie zawsze jako kod w repozytorium (plik ignorowania, adnotacja przy
linii), nigdy w interfejsie narzędzia. Wyciszenie poza repozytorium jest
niewidoczne w przeglądzie, nie podlega historii i znika przy zmianie
dostawcy.

## 7. Wyjątek ma właściciela, uzasadnienie i termin

Każde odstępstwo od bramki zapisuje trzy pola: **kto** je zaakceptował, **na
jakiej podstawie** i **do kiedy**. Wyjątek bez daty ponownej weryfikacji nie
jest wyjątkiem, tylko trwałym obniżeniem poziomu zabezpieczeń — z tą różnicą,
że nikt tego tak nie nazwał.

Przegląd listy wyjątków należy do rytmu audytu. Wyjątek po terminie jest
sygnałem maszynowym (§11), nie tematem do dyskusji.

## 8. Skaner fail-closed i jedno źródło ustaleń

- Brak narzędzia, brak tokenu, wyczerpany limit API, timeout pobierania bazy
  podatności — **blokuje z instrukcją**. Cicha zielona bramka przy niedziałającym
  skanerze jest gorsza niż jej brak, bo produkuje fałszywe poczucie pokrycia.
- Ustalenia z wszystkich narzędzi zbieraj w jednym formacie i jednym miejscu.
  To samo ustalenie zgłoszone przez dwa narzędzia liczy się raz — inaczej
  metryka długu bezpieczeństwa zależy od liczby zainstalowanych skanerów.
- Wynik skanu jest artefaktem przebiegu, tak samo jak raport testów.

## 9. Skan nie zastępuje przeglądu człowieka

Skanery są dobre we wzorcach, a ślepe na intencję. Systematycznie nie widzą:

- błędów autoryzacji na poziomie obiektu i funkcji — czy ten użytkownik ma
  prawo do **tego** zasobu;
- niepoprawnej logiki biznesowej, która jest bezpiecznie zaimplementowana i
  robi coś złego;
- nadmiarowego zakresu uprawnień nadanego usłudze, tokenowi albo roli;
- ujawnienia danych w odpowiedziach, komunikatach błędów i logach;
- kryptografii poprawnej składniowo, a użytej w złym kontekście;
- wielokrokowych warunków wyścigu i błędów w maszynach stanu.

Dlatego przegląd człowieka jest **osobnym, wymaganym gate'em**, a nie
sumowaniem zielonych znaczków. Recenzent sprawdza co najmniej: walidację
danych wejściowych, autoryzację per zasób, operacje na bazie danych
(parametryzacja, zakres transakcji), obsługę sekretów oraz pochodzenie i
aktualność użytych bibliotek.

Zasady samego przeglądu — kto zatwierdza, jak odpowiadać na uwagi — opisuje
[`pull-request-review.md`](pull-request-review.md).

## 10. Kod tworzony z udziałem narzędzi generatywnych

Wyróżnienie nie wynika z założenia, że taki kod jest z definicji gorszy.
Wynika z **tempa i objętości**: powstaje szybciej, niż rośnie zdolność zespołu
do jego przeglądu, i chętnie odtwarza wzorce popularne w danych treningowych —
łącznie z popularnymi błędami. Wymaganie dotyczy więc przepustowości
weryfikacji, nie pochodzenia kodu.

Gotowe brzmienie do wklejenia do polityki projektu:

> **Weryfikacja bezpieczeństwa kodu.** Każda zmiana zawierająca kod wygenerowany
> lub zmodyfikowany przy użyciu narzędzi generatywnych musi przejść automatyczne
> testy bezpieczeństwa w pipelinie CI/CD. Weryfikacja obejmuje analizę statyczną
> (SAST), kontrolę podatności zależności (SCA), skanowanie sekretów oraz —
> jeżeli zmiana dotyczy uruchamianej aplikacji webowej lub API — testy dynamiczne
> (DAST) na środowisku testowym. Wynik automatycznego skanowania **nie zastępuje
> przeglądu kodu**. Warunkiem połączenia zmiany z główną gałęzią jest pozytywny
> przegląd wykonany przez osobę inną niż autor zmiany, obejmujący co najmniej
> walidację danych wejściowych, autoryzację, operacje na bazie danych, obsługę
> sekretów oraz aktualność i pochodzenie zastosowanych bibliotek.

Uzupełnienie, bez którego zapis bywa obchodzony: **agent nie zatwierdza własnej
zmiany**, a przegląd AI pozostaje doradczy i nigdy nie nadpisuje czerwonej
bramki — [`ci-cd.md`](ci-cd.md) §7.

## 11. Sygnały maszynowe (tryb raportowy)

1. Krok skanera z wymuszonym sukcesem (dopisane „lub prawda", wyzerowany kod
   wyjścia, wyłączone przerywanie skryptu).
2. Wyciszenie bez uzasadnienia albo bez daty przeglądu.
3. Konfiguracja skanu sekretów obejmująca wyłącznie drzewo robocze, bez historii.
4. DAST skonfigurowany jako bramka pull requesta — z definicji wolny i
   niestabilny w tym miejscu; przenieś na środowisko testowe.
5. Pierwsze wdrożenie SAST bez zapisanego baseline'u.
6. Wyjątek po terminie ponownej weryfikacji.
7. Zależność bezpośrednia z podatnością krytyczną starszą niż ustalone SLA.
8. Job z dostępem do sekretów publikujący artefakty bez przeglądu zawartości.

## 12. Kolejność wdrożenia w istniejącym projekcie

Od klasy o najniższym odsetku fałszywych alarmów i najwyższej szkodliwości:

1. **Sekrety** — najlepszy stosunek wartości do szumu, od razu jako gate
   blokujący, razem ze skanem historii.
2. **SCA na zależnościach bezpośrednich** — krytyczne blokują, reszta raportuje.
3. **SAST w trybie raportowym z baseline'em**, awans na blokadę przyrostu po
   okresie zliczania fałszywych alarmów.
4. **IaC i obrazy** — jeśli projekt je wytwarza.
5. **DAST na środowisku testowym** — skan bazowy po wdrożeniu, pełny w rytmie
   nocnym lub przed wydaniem.
6. **Bot aktualizacji** z cooldownem dla zwykłych wydań i bez cooldownu dla
   aktualizacji bezpieczeństwa — szczegóły w [`ci-cd.md`](ci-cd.md) §3.

Każdy krok zaczyna się od pomiaru, nie od włączenia blokady. Kolejność jest
ważniejsza niż komplet: projekt z działającym skanem sekretów i przeglądem
człowieka jest bezpieczniejszy niż projekt z pięcioma skanerami, których
wyniki nikt nie czyta.

## Źródła referencyjne

- OWASP: [Top Ten](https://owasp.org/www-project-top-ten/)
- OWASP: [ZAP](https://www.zaproxy.org/)
- Semgrep: [dokumentacja](https://semgrep.dev/docs/)
- Trivy: [dokumentacja](https://trivy.dev/)
- OSV-Scanner: [dokumentacja](https://google.github.io/osv-scanner/)
- Gitleaks: [repozytorium](https://github.com/gitleaks/gitleaks)
- Checkov: [dokumentacja](https://www.checkov.io/)
- Renovate: [dokumentacja](https://docs.renovatebot.com/)
- NIST: [Secure Software Development Framework
  1.1](https://csrc.nist.gov/pubs/sp/800/218/final)

Powiązane: [`ci-cd.md`](ci-cd.md), [`rules-as-gates.md`](rules-as-gates.md),
[`multi-agent-delivery.md`](multi-agent-delivery.md),
[`ci-pipeline-architecture.md`](ci-pipeline-architecture.md),
[`pull-request-review.md`](pull-request-review.md) oraz — dla wsparcia
runtime'ów i dystansu wersji, których SCA nie mierzy —
[`dependency-currency.md`](dependency-currency.md).
