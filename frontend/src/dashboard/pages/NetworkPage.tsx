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
  const activeLinks = links.filter((link) => link.active);
  const averageLatency = links.length
    ? Math.round(
        links.reduce((total, link) => total + Number.parseInt(link.latency, 10), 0) / links.length
      )
    : 0;

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

        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="theme-card-muted p-5">
            <h3 className="theme-title text-lg font-semibold">{isZh ? '智能体间链路' : 'Inter-Agent Links'}</h3>
            <div className="mt-4 space-y-3">
              {links.map((link) => (
                <div
                  key={link.id}
                  className="theme-subtle-card flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                >
                  <div>
                    <p className="theme-title text-sm font-medium">
                      {link.source} <span className="theme-muted">{isZh ? '到' : 'to'}</span> {link.target}
                    </p>
                    <p className="theme-muted mt-1 text-xs uppercase tracking-[0.18em]">
                      {link.active ? (isZh ? '活动流' : 'Animated active stream') : (isZh ? '待机路径' : 'Standby path')}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className={[
                        'rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]',
                        link.active
                          ? 'theme-badge-cyan'
                          : 'theme-badge-rose'
                      ].join(' ')}
                    >
                      {link.latency}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid gap-4">
            <div className="theme-card-muted p-5">
              <p className="theme-muted text-xs font-semibold uppercase tracking-[0.22em]">
                Summary
              </p>
              <div className="mt-4 space-y-4">
                <div>
                  <p className="theme-title text-3xl font-semibold">{activeLinks.length}</p>
                  <p className="theme-soft text-sm">{isZh ? '活动链路' : 'Active animated links'}</p>
                </div>
                <div>
                  <p className="theme-title text-3xl font-semibold">{agents.filter((agent) => agent.status === 'offline').length}</p>
                  <p className="theme-soft text-sm">{isZh ? '需要恢复的离线节点' : 'Offline nodes requiring recovery'}</p>
                </div>
                <div>
                  <p className="theme-title text-3xl font-semibold">
                    {averageLatency}ms
                  </p>
                  <p className="theme-soft text-sm">{isZh ? '平均链路时延' : 'Average path latency'}</p>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-white/8 bg-gradient-to-br from-cyan-400/12 to-blue-500/12 p-5">
              <h3 className="theme-title text-lg font-semibold">{isZh ? '建议运维动作' : 'Suggested operator action'}</h3>
              <p className="theme-copy mt-3 text-sm leading-6">
                {isZh ? <>将流量从 <code className="theme-code-chip rounded px-1.5 py-0.5">mission-core {'->'} agent-delta</code> 迁移出去，并在重新纳入生产环之前先对备用通道执行一次健康检查。</> : <>Re-route traffic away from <code className="theme-code-chip rounded px-1.5 py-0.5">mission-core {'->'} agent-delta</code>{' '}and trigger a health check on the standby corridor before re-admitting Delta into the production ring.</>}
              </p>
            </div>
          </div>
        </div>
      </div>
    </SectionCard>
  );
};
