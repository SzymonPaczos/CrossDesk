# Konwencja: bramki jakości, odstępstwa i definicja ukończenia

Stack-agnostic. Zakres: **katalog bramek wraz z trybem każdej, wymagania wobec
samej bramki, obsługa odstępstw oraz definicja ukończenia funkcjonalności.**

Rozdział ról — trzy konwencje dotykają bramek z różnych stron i nie powtarzają
się nawzajem:

- [`test-evidence.md`](test-evidence.md) — czy **pojedynczy test** cokolwiek dowodzi.
- [`ci-pipeline-architecture.md`](ci-pipeline-architecture.md) — **topologia**
  pipeline'u i kryterium podziału na twarde i miękkie.
- Ta konwencja — **który konkretnie gate istnieje, w jakim trybie**, i kiedy
  funkcjonalność wolno uznać za ukończoną.
- [`architecture-principles.md`](architecture-principles.md) — format
  odstępstwa, do którego odsyła § „Obsługa wyjątków".

---

## Strategia testów

- Każda zmiana zachowania MUSI mieć test na najniższej warstwie, która
  wiarygodnie chroni ryzyko.
- Reguły domenowe, autoryzacja, transakcje, idempotencja, migracje i kontrakty
  MUSZĄ mieć testy automatyczne.
- Testy MUSZĄ być niezależne od kolejności, czasu rzeczywistego, zewnętrznej
  sieci i współdzielonego stanu, chyba że są jawnie oznaczone jako integracyjne
  lub E2E.
- Naprawa błędu krytycznego MUSI zawierać test regresji.
- Test POWINIEN sprawdzać zachowanie publiczne, nie prywatną implementację.
- Snapshot NIE MOŻE być jedynym testem złożonej logiki.
- Coverage jest wskaźnikiem pomocniczym. Nie jest dowodem jakości i NIE
  POWINIEN być jedyną bramką.

## Macierz bramek

| Bramka | Tryb |
|---|---|
| formatowanie, lint, typecheck | blokujący |
| testy jednostkowe | blokujący |
| testy integracyjne zmienianego obszaru | blokujący |
| testy i diff kontraktów | blokujący |
| kierunek importów, deep importy, cykle | blokujący |
| secret scanning | blokujący |
| krytyczne/wysokie SAST i SCA | blokujący według polityki ryzyka |
| wyciek server-only do bundle’a | blokujący |
| E2E krytycznych podróży | blokujący przed release; na PR według kosztu |
| liczba linii, propsów, flag, złożoność | raportowy |
| dyrektywa client w korzeniu | raportowy |
| spadek coverage | raportowy lub blokujący tylko dla ustalonego obszaru krytycznego |

## Jakość bramki

- Każda bramka MUSI być deterministyczna, mieć zrozumiały komunikat i dać się
  uruchomić lokalnie lub w kontenerze.
- Nowa reguła dla legacy MOŻE działać raportowo wyłącznie do ustalonej daty migracji.
- NIE WOLNO obniżać globalnego progu, aby przepuścić pojedynczy PR.
- Heurystyka NIE MOŻE automatycznie blokować merge, jeżeli poprawny wyjątek
  jest częsty i zależy od kontekstu.

## Obsługa wyjątków

Wyjątek MUSI być lokalny, zawierać strukturę z
[`architecture-principles.md`](architecture-principles.md) i wygasać
automatycznie. CI MUSI odrzucać wyjątki po terminie. Wyjątek dłuższy niż
kwartał POWINIEN zostać opisany jako decyzja architektoniczna albo usunięty.

## Definition of Done dla funkcjonalności

Funkcjonalność jest ukończona, gdy:

1. zachowuje granice warstw i runtime;
2. waliduje wejścia i egzekwuje uprawnienia;
3. ma testy sukcesu, błędu i krytycznego ryzyka;
4. ma obsługę loading/error/empty tam, gdzie dotyczy UI;
5. ma timeouty, retry/idempotencję tam, gdzie dotyczy I/O;
6. emituje potrzebne logi, metryki i korelację;
7. nie wprowadza wyjątku bez właściciela i terminu.


Powiązane: [`test-evidence.md`](test-evidence.md),
[`ci-pipeline-architecture.md`](ci-pipeline-architecture.md),
[`architecture-principles.md`](architecture-principles.md),
[`rules-as-gates.md`](rules-as-gates.md).
