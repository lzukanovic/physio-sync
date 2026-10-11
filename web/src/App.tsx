import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import Capture from "./routes/Capture";
import Devices from "./routes/Devices";
import Studies from "./routes/Studies";
import Take from "./routes/Take";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/capture" replace />} />
        <Route path="/capture" element={<Capture />} />
        <Route path="/studies" element={<Studies />} />
        <Route path="/takes/:id" element={<Take />} />
        <Route path="/devices" element={<Devices />} />
      </Route>
    </Routes>
  );
}
