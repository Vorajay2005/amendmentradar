import { MotionConfig } from "framer-motion";
import { Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { ErrorState } from "./components/ui";
import About from "./pages/About";
import Analyze from "./pages/Analyze";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import Results from "./pages/Results";

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Landing />} />
          <Route path="analyze" element={<Analyze />} />
          <Route path="results" element={<Results />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="about" element={<About />} />
          <Route path="*" element={<div className="px-4 py-16"><ErrorState kind="empty" title="Page not found" message="That page doesn't exist." /><p className="mt-6 text-center"><Link className="underline" to="/">Go home</Link></p></div>} />
        </Route>
      </Routes>
    </MotionConfig>
  );
}
