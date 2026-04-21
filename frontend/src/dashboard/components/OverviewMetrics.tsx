import { MetricCardModel } from '../types';
import { LanguageMode } from '../i18n';
import { MetricCard } from './MetricCard';

interface OverviewMetricsProps {
  metrics: MetricCardModel[];
  language: LanguageMode;
  onMetricSelect: (metricId: string) => void;
}

export const OverviewMetrics = ({ metrics, language, onMetricSelect }: OverviewMetricsProps) => {
  return (
    <section className="grid gap-4 xl:grid-cols-3">
      {metrics.map((metric) => (
        <MetricCard
          key={metric.id}
          metric={metric}
          language={language}
          onSelect={onMetricSelect}
        />
      ))}
    </section>
  );
};
