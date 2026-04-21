import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { LanguageMode } from '../i18n';
import { TopologyAgentModel } from '../types';
import { SectionCard } from '../components/SectionCard';

interface AgentsPageProps {
  agents: TopologyAgentModel[];
  language: LanguageMode;
}

const statusTone = {
  online: 'theme-badge-emerald',
  busy: 'theme-badge-amber',
  offline: 'theme-badge-rose'
};

export const AgentsPage = ({ agents, language }: AgentsPageProps) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const isZh = language === 'zh';
  const statusLabel = {
    online: isZh ? '在线' : 'online',
    busy: isZh ? '忙碌' : 'busy',
    offline: isZh ? '离线' : 'offline'
  };

  useEffect(() => {
    if (selectedAgentId && !agents.some((agent) => agent.id === selectedAgentId)) {
      setSelectedAgentId('');
    }
  }, [agents, selectedAgentId]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedAgentId('');
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const selectedAgent =
    agents.find((agent) => agent.id === selectedAgentId) ?? null;

  const detailDialog =
    selectedAgent && typeof document !== 'undefined'
      ? createPortal(
          <div
            className="fixed inset-0 z-[260] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
            role="presentation"
            onClick={() => setSelectedAgentId('')}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label={`${selectedAgent.name} ${isZh ? '详情' : 'details'}`}
              className="glass-panel max-h-[85vh] w-full max-w-4xl overflow-y-auto p-6 md:p-7"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="relative pr-24">
                <button
                  type="button"
                  onClick={() => setSelectedAgentId('')}
                  className="theme-top-button absolute right-0 top-0 px-4 py-2"
                >
                  {isZh ? '关闭' : 'Close'}
                </button>

                <div>
                  <p className="panel-eyebrow">{isZh ? '智能体详情' : 'Agent Detail'}</p>
                  <h3 className="theme-title mt-2 text-2xl font-semibold">{selectedAgent.name}</h3>
                  <div className="mt-3">
                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${statusTone[selectedAgent.status]}`}>
                      {statusLabel[selectedAgent.status]}
                    </span>
                  </div>
                  <p className="theme-copy mt-2 max-w-3xl text-sm leading-6">{selectedAgent.summary}</p>
                </div>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '角色' : 'Role'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.role}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '区域' : 'Region'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.region}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '吞吐量' : 'Throughput'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.throughput}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '运行中任务' : 'Running Tasks'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.taskCount}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '运行时长' : 'Uptime'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.uptime}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '最后心跳' : 'Last Heartbeat'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.lastHeartbeat}</dd>
                </div>
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                <div>
                  <h4 className="theme-title text-sm font-semibold uppercase tracking-[0.18em]">{isZh ? '能力标签' : 'Capabilities'}</h4>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedAgent.capabilities.map((capability) => (
                      <span
                        key={capability}
                        className="theme-chip rounded-full px-3 py-1 text-xs font-medium"
                      >
                        {capability}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="theme-title text-sm font-semibold uppercase tracking-[0.18em]">{isZh ? '告警与备注' : 'Alerts & Notes'}</h4>
                  <ul className="mt-3 space-y-2">
                    {selectedAgent.alerts.map((alert) => (
                      <li key={alert} className="theme-subtle-card theme-copy px-4 py-3 text-sm leading-6">
                        {alert}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>,
          document.body
        )
      : null;

  return (
    <SectionCard
      id="agents-section"
      eyebrow={isZh ? '智能体' : 'Agents'}
      title={isZh ? '智能体名册' : 'Fleet Roster'}
      description={
        isZh
          ? '点击任意智能体卡片即可打开专属详情窗口，查看其资料、健康状态、能力标签与任务负载。'
          : 'Click an agent card to open a dedicated detail window with its profile, health, capabilities, and task load.'
      }
    >
      <div className="grid gap-4 xl:grid-cols-2">
        {agents.map((agent) => (
          <article
            key={agent.id}
            className={[
              'theme-card-muted overflow-hidden p-5 transition',
              selectedAgent?.id === agent.id
                ? 'theme-nav-active ring-1 ring-cyan-300/25'
                : 'hover:border-cyan-300/20 hover:bg-white/[0.04]'
            ].join(' ')}
          >
            <button
              type="button"
              onClick={() => setSelectedAgentId(agent.id)}
              className="w-full text-left"
              aria-haspopup="dialog"
              aria-expanded={selectedAgent?.id === agent.id}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="theme-title text-lg font-semibold">{agent.name}</h3>
                  <p className="theme-soft mt-1 text-sm">{agent.role}</p>
                </div>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${statusTone[agent.status]}`}>
                  {statusLabel[agent.status]}
                </span>
              </div>
              <dl className="theme-copy mt-5 grid gap-3 text-sm sm:grid-cols-2">
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '区域' : 'Region'}</dt>
                  <dd className="theme-title mt-2 font-medium">{agent.region}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '吞吐量' : 'Throughput'}</dt>
                  <dd className="theme-title mt-2 font-medium">{agent.throughput}</dd>
                </div>
              </dl>
              <p className="theme-soft mt-4 text-sm leading-6">{agent.summary}</p>
            </button>
          </article>
        ))}
      </div>
      {detailDialog}
    </SectionCard>
  );
};
