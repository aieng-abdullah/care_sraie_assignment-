// @ts-ignore
import "./globals.css";

export const metadata = {
  title: "DocIntel - Document Intelligence",
  description: "AI-powered document intelligence system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
