# Konwencja: błędy, niezawodność i obserwowalność

Stack-agnostic. Zakres: **model błędów, zachowanie przy wywołaniach
zewnętrznych i asynchronicznych oraz minimum obserwowalności krytycznej
ścieżki.**

Rozdział ról:

- [`progressive-delivery.md`](progressive-delivery.md) — SLO, error budget i
  metryki dostawy w skali procesu; tu chodzi o pojedynczą operację.
- [`api-contract-design.md`](api-contract-design.md) — kontrakt błędu na zewnątrz; ta
  konwencja mówi, co system robi z błędem **wewnątrz**.
- [`production-operations.md`](production-operations.md) — praca z produkcją.

---

## Model błędów

- Każdy błąd MUSI prowadzić do decyzji: zwróć, obsłuż, ponów, skompensuj,
  skieruj do DLQ albo eskaluj.
- Oczekiwane błędy domenowe MUSZĄ być modelowane jawnie, nie jako ogólny
  `Exception` lub `Error`.
- Nieoczekiwany błąd MUSI zachować przyczynę techniczną i identyfikator korelacyjny.
- NIE WOLNO łapać błędu wyłącznie po to, aby go zalogować i zwrócić fałszywy sukces.

## Wywołania zewnętrzne i asynchroniczność

- Każde wywołanie zewnętrzne MUSI mieć timeout.
- Retry MUSI być ograniczony, używać backoffu z jitterem i dotyczyć tylko
  błędów przejściowych.
- Błędy walidacji, autoryzacji i trwałe błędy biznesowe NIE MOGĄ być ponawiane.
- Konsument wiadomości MUSI zakładać co najmniej jednokrotne dostarczenie i być
  idempotentny.
- Wynik niepewny, np. timeout po wysłaniu płatności, MUSI zostać zapisany jako
  niepewny/pending, nie failed lub success bez dowodu.
- Circuit breaker lub degradacja funkcji POWINNY chronić krytyczną ścieżkę
  przed zawodną zależnością.

## Obserwowalność

- Każde żądanie i zadanie asynchroniczne MUSI mieć `traceId` lub `correlationId`.
- Logi MUSZĄ być strukturalne i zawierać nazwę operacji, wynik, czas,
  bezpieczny identyfikator aktora/tenanta i korelację.
- Logi, trace i błędy NIE MOGĄ zawierać haseł, tokenów, danych kart ani
  zbędnych danych osobowych.
- Krytyczne operacje MUSZĄ emitować liczbę, czas trwania i liczbę błędów.
- Krytyczna ścieżka MUSI mieć SLI/SLO i alert oparty na wpływie na użytkownika.
- Readiness i liveness MUSZĄ odpowiadać rzeczywistemu modelowi uruchomienia.
  Liveness nie może powodować pętli restartów z powodu chwilowej awarii
  zależności.

## Testy

Testy MUSZĄ symulować timeout, częściową awarię, powtórne dostarczenie, restart
procesu i brak zależności dla krytycznych operacji. Kontrolowany zegar jest
preferowany wobec `sleep`.


Powiązane: [`progressive-delivery.md`](progressive-delivery.md),
[`production-operations.md`](production-operations.md),
[`api-contract-design.md`](api-contract-design.md),
[`backend-layers.md`](backend-layers.md).
