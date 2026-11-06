# Konwencja: warstwy backendu i granice domeny

Zasady są stack-agnostic, przykłady w Pythonie. Zakres: **podział na warstwy,
kierunek zależności wewnątrz backendu, granice transakcji i publikacja zdarzeń.**

Rozdział ról:

- [`architecture-principles.md`](architecture-principles.md) — granice i
  kierunek zależności ogólnie.
- [`code-structure.md`](code-structure.md) — moduły, funkcje i klasy wewnątrz warstwy.
- [`api-contract-design.md`](api-contract-design.md) — kontrakt na zewnątrz; ta
  konwencja kończy się tam, gdzie zaczyna się transport.

---

## Warstwy

```text
transport/adapters -> application use cases -> domain
                              |
                              v
                            ports
                              ^
                              |
                       infrastructure
```

- `transport`: HTTP, CLI, webhook i kolejka; waliduje oraz mapuje.
- `application`: przypadki użycia, autoryzacja działania i granice transakcji.
- `domain`: reguły biznesowe, encje, value objects i zdarzenia.
- `ports`: kontrakty repozytoriów, zegara, komunikacji i storage.
- `infrastructure`: ORM, baza, broker i zewnętrzni klienci.

## Reguły

- Domena NIE MOŻE importować frameworka webowego, ORM, klienta HTTP, brokera
  ani konfiguracji środowiska.
- Każdy przypadek użycia zapisujący dane MUSI definiować granicę transakcji.
- Transakcja MUSI być krótka i obejmować tylko atomową zmianę. Wolne I/O
  sieciowe wewnątrz transakcji jest zabronione.
- Publikacja zdarzenia wynikającego z commitu MUSI używać transactional outbox
  albo mechanizmu o równoważnej gwarancji.
- Obiekty ORM NIE MOGĄ być kontraktem domeny, API ani wiadomości.
- Usługa aplikacyjna POWINNA ograniczać się do orkiestracji zależności; reguły
  i niezmienniki należą do domeny.
- Klasy POWINNY reprezentować encje, value objects i stanowych
  współpracowników. Bezstanowe transformacje pozostają funkcjami.
- Prosty CRUD MOŻE ominąć rozbudowany model domenowy, lecz nadal wymaga
  walidacji, autoryzacji, transakcji i mapowania transportu.
- Publiczne funkcje i granice modułów MUSZĄ być typowane. PEP 8 pozostaje
  bazowym przewodnikiem stylu Pythona ([PEP
  8](https://peps.python.org/pep-0008/)), ale formatter projektu jest źródłem
  prawdy dla formatowania.

```py
class CreateOrder:
    def __init__(self, uow: UnitOfWork, outbox: OutboxPort) -> None:
        self._uow = uow
        self._outbox = outbox

    def execute(self, command: CreateOrderCommand, actor: Actor) -> OrderId:
        actor.require("orders:create")
        with self._uow.transaction():
            order = Order.create(command.customer_id, command.items)
            self._uow.orders.add(order)
            self._outbox.add(OrderCreated(order.id))
        return order.id
```

## Egzekwowanie

Formatter, lint, typecheck i testy importów MUSZĄ blokować merge. Import
frameworka lub ORM w `domain/` MUSI zostać wykryty mechanicznie. Testy
integracyjne MUSZĄ obejmować rollback, współbieżność, outbox i migracje dla
zmienianego obszaru.

Powiązane: [`architecture-principles.md`](architecture-principles.md),
[`code-structure.md`](code-structure.md),
[`api-contract-design.md`](api-contract-design.md),
[`reliability-and-observability.md`](reliability-and-observability.md).
