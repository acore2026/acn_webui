import { DashboardMockData } from '../types';
import { LanguageMode } from '../i18n';
import { CriticalMessagesFeed } from '../components/CriticalMessagesFeed';
import { ElementStatusSection } from '../components/ElementStatusSection';
import { OverviewMetrics } from '../components/OverviewMetrics';
import { TopologyMap } from '../components/TopologyMap';

interface OverviewPageProps {
  data: DashboardMockData;
  language: LanguageMode;
  onMetricSelect: (metricId: string) => void;
}

export const OverviewPage = ({
  data,
  language,
  onMetricSelect
}: OverviewPageProps) => {
  return (
    <div className="flex min-h-[calc(100vh-10rem)] flex-col gap-6">
      <OverviewMetrics
        metrics={data.metrics}
        language={language}
        onMetricSelect={onMetricSelect}
      />
      <ElementStatusSection elements={data.elements} language={language} />
      <div className="min-h-[480px] flex-1">
        <TopologyMap
          nodes={data.messageFlow.nodes}
          edges={data.messageFlow.edges}
          language={language}
        />
      </div>
      <div className="h-[360px]">
        <CriticalMessagesFeed messages={data.messages} language={language} />
      </div>
    </div>
  );
};
