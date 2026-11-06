# Konwencja: granice runtime i serwer–klient

Stack-agnostic w warstwie zasad, z przykładami w TypeScript. Zakres: **do
którego środowiska uruchomieniowego należy moduł, co wolno przekazać przez
granicę procesu i jak nie wypuścić kodu serwerowego ani sekretu do bundla
klienta.**

Rozdział ról:

- [`architecture-principles.md`](architecture-principles.md) — definicja
  granicy runtime/bundla.
- [`third-party-assets-privacy.md`](third-party-assets-privacy.md) — co bundle
  **wysyła** do osób trzecich; ta konwencja mówi, co bundle **zawiera**.
- [`ci-cd.md`](ci-cd.md) — sekrety w pipelinie i w artefaktach.

---

## Reguły

- Każdy moduł MUSI należeć do runtime’u: klienta, serwera, workera, skryptu
  albo kodu rzeczywiście współdzielonego.
- Dyrektywa lub entry point kodu klienckiego MUSI znajdować się możliwie nisko
  w drzewie. Oznaczenie layoutu lub korzenia jako klienta jest sygnałem
  architektonicznym do review.
- Kod klienta NIE MOŻE bezpośrednio ani pośrednio importować sterowników baz,
  API Node, sekretów, administracyjnych SDK ani modułów uprzywilejowanych.
- Dostęp do bazy, tokenów usługowych i ostateczna kontrola uprawnień MUSZĄ
  odbywać się na serwerze.
- Dane przekraczające granicę serwer-klient MUSZĄ być serializowalne, minimalne
  i jawnie mapowane.
- Funkcje, uchwyty połączeń, obiekty ORM i pełne obiekty sesji NIE MOGĄ
  przechodzić przez granicę procesu.
- Współdzielić MOŻNA czyste funkcje, typy i walidatory bez zależności runtime.

Źle:

```ts
// client/orders.ts
import { db } from "@/server/db";
export const listOrders = () => db.order.findMany();
```

Dobrze:

```ts
// server/orders/read-orders.ts
import "server-only";

export async function readOrders(actor: Actor) {
  return ordersRepository.listVisibleTo(actor);
}
```

```ts
// shared/contracts/order-list.ts
export type OrderListItem = {
  id: string;
  status: "new" | "paid" | "shipped";
};
```

## Egzekwowanie

- Importy `db`, `node:*`, modułów sekretów i SDK administracyjnych do klienta
  MUSZĄ blokować merge.
- Analiza produkcyjnego bundle’a MUSI wykrywać wyciek modułów serwerowych i
  wzorców sekretów.
- Dyrektywa kliencka w korzeniu jest sygnałem raportowym, ponieważ czasem
  wynika z ograniczeń frameworka.


Powiązane: [`architecture-principles.md`](architecture-principles.md),
[`frontend-architecture.md`](frontend-architecture.md),
[`ci-cd.md`](ci-cd.md), [`rules-as-gates.md`](rules-as-gates.md).
