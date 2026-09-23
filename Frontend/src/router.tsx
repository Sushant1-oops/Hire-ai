import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Default was staleTime: 0, so every navigation/remount refetched
        // over the network even for data fetched moments ago — every page
        // felt like a fresh load. 20s lets cached data render instantly on
        // revisits while still keeping things reasonably fresh; queries that
        // need to stay live (e.g. pending application polling) set their own
        // refetchInterval regardless of this.
        staleTime: 20_000,
        // Default is 3 retries with exponential backoff — fine for a flaky
        // network blip, but it means a genuinely down/slow backend takes
        // several seconds longer than necessary to show an error.
        retry: 1,
      },
    },
  });

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
