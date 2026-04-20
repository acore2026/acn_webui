import { TopologyAgentModel, TopologyLinkModel } from '../types';
import { SectionCard } from '../components/SectionCard';

interface NetworkPageProps {
  agents: TopologyAgentModel[];
  links: TopologyLinkModel[];
}

export const NetworkPage = ({ agents, links }: NetworkPageProps) => {
  const activeLinks = links.filter((link) => link.active);
  const averageLatency = links.length
    ? Math.round(
        links.reduce((total, link) => total + Number.parseInt(link.latency, 10), 0) / links.length
      )
    : 0;

  return (
    <SectionCard
      eyebrow="Network"
      title="Route Quality"
      description="Link-level transport view for the active mesh, focused on latency exposure and stream availability."
    >
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="theme-card-muted p-5">
          <h3 className="theme-title text-lg font-semibold">Inter-Agent Links</h3>
          <div className="mt-4 space-y-3">
            {links.map((link) => (
              <div
                key={link.id}
                className="theme-subtle-card flex flex-wrap items-center justify-between gap-3 px-4 py-3"
              >
                <div>
                  <p className="theme-title text-sm font-medium">
                    {link.source} <span className="theme-muted">to</span> {link.target}
                  </p>
                  <p className="theme-muted mt-1 text-xs uppercase tracking-[0.18em]">
                    {link.active ? 'Animated active stream' : 'Standby path'}
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
                <p className="theme-soft text-sm">Active animated links</p>
              </div>
              <div>
                <p className="theme-title text-3xl font-semibold">{agents.filter((agent) => agent.status === 'offline').length}</p>
                <p className="theme-soft text-sm">Offline nodes requiring recovery</p>
              </div>
              <div>
                <p className="theme-title text-3xl font-semibold">
                  {averageLatency}ms
                </p>
                <p className="theme-soft text-sm">Average path latency</p>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-white/8 bg-gradient-to-br from-cyan-400/12 to-blue-500/12 p-5">
            <h3 className="theme-title text-lg font-semibold">Suggested operator action</h3>
            <p className="theme-copy mt-3 text-sm leading-6">
              Re-route traffic away from <code className="theme-code-chip rounded px-1.5 py-0.5">mission-core {'->'} agent-delta</code>{' '}
              and trigger a health check on the standby corridor before re-admitting Delta into the production ring.
            </p>
          </div>
        </div>
      </div>
    </SectionCard>
  );
};
