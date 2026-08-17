## What this changes

## Checklist

- [ ] `make test && make lint` passes
- [ ] Schema changes (if any) updated in all three places: Pydantic model,
      TypeScript mirror, `make schema`
- [ ] New failure modes come with a deterministic sample incident and tests
- [ ] The deterministic diagnosis loop remains LLM-free
