// MSW server setup (Task T4). `setup.ts` owns the beforeAll/afterEach/afterAll
// lifecycle; every test file calls `server.use(...)` to override the default
// handler for its own scenario, never `server.listen()`/`close()` directly.
import { setupServer } from "msw/node";
import { handlers } from "./mswHandlers";

export const server = setupServer(...handlers);
