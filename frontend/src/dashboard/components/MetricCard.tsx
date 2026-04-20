import { MetricCardModel } from '../types';
import { PulseIcon, SignalIcon, TaskIcon } from './icons';

interface MetricCardProps {
  metric: MetricCardModel;
}

const iconByMetric = {
  latency: PulseIcon,
  agents: SignalIcon,
  tasks: TaskIcon
};

const toneMap = {
  healthy: {
    dot: 'bg-emerald-400',
    badge: 'theme-badge-emerald'
  },
  warning: {
    dot: 'bg-amber-400',
    badge: 'theme-badge-amber'
  },
  critical: {
    dot: 'bg-rose-400',
    badge: 'theme-badge-rose'
  }
};

export const MetricCard = ({ metric }: MetricCardProps) => {
  const Icon = iconByMetric[metric.id as keyof typeof iconByMetric] ?? PulseIcon;
  const tone = toneMap[metric.tone];

  return (
    <article className="glass-panel group relative overflow-hidden p-5 transition duration-300 hover:-translate-y-1 hover:border-cyan-300/25 hover:bg-white/[0.08] hover:shadow-glow">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent opacity-0 transition group-hover:opacity-100" />

      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="theme-copy text-sm font-medium">{metric.title}</p>
          <div className="mt-3 flex items-center gap-3">
            <h3 className="theme-title text-3xl font-semibold tracking-tight">{metric.value}</h3>
            <span className={`h-2.5 w-2.5 rounded-full ${tone.dot} shadow-[0_0_16px_currentColor]`} />
          </div>
        </div>
        <div className="theme-icon-shell theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
          <Icon className="h-6 w-6" />
        </div>
      </div>

      <p className="theme-soft mt-4 text-sm leading-6">{metric.detail}</p>

      {metric.trend ? (
        <div className={`mt-4 inline-flex rounded-full border px-3 py-1 text-xs font-medium ${tone.badge}`}>
          {metric.trend}
        </div>
      ) : null}
    </article>
  );
};
