import { createApiClient } from "./client.ts";
import { getServerApiOrigin } from "./server-config.server.ts";

export const serverApiClient = createApiClient({ origin: getServerApiOrigin() });
