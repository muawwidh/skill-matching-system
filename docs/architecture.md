# Architecture

The project follows the required layered architecture:

```mermaid
flowchart LR
  Frontend["React frontend"] --> ApiRoutes["FastAPI routes"]
  ApiRoutes --> Services["Services"]
  Services --> Repositories["Repositories"]
  Repositories --> Database["PostgreSQL / pgvector"]
  Services --> NLP["NLP modules"]
  Services --> Taxonomy["Taxonomy modules"]
  Services --> Matching["Matching modules"]
  Services --> Evaluation["Evaluation modules"]
```

Phase 1 implements the application shell, authentication, role-aware dependencies, database setup,
and deployment scaffolding. Later phases should extend the existing service and repository boundaries
instead of placing business logic in route handlers.
