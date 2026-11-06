# Konwencja: architektura frontendu

Stack-agnostic w warstwie zasad, z przykładami w React/TypeScript. Zakres:
**warstwy i kierunek zależności, dekompozycja komponentów oraz rodzaje stanu
i miejsce pobierania danych.**

Rozdział ról:

- [`architecture-principles.md`](architecture-principles.md) — granice,
  priorytet reguł, format wyjątku.
- [`design-system-foundations.md`](design-system-foundations.md) — jak
  **wygląda** komponent: tokeny, stany, dostępność.
- Ta konwencja — **gdzie przebiega granica** między komponentami i w którą
  stronę wolno kierować zależności.

---

## Model trzech warstw

Zamiast atomów, molekuł i organizmów frontend używa trzech warstw:

| Warstwa | Wie o | Nie wie o |
|---|---|---|
| `shared` / prymitywy | tokenach, dostępności, neutralnych narzędziach | domenie, API biznesowym, routingu |
| `features` / domena UI | modelu domeny i konkretnym przypadku użycia | ekranie lub trasie, w której zostanie osadzona |
| `app` / widoki i trasy | routingu, orkiestracji oraz składaniu funkcji | brak wyższej warstwy |

Dozwolony kierunek to `app -> features -> shared`. Zależności w przeciwnym
kierunku są zabronione.

## Reguły

- `app` MUSI ograniczać się do routingu, layoutów, providerów oraz składania
  funkcjonalności.
- `features` MUSI grupować kod według przypadku użycia lub obszaru domenowego.
- `shared` MUSI pozostać neutralne domenowo i niezależne od tras.
- Widok, lokalne hooki, schematy, adaptery, testy i typy używane przez jedną
  funkcję MUSZĄ być kolokowane z tą funkcją.
- Feature NIE MOŻE wykonywać deep importu do wnętrza innego feature’a.
- Kod wspólny POWINIEN trafić do `shared` po trzecim stabilnym użyciu.
  Wcześniejsze wydzielenie wymaga uzasadnienia, że jest to prymityw platformy.
- Rozmiar pliku NIE JEST regułą architektoniczną. Plik 300-liniowy z jednym
  powodem zmiany może być poprawniejszy niż plik 80-liniowy z pięcioma trybami.

## Przykład

```text
src/
  app/
    routes/
    providers/
  features/
    orders/
      list/
        OrderListFeature.tsx
        OrderListView.tsx
        order-list.query.ts
        order-list.test.tsx
      public.ts
  shared/
    ui/
    validation/
    formatting/
```

Źle:

```ts
// shared/ui/OrderPaymentButton.tsx
import { useOrderPayment } from "@/features/orders/payment/useOrderPayment";
```

Dobrze:

```tsx
// features/orders/payment/OrderPaymentButton.tsx
export function OrderPaymentButton({ orderId }: Props) {
  const payment = useOrderPayment(orderId);
  return <Button onClick={payment.start}>Zapłać</Button>;
}
```

## Egzekwowanie

- Naruszenie kierunku zależności, deep import między feature’ami i cykl
  importów MUSZĄ blokować merge.
- Rozmiar pliku, liczba propsów i głębokość JSX są wyłącznie sygnałami raportowymi.
- Publiczne API feature’a POWINNO być jawne i małe, np. `public.ts`, bez `export *`.


---

# Komponenty i kompozycja

## Granica komponentu

Granica komponentu jest granicą zmiany, nie granicą wizualną. Dwie części
zostają razem, jeżeli zmieniają się z tego samego powodu, w tym samym tempie i
zwykle przez ten sam zespół.

## Reguły dekompozycji

- Komponent MUSI mieć jeden dominujący powód zmiany.
- Komponent POWINIEN zostać podzielony, gdy zawiera niezależne uprawnienia,
  źródła danych, stany ładowania/błędu, kontrakty interakcji lub cykle zmian.
- Więcej niż 5–7 propsów, trzy flagi logiczne, prop drilling przez trzy poziomy
  i test wymagający połowy aplikacji są sygnałami, nie automatycznymi błędami.
- Kombinacje flag POWINNY zostać zastąpione jawnym `variant`, osobnymi
  komponentami lub kompozycją.
- `children`, sloty i małe jawne podkomponenty są preferowane wobec komponentu
  przyjmującego kilkanaście opcji.
- Kontekst jest dopuszczalny po rozważeniu kompozycji. NIE WOLNO używać go
  wyłącznie do uniknięcia dwóch poziomów propsów.

Źle:

```tsx
<DataTable
  selectable
  editable
  expandable
  paymentMode
  showOrderActions
  mobileStacked
/>
```

Dobrze:

```tsx
<OrderTable>
  <OrderTable.Selection />
  <OrderTable.Columns>
    <OrderNumberColumn />
    <OrderStatusColumn />
    <OrderActionsColumn />
  </OrderTable.Columns>
</OrderTable>
```

## Efekty i stan pochodny

- `useEffect` MUSI synchronizować React z systemem zewnętrznym: siecią,
  subskrypcją, API przeglądarki, telemetryką lub biblioteką imperative.
- `useEffect` NIE MOŻE służyć do przepisywania propsów do stanu, filtrowania
  list, deterministycznej walidacji lub składania wartości pochodnych.
- Wartość pochodna MUSI być obliczana podczas renderu, chyba że istnieje
  zmierzony powód do cache’owania.

Źle:

```tsx
const [visible, setVisible] = useState<Product[]>([]);
useEffect(() => {
  setVisible(products.filter((p) => p.name.includes(query)));
}, [products, query]);
```

Dobrze:

```tsx
const visible = products.filter((p) => p.name.includes(query));
```

## Memoizacja

Ręczne `memo`, `useMemo` i `useCallback` POWINNY wynikać z profilu wydajności
albo z wymogu stabilności referencji w API. Nie są domyślnym stylem kodu. Gdy
React Compiler jest włączony, automatycznie memoizuje wartości, funkcje i
komponenty, przez co potrzeba ręcznej memoizacji jest mniejsza ([oficjalna
dokumentacja React Compiler](https://react.dev/learn/react-compiler)).

Stan włączenia kompilatora i wyjątki zależne od wersji MUSZĄ znajdować się w
dokumentacji technicznej projektu, nie w tej konwencji.

## Egzekwowanie

Lint MUSI wykrywać naruszenia Rules of Hooks i brakujące zależności efektów.
Liczba propsów, linii i flag pozostaje raportem do review, nigdy samodzielną
bramką.


---

# Stan i dostęp do danych

## Cztery rodzaje stanu

| Rodzaj | Przykłady | Właściciel |
|---|---|---|
| serwera | profil, zamówienie, wyniki | loader/query cache |
| URL | filtry, sortowanie, paginacja, zakładka | router |
| formularza | wartości, walidacja, dirty/touched | formularz |
| UI | modal, zaznaczenie, tryb widoku | najbliższy komponent |

Globalny store jest narzędziem pomocniczym, nie piątym domyślnym miejscem na wszystko.

## Reguły

- Każda wartość MUSI mieć jeden typ stanu i jedno źródło prawdy.
- Stan serwera MUSI zachować semantykę cache, invalidacji, retry i świeżości.
  NIE WOLNO kopiować wyniku query do globalnego store’a tylko po to, aby go
  wyświetlić.
- Stan odtwarzający widok i użyteczny w linku MUSI trafić do URL.
- Stan UI MUSI mieszkać możliwie blisko miejsca użycia.
- Dane potrzebne do renderu MUSZĄ być pobierane na granicy trasy, loadera,
  komponentu serwerowego lub feature’a.
- Liście prezentacyjne POWINNY otrzymywać gotowe dane propsami i nie znać klienta HTTP.
- Wyjątkiem jest lazy loading po interakcji, gdy moment pobrania jest częścią
  zachowania komponentu.
- Mutacja MUSI wskazywać, który cache aktualizuje lub unieważnia oraz co dzieje
  się po częściowej porażce.

Źle:

```tsx
function OrderStatusBadge({ orderId }: { orderId: string }) {
  const order = useQuery(orderQuery(orderId));
  return <Badge>{order.data?.status}</Badge>;
}
```

Dobrze:

```tsx
function OrderDetailsFeature({ orderId }: Props) {
  const order = useOrderQuery(orderId);
  if (order.isLoading) return <OrderSkeleton />;
  if (order.isError) return <OrderError error={order.error} />;
  if (!order.data) return <OrderEmpty />;
  return <OrderDetailsView order={order.data} />;
}
```

## Egzekwowanie

Bezpośredni import klienta HTTP w `shared/ui` MUSI być zabroniony. Review MUSI
wskazać rodzaj nowego stanu i właściciela invalidacji. Stany `loading`,
`error`, `empty` i `success` są częścią kontraktu feature’a.


---

Powiązane: [`architecture-principles.md`](architecture-principles.md),
[`runtime-boundaries.md`](runtime-boundaries.md),
[`code-structure.md`](code-structure.md),
[`rules-as-gates.md`](rules-as-gates.md).
