import { ReactNode } from 'react';

interface SectionCardProps {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}

export const SectionCard = ({ eyebrow, title, description, children }: SectionCardProps) => {
  return (
    <section className="glass-panel overflow-hidden">
      <header className="border-b border-[color:var(--border-soft)] px-6 py-5">
        <p className="panel-eyebrow">{eyebrow}</p>
        <h2 className="theme-title mt-2 text-2xl font-semibold">{title}</h2>
        <p className="theme-soft mt-1 text-sm">{description}</p>
      </header>
      <div className="p-6">{children}</div>
    </section>
  );
};
