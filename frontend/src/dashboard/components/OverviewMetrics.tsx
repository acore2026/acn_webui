import { MetricCardModel } from '../types';
import { MetricCard } from './MetricCard';

interface OverviewMetricsProps {
  metrics: MetricCardModel[];
}

export const OverviewMetrics = ({ metrics }: OverviewMetricsProps) => {
  return (
    <section className="grid gap-4 xl:grid-cols-3">
      {metrics.map((metric) => (
        <MetricCard key={metric.id} metric={metric} />
      ))}
    </section>
  );
};
