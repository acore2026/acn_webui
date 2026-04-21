import { MetricCardModel } from '../types';
import { LanguageMode } from '../i18n';
import { PulseIcon, SignalIcon, TaskIcon } from './icons';

interface MetricCardProps {
  metric: MetricCardModel;
  language: LanguageMode;
  onSelect: (metricId: string) => void;
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

const metricCopy = {
  en: {
    latency: {
      title: 'System Latency',
      detail: 'Average active link latency from current backend mesh state.',
      waiting: 'Waiting for active routes'
    },
    agents: {
      title: 'Active Agents',
      detail: 'Live agent roster derived from the backend database and in-memory status cache.'
    },
    tasks: {
      title: 'Running Tasks',
      detail: 'Current workload count backed by the tasks table and active agent state.'
    }
  },
  zh: {
    latency: {
      title: '系统时延',
      detail: '基于当前后端网格状态计算的活动链路平均时延。',
      waiting: '等待活动链路'
    },
    agents: {
      title: '在线智能体',
      detail: '根据后端数据库与运行时缓存汇总得到的智能体实时名册。'
    },
    tasks: {
      title: '运行中任务',
      detail: '基于 tasks 表和智能体活动状态计算的当前工作负载数量。'
    }
  }
} as const;

export const MetricCard = ({ metric, language, onSelect }: MetricCardProps) => {
  const Icon = iconByMetric[metric.id as keyof typeof iconByMetric] ?? PulseIcon;
  const tone = toneMap[metric.tone];
  const localized = metricCopy[language][metric.id as keyof typeof metricCopy.en];
  const title = localized?.title ?? metric.title;
  const detail = localized?.detail ?? metric.detail;
  const trend = language === 'zh' && metric.id === 'latency' && metric.trend === metricCopy.en.latency.waiting
    ? metricCopy.zh.latency.waiting
    : metric.trend;
  const isInteractive = metric.id === 'agents' || metric.id === 'tasks';

  return (
    <article
      className={[
        'glass-panel group relative overflow-hidden p-5 transition duration-300 hover:-translate-y-1 hover:border-cyan-300/25 hover:bg-white/[0.08] hover:shadow-glow',
        isInteractive ? 'cursor-pointer' : ''
      ].join(' ')}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent opacity-0 transition group-hover:opacity-100" />

      <button
        type="button"
        onClick={() => {
          if (isInteractive) {
            onSelect(metric.id);
          }
        }}
        disabled={!isInteractive}
        className="w-full text-left disabled:cursor-default"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="theme-copy text-sm font-medium">{title}</p>
            <div className="mt-3 flex items-center gap-3">
              <h3 className="theme-title text-3xl font-semibold tracking-tight">{metric.value}</h3>
              <span className={`h-2.5 w-2.5 rounded-full ${tone.dot} shadow-[0_0_16px_currentColor]`} />
            </div>
          </div>
          <div className="theme-icon-shell theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
            <Icon className="h-6 w-6" />
          </div>
        </div>

        <p className="theme-soft mt-4 text-sm leading-6">{detail}</p>

        {trend ? (
          <div className={`mt-4 inline-flex rounded-full border px-3 py-1 text-xs font-medium ${tone.badge}`}>
            {trend}
          </div>
        ) : null}
      </button>
    </article>
  );
};
