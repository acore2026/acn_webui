import { BackendLogEntry, NetworkElementLogGroup, TopologyAgentModel, TopologyLinkModel } from '../types';
import { LanguageMode } from '../i18n';
import { BackendLogPanel } from '../components/BackendLogPanel';
import { NetworkElementLogsPanel } from '../components/NetworkElementLogsPanel';
import { SectionCard } from '../components/SectionCard';

interface NetworkPageProps {
  agents: TopologyAgentModel[];
  links: TopologyLinkModel[];
  backendLogs: BackendLogEntry[];
  backendLogsLoading: boolean;
  backendLogsError: string | null;
  elementLogs: NetworkElementLogGroup[];
  elementLogsLoading: boolean;
  elementLogsError: string | null;
  language: LanguageMode;
}

export const NetworkPage = ({
  agents,
  links,
  backendLogs,
  backendLogsLoading,
  backendLogsError,
  elementLogs,
  elementLogsLoading,
  elementLogsError,
  language
}: NetworkPageProps) => {
  const isZh = language === 'zh';

  return (
    <SectionCard
      eyebrow={isZh ? '网络' : 'Network'}
      title={isZh ? '链路质量' : 'Route Quality'}
      description={isZh ? '面向活动网格的链路级传输视图，重点关注时延暴露与流可用性。' : 'Link-level transport view for the active mesh, focused on latency exposure and stream availability.'}
    >
      <div className="space-y-4">
        <BackendLogPanel
          logs={backendLogs}
          loading={backendLogsLoading}
          error={backendLogsError}
          language={language}
        />

        <NetworkElementLogsPanel
          groups={elementLogs}
          loading={elementLogsLoading}
          error={elementLogsError}
          language={language}
        />
      </div>
    </SectionCard>
  );
};
