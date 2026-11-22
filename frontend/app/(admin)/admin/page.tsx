import type { Metadata } from "next";
import { Dashboard } from "./Dashboard";

export const metadata: Metadata = { title: "Ringkasan" };

export default function AdminHomePage() {
  return <Dashboard />;
}
