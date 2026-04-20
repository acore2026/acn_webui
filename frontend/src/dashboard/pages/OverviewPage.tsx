import { DashboardMockData } from '../types';
import { CriticalMessagesFeed } from '../components/CriticalMessagesFeed';
import { OverviewMetrics } from '../components/OverviewMetrics';
import { TopologyMap } from '../components/TopologyMap';

interface OverviewPageProps {
  data: DashboardMockData;
}

export const OverviewPage = ({ data }: OverviewPageProps) => {
  return (
    <div className="flex min-h-[calc(100vh-10rem)] flex-col gap-6">
      <OverviewMetrics metrics={data.metrics} />
      <div className="min-h-[480px] flex-1">
        <TopologyMap agents={data.topology.agents} links={data.topology.links} />
      </div>
      <div className="h-[360px]">
        <CriticalMessagesFeed messages={data.messages} />
      </div>
    </div>
  );
};
