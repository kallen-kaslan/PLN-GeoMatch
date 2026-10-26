import {
  createBrowserRouter,
  type RouteObject,
} from "react-router-dom";
import Shell from "@/components/layout/Shell";
import LoginPage from "@/pages/Login";
import DashboardPage from "@/pages/Dashboard";
import UploadPage from "@/pages/Upload";
import ProcessPage from "@/pages/Process";
import CandidatesPage from "@/pages/Candidates";
import ResultPage from "@/pages/Result";
import HistoryPage from "@/pages/History";
import AdminPage from "@/pages/Admin";
import MasterPage from "@/pages/Master";
import PdpjPage from "@/pages/Pdpj";
import CorrectionsPage from "@/pages/Corrections";
import CorrectionMapPage from "@/pages/CorrectionMap";

export const routeTree: RouteObject[] = [
  { path: "/login", Component: LoginPage },
  {
    path: "/",
    Component: Shell,
    children: [
      { index: true, Component: DashboardPage },
      { path: "upload", Component: UploadPage },
      { path: "koreksi/:category", Component: CorrectionsPage },
      { path: "koreksi", Component: CorrectionsPage },
      { path: "pdpj", Component: PdpjPage },
      { path: "master/:kind", Component: MasterPage },
      { path: "master", Component: MasterPage },
      { path: "process", Component: ProcessPage },
      { path: "candidates", Component: CandidatesPage },
      { path: "peta-koreksi", Component: CorrectionMapPage },
      { path: "result", Component: ResultPage },
      { path: "history", Component: HistoryPage },
      { path: "admin", Component: AdminPage },
    ],
  },
];

export const router = createBrowserRouter(routeTree);
