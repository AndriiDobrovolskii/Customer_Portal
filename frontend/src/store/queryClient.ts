// TanStack Query client instance shared by the whole app (App.tsx wires the
// <QueryClientProvider>). Test files construct their own isolated
// QueryClient per render (test/test-utils.tsx) rather than importing this
// singleton, so state never leaks between tests.
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1 },
    mutations: { retry: 0 },
  },
});
