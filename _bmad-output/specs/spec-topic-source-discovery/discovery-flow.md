# Discovery Flow

```mermaid
flowchart TD
    A["User types an interest, or picks an\nLLM-invented Step-3 suggestion\n(existing flow, unchanged)"] --> B["Topic created, status = pending\nservices/preferences.py::set_preferences\nonly ids where add_topic reported created=True"]
    B -->|"BackgroundTask - receives db.get_bind(),\nnot the request-scoped session"| K["Topic.color assigned FIRST\nunique + WCAG AA 4.5:1, capped retries\nruns whether or not discovery succeeds"]
    K --> C["Finder LLM proposes RSS candidates\nllm/base.discover_sources, per the\nauthoritative / global-scale / free / on-topic criteria"]
    C -.->|"deferred, not built"| J["Second, independent judge LLM\nsee CLAUDE.md open technical risk"]
    C -->|"Refusal or exhausted LLMError:\nlogged, terminal, color already set"| Z["Topic stays sourceless\naccepted V1 edge case"]
    C --> D["Deterministic validation\nhttp/https scheme check, dedupe, cap,\nthen feedparser fetch+parse with a timeout\nrejects hallucinated / dead / non-feed URLs"]
    D --> E["Source rows created, status = pending\nservices/topic_sourcing.py\nURL already owned by another Topic is\nlogged as a collision, not a success"]
    E --> F["Pipeline queries widen:\nSource.status in (approved, pending),\nTopic.status not rejected\nfetcher.py + relevance.py,\nstill scoped by subscribed_topic_ids"]
    F --> G["Digest built for users subscribed\nto this topic only"]
    F --> H["Existing admin queue:\napprove/reject each Source\n(admin.py, unchanged) - now a post-hoc\nremoval rather than a gate"]
```

Dashed edge = explicitly not built in this feature (CAP boundary, see SPEC.md Constraints/Non-goals). Color assignment sits ahead of the finder deliberately: it must not depend on an LLM call succeeding (CAP-2). Everything else is a strict top-to-bottom sequence gated by the step above it; no branch fans back upstream.
