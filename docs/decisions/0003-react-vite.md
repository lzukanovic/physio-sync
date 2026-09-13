# 0003 — React + Vite rather than Next.js

**Context.** The application has multiple pages and menus, and Next.js has good
tooling and generation support.

**Decision.** React with Vite and React Router, built to static files served by
FastAPI.

**Consequences.** Next is a full-stack framework; using it here would mean
switching off server components, route handlers, SSR, and its data-fetching
model to use one feature, file-based routing. Each of those becomes a rule to
enforce and a way for a session to drift. React Router provides the same
multi-page structure with nothing to suppress, and no Node runtime on the lab PC.
