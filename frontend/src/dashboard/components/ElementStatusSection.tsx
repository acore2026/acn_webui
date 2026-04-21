import { ElementGroupModel } from '../types';
import { LanguageMode } from '../i18n';
import { BotIcon, ControlIcon, NetworkIcon } from './icons';
import { SectionCard } from './SectionCard';

interface ElementStatusSectionProps {
  elements: ElementGroupModel[];
  language: LanguageMode;
}

const groupIconMap = {
  'acn-agent': BotIcon,
  'agent-gw': NetworkIcon,
  idm: ControlIcon
};

const statusToneMap = {
  online: 'theme-badge-emerald',
  degraded: 'theme-badge-amber',
  offline: 'theme-badge-rose'
};

const endpointToneMap = {
  online: 'theme-badge-emerald',
  offline: 'theme-badge-rose'
};

export const ElementStatusSection = ({ elements, language }: ElementStatusSectionProps) => {
  const isZh = language === 'zh';
  return (
    <SectionCard
      eyebrow={isZh ? '基础设施' : 'Infrastructure'}
      title={isZh ? '网络组件状态' : 'Network Element Status'}
      description={isZh ? '实时检测 ACN 工作流核心服务的可达性，包括 ACN Agent、AgentGW、Relay 和 IDM。' : 'Live reachability for the core services behind the ACN workflow: ACN Agent, AgentGW, Relay, and IDM.'}
    >
      <div className="grid gap-4 xl:grid-cols-3">
        {elements.map((element) => {
          const Icon = groupIconMap[element.id as keyof typeof groupIconMap] ?? NetworkIcon;

          return (
            <article key={element.id} className="theme-card-muted p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  <span className="theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
                    <Icon className="h-6 w-6" />
                  </span>
                  <div>
                    <h3 className="theme-title text-lg font-semibold">{element.name}</h3>
                    <p className="theme-soft mt-2 text-sm leading-6">{element.summary}</p>
                  </div>
                </div>

                <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${statusToneMap[element.status]}`}>
                  {isZh ? (element.status === 'online' ? '在线' : element.status === 'offline' ? '离线' : '降级') : element.status}
                </span>
              </div>

              <div className="mt-5 space-y-3">
                {element.components.map((component) => (
                  <div
                    key={component.id}
                    className="theme-subtle-card flex items-start justify-between gap-4 px-4 py-4"
                  >
                    <div>
                      <p className="theme-title text-sm font-semibold">{component.name}</p>
                      <p className="theme-copy mt-2 text-sm leading-6">{component.description}</p>
                    </div>

                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${endpointToneMap[component.status]}`}>
                      {isZh ? (component.status === 'online' ? '在线' : '离线') : component.status}
                    </span>
                  </div>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </SectionCard>
  );
};
