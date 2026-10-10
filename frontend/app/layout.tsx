import type { Metadata } from "next";
import "./globals.css";
import "./themes.css";
import { AuthProvider } from "@/components/auth";
import { Shell } from "@/components/shell";
import { THEME_BOOT, ThemeProvider } from "@/components/theme";
import { ToastProvider } from "@/components/ui";

export const metadata: Metadata = {
  title: "Asclepius · Clinical intelligence platform",
  description: "Synthetic-data healthcare IT platform: FHIR R4, HL7 v2, ABDM-aligned consent and governed clinical AI.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} /></head>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 focus:text-black">Skip to content</a>
        <div className="aurora"><i /><i /><i /></div>
        <div className="grid-fade" />
        <div className="grain" />
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <Shell>{children}</Shell>
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
