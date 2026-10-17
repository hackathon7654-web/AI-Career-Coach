import type { ReactNode } from 'react';
import { Header } from './Header';
import { Footer } from './Footer';

interface AppLayoutProps {
  children: ReactNode;
}

export const AppLayout = ({ children }: AppLayoutProps) => {
  return (
    <div className="min-h-screen flex flex-col bg-[#F7F9FB] text-[#191C1E]">
      <Header />
      <main className="flex-1 w-full pt-[84px] sm:pt-24 pb-12 sm:pb-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col">
        {children}
      </main>
      <Footer />
    </div>
  );
};
