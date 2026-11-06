# Runtime agentowy: wymagania przed wyborem frameworka

Zebrano: 2026-11-05. Przegląd: 2026-12-05.
Zebrał: autor zmiany; porównanie nie ma niezależnego benchmarku SDK.
Grounding: dokumentacja producentów wskazana przy wierszach. Wnioski dla
toolkitu są oceną autora, nie wynikami pomiaru skuteczności tych frameworków.

## Porównanie odpowiedzialności

| Punkt odniesienia | Co sprawdzić w dokumentacji i projekcie |
|---|---|
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/running_agents/) | loop narzędzi, handoff, session i serializowane wznowienie; dokumentacja opisuje także integracje durable execution. Oceń wybrany backend i semantykę efektów ubocznych, nie samą obecność historii rozmowy. |
| [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/sessions) | sesje, continue/resume/fork i dostępne mechanizmy przechowywania historii. Sprawdź uprawnienia i wznowienie faktycznej pracy przy awarii procesu, oddzielnie od odtworzenia kontekstu. |
| [Google ADK](https://github.com/google/adk-python/blob/main/docs/guides/sessions/state/index.md) | zakres stanu session/app/user/temp i wybrany backend sesji; zakres przechowywania nie rozstrzyga sam wykonania zewnętrznej operacji po retry. |
| [Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/session-management/) | session management agentów i orchestratorów oraz warunki współbieżności wybranej implementacji; nie zakładaj, że wielu piszących do jednej rozmowy jest poprawnym domyślnym użyciem. |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence) | checkpointer/store, granice checkpointów i odzyskiwanie; osobno sprawdź deterministyczne odtworzenie i idempotencję operacji spoza grafu. |

Nie wykonano porównania wydajności ani migracji aplikacji. Nie wszystkie
projekty potrzebują tych samych usług, infrastruktury i modelu stanu.

## Dobór dla konkretnego zadania

Krótki przewidywalny workflow z limitem może korzystać z małego runnera lub
wybranego SDK. Trwała kolejka, wieloetapowe przerwania, praca człowieka i
odzyskiwanie niepewnego wykonania wymagają jawnego stanu i testów awarii.
Liczba wywołań modelu nie jest kryterium wystarczającym do narzucenia grafu.

Próba odbioru obejmuje: crash przed/po efekcie ubocznym, wznowienie bez
duplikatu, brakujący wynik workera, limit czasu/kosztu, odbiór nieudanego
narzędzia, izolację uprawnień i zmianę uzgodnionego zakresu. Zachowanie po
niepewnym wykonaniu musi być określone; „exactly once” nie wynika z samego
posiadania checkpointu.

Mały adapter procesu toolkitu rozwiązuje kolejkę lokalnych nodów i receipts.
Nie jest zamiennikiem wszystkich funkcji SDK, sandboxem ani trwałym silnikiem
zewnętrznych transakcji. Jego użycie w projekcie wymaga podłączenia do
uruchamiania/wznowienia pracy i potwierdzonej integracji. Tej konfiguracji nie
zastępuje nowy akapit w instrukcji modelu.
