# React Architect Context

## Project Context

This is a React/TypeScript project. When planning, account for:
- Component hierarchy depth and prop drilling complexity
- Client vs. server component boundaries (if using Next.js/RSC)
- Bundle size implications of dependencies and code splitting boundaries
- The 4-file rule: tasks touching more than 3 files must be split into smaller tasks

## Component Hierarchy Complexity

When planning tasks that involve React patterns, account for their specific complexity:

- **Presentational components**: Pure UI with props (Haiku). Stateless, no side effects.
- **Container components / custom hooks with complex state**: State machines, multi-step forms, complex reducer logic (Sonnet). Individual state updates can be Haiku.
- **Context providers**: Simple value providers are Haiku. Providers with complex derived state, memoization strategies, or multiple context composition are Sonnet.
- **Error boundaries**: Basic error boundary is Haiku. Recovery strategies, retry logic, and fallback UI coordination is Sonnet.
- **Route-level components**: Simple page layouts are Haiku. Pages with data loading, guards, and parallel data fetching are Sonnet.

## State Management Complexity

- **useState/useReducer**: Local component state is Haiku. Complex reducer with many action types is Sonnet.
- **React Context**: Simple theme/auth context is Haiku. Multi-context composition with performance optimization is Sonnet.
- **Redux/Zustand/Jotai**: Slice/store definition is Haiku. Middleware, async thunks, normalized state with selectors is Sonnet.
- **TanStack Query/SWR**: Basic query hook is Haiku. Optimistic updates, cache invalidation strategies, infinite queries are Sonnet.
- **Form state (React Hook Form/Formik)**: Simple forms are Haiku. Multi-step forms with validation, conditional fields, and dynamic schemas are Sonnet.

## API Layer Patterns

- **REST client setup**: Axios/fetch wrapper with interceptors is Sonnet. Individual endpoint functions are Haiku.
- **GraphQL client**: Apollo/urql client configuration is Sonnet. Individual queries/mutations are Haiku.
- **WebSocket integration**: Connection lifecycle and reconnection logic is Sonnet. Individual message handlers are Haiku.
- **Authentication flow**: Token refresh, OAuth flows, session management is Sonnet. Protected route wrappers are Haiku.

## SSR/SSG Considerations (Next.js)

- **Static pages (SSG)**: Simple `getStaticProps` pages are Haiku. ISR with revalidation strategies is Sonnet.
- **Server Components**: Data-fetching server components are Haiku. Mixing server/client boundaries with streaming is Sonnet.
- **API routes**: Simple CRUD endpoints are Haiku. Routes with middleware, validation, and error handling chains are Sonnet.
- **Middleware**: Request/response middleware with auth checks, redirects, and geolocation is Sonnet.

## React-Specific Decomposition Notes

- Components are natural Haiku boundaries -- define the interface (props type), then implement the component as a Haiku task
- Custom hooks are excellent extraction points -- complex logic in a hook (Sonnet to design), then components that use it (Haiku)
- Context providers should be defined separately from consumers -- provider setup (may be Sonnet), consumer usage (Haiku)
- Test files pair 1:1 with source files -- component + test can be a single Haiku task if the component is simple
- Shared types/interfaces should be defined first (Haiku), then implementations that depend on them
