# {{name}}

Stos: {{stack}}.
Kanoniczne instrukcje tego projektu. `AGENTS.md` jest wskaźnikiem.

## Praca

- Przyjęta praca jest w `.claude/backlog.md`; czytaj wskazany rekord, nie cały plik.
- Każde zadanie wieloetapowe ma jeden plan odbioru w backlogu lub jego briefie.
  Zmiana tematu nie kasuje etapów. Przed „gotowe” sprawdź cały zakres i dowody.
- Własna gałąź; merge, push i produkcja wymagają upoważnienia właściciela.
- Bez sekretów i surowych rozmów w repo. Brak wymaganej kontroli to brak dowodu.
- {{parallel_policy}}

## Procedury czytane na żądanie

{{convention_map}}

## Kontrole i bezpieczeństwo

Profil CI: {{ci}}. Kontrole: `python3 .claude/run-checks.py`.
{{ci_policy}}
Security Reviewer: `.claude/agents/security-reviewer.md`; niezależny,
read-only, co najmniej raz na 7 dni i przy zmianach wysokiego ryzyka.
{{production_policy}}

Wygenerowane pliki nie są dowodem odbioru projektu. Dokończ listę
`.claude/bootstrap-verification.md`; generator nie uruchamia kontrolek,
nie instaluje hooków, nie wdraża i nie zatwierdza własnej adopcji.
