# Konwencja: TypeScript i JavaScript

Zakres: **typowanie jako warstwa obronna i walidacja na granicy zaufania.**
Reguły dotyczą kodu aplikacyjnego; konfiguracja i małe skrypty mają własne
ustępstwa, wypisane niżej.

Rozdział ról:

- [`architecture-principles.md`](architecture-principles.md) — definicja
  granicy zaufania.
- [`api-contract-design.md`](api-contract-design.md) — schemat jako kontrakt
  między usługami; ta konwencja mówi, co dzieje się z danymi **po**
  przekroczeniu granicy.
- [`code-structure.md`](code-structure.md) — moduły i zależności.

---

## Reguły

- Nowy kod aplikacyjny POWINIEN używać TypeScriptu w trybie `strict`.
- `noUncheckedIndexedAccess` i `exactOptionalPropertyTypes` POWINNY być
  włączone dla nowych projektów. Migracja istniejącego repozytorium może
  przebiegać katalogami.
- Dane z HTTP, storage, webhooka, kolejki, pliku i zmiennych środowiskowych
  MUSZĄ wejść jako `unknown` i przejść walidację runtime.
- `any`, `as X` i non-null assertion `!` NIE MOGĄ służyć do omijania modelu
  typów. Każde użycie w kodzie produkcyjnym wymaga lokalnego uzasadnienia.
- Typ transportowy, typ ORM i typ domenowy MUSZĄ pozostać rozdzielone, jeżeli
  mają inne reguły lub cykle zmian.
- Stany wzajemnie wykluczające się POWINNY być modelowane unią rozłączną.
- Promise MUSI zostać `await`, zwrócony lub jawnie oznaczony jako kontrolowane
  fire-and-forget.
- JavaScript MOŻE pozostać w konfiguracji i małych skryptach, ale nie zwalnia
  to z walidacji granic.

```ts
type AsyncData<T> =
  | { status: "loading" }
  | { status: "error"; error: AppError }
  | { status: "success"; data: T };
```

Źle:

```ts
function parseOrder(body: any): Order {
  return body as Order;
}
```

Dobrze:

```ts
const CreateOrderSchema = z.object({
  customerId: z.string().uuid(),
  quantity: z.number().int().positive(),
});

function parseCreateOrder(body: unknown): CreateOrderInput {
  return CreateOrderSchema.parse(body);
}
```

Duże repozytoria MOGĄ używać TypeScript Project References do fizycznego
odzwierciedlenia granic i kolejności budowania. Oficjalna dokumentacja
wskazuje, że references dzielą program na mniejsze projekty i pomagają
egzekwować logiczny podział ([TypeScript
Handbook](https://www.typescriptlang.org/docs/handbook/project-references.html)).

## Egzekwowanie

`tsc --noEmit`, lint typowany, zakaz nieobsłużonych Promise i testy schematów
granicznych MUSZĄ blokować merge. Liczba typów generycznych lub złożoność typu
jest sygnałem do review, nie bramką.


Powiązane: [`architecture-principles.md`](architecture-principles.md),
[`code-structure.md`](code-structure.md),
[`api-contract-design.md`](api-contract-design.md),
[`rules-as-gates.md`](rules-as-gates.md).
