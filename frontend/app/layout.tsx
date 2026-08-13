import type { Metadata, Viewport } from "next";
import { connection } from "next/server";
import { Geist, Geist_Mono, Inter } from "next/font/google";
import { PreferenceHydrator } from "@/components/layout/PreferenceHydrator";
import { AppDialogProvider } from "@/components/ui/AppDialog";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "AllHaven Command Center",
  description: "Modular AI command center for personal and company productivity.",
};

// Proper mobile scaling + dark browser chrome on phones/tablets.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#06070E",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Nonces are per request, so the web production build must render documents
  // dynamically. The Capacitor target remains a fully static export and has no
  // HTTP response headers/middleware to nonce.
  if (process.env.NODE_ENV === "production" && process.env.BUILD_TARGET !== "mobile") {
    await connection();
  }

  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable} ${inter.variable}`}>
      <body>
        <ToastProvider>
          <AppDialogProvider>
            <PreferenceHydrator />
            {children}
          </AppDialogProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
