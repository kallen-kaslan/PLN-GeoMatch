import { RouterProvider } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { router } from "@/routes";
import { useEffect } from "react";
import { useAppStore } from "@/store/app";
import { sessionChannel } from "@/lib/accounts";

const App = () => {
  useEffect(() => {
    const expired = () => useAppStore.getState().endSession();
    const changed = () => { useAppStore.getState().endSession(); void useAppStore.getState().initialize(); };
    window.addEventListener("geomatch:unauthorized", expired);
    sessionChannel?.addEventListener("message", changed);
    void useAppStore.getState().initialize();
    return () => { window.removeEventListener("geomatch:unauthorized", expired); sessionChannel?.removeEventListener("message", changed); };
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
};

export default App;
