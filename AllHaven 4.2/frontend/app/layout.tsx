import type { Metadata, Viewport } from "next";
import { PreferenceHydrator } from "@/components/layout/PreferenceHydrator";
import { AppDialogProvider } from "@/components/ui/AppDialog";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Geist for UI (Aurora Glass), Geist Mono for labels/metrics, Inter fallback. */}
        <link
          href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
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
