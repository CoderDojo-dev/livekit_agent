import { useState } from "react";
import {
  Content,
  Dropdown,
  Header,
  HeaderContainer,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuButton,
  HeaderName,
  SideNav,
  SideNavItems,
  SideNavLink,
  SkipToContent,
  Theme,
} from "@carbon/react";
import {
  Analytics,
  Chat,
  Dashboard,
  ListChecked,
  Network_3,
  PhoneFilled,
  Renew,
  Rule,
  Security,
  UserProfile,
  WarningAlt,
} from "@carbon/icons-react";
import { RefreshProvider, useRefresh } from "./refresh";
import { ActionLedgerPanel } from "./components/ActionLedgerPanel";
import { AuditInspector } from "./components/AuditInspector";
import { BusinessRuleRegistry } from "./components/BusinessRuleRegistry";
import { CallbackQueue } from "./components/CallbackQueue";
import { Customer360View } from "./components/Customer360View";
import { EscalationQueue } from "./components/EscalationQueue";
import { KpiPanel } from "./components/KpiPanel";
import { SessionInspector } from "./components/SessionInspector";
import { SystemMatrix } from "./components/SystemMatrix";
import { TelemetryOverview } from "./components/TelemetryOverview";
const NAV = [
  { id: "overview", label: "Telemetry Overview", icon: Dashboard },
  { id: "kpis", label: "Performance KPIs", icon: Analytics },
  { id: "escalations", label: "Escalation Queue", icon: WarningAlt },
  { id: "callbacks", label: "Callback Queue", icon: PhoneFilled },
  { id: "session", label: "Session Inspector", icon: Chat },
  { id: "customer360", label: "Customer 360", icon: UserProfile },
  { id: "actions", label: "Action Ledger", icon: ListChecked },
  { id: "rules", label: "Policy Rules", icon: Rule },
  { id: "audit", label: "Audit & Integrity", icon: Security },
  { id: "matrix", label: "System Matrix", icon: Network_3 },
] as const;
type TabId = (typeof NAV)[number]["id"];
const REFRESH_ITEMS = [
  { id: 5000, label: "Refresh · 5 s" },
  { id: 15000, label: "Refresh · 15 s" },
  { id: 30000, label: "Refresh · 30 s" },
  { id: 60000, label: "Refresh · 1 min" },
  { id: 0, label: "Refresh · paused" },
];
function Shell() {
  const [tab, setTab] = useState<TabId>("overview");
  const [sessionId, setSessionId] = useState("");
  const { intervalMs, setIntervalMs, sync, lastSync } = useRefresh();
  const inspectSession = (id: string) => {
    setSessionId(id);
    setTab("session");
  };
  return (
    <HeaderContainer
      render={({ isSideNavExpanded, onClickSideNavExpand }) => (
        <>
          <Header aria-label="Telecom supervision console">
            <SkipToContent />
            <HeaderMenuButton
              aria-label={isSideNavExpanded ? "Close navigation" : "Open navigation"}
              onClick={onClickSideNavExpand}
              isActive={isSideNavExpanded}
              isCollapsible
            />
            <HeaderName href="#" prefix="Telecom" onClick={(e) => e.preventDefault()}>
              Supervision Console
            </HeaderName>
            <HeaderGlobalBar>
              <div
                className="live-pulse"
                title={
                  lastSync
                    ? `Last synchronised at ${lastSync.toLocaleTimeString()}`
                    : "Waiting for first synchronisation"
                }
              >
                <span className="live-pulse__dot" />
                LIVE
              </div>
              <div className="refresh-select">
                <Dropdown
                  id="refresh-interval"
                  size="sm"
                  titleText=""
                  hideLabel
                  label="Refresh interval"
                  items={REFRESH_ITEMS}
                  itemToString={(item) => (item ? item.label : "")}
                  selectedItem={REFRESH_ITEMS.find((i) => i.id === intervalMs) ?? REFRESH_ITEMS[1]}
                  onChange={({ selectedItem }) => selectedItem && setIntervalMs(selectedItem.id)}
                />
              </div>
              <HeaderGlobalAction aria-label="Synchronise now" tooltipAlignment="end" onClick={sync}>
                <Renew size={20} />
              </HeaderGlobalAction>
            </HeaderGlobalBar>
            <SideNav
              aria-label="Primary navigation"
              isRail
              expanded={isSideNavExpanded}
              onOverlayClick={onClickSideNavExpand}
            >
              <SideNavItems>
                {NAV.map((item) => (
                  <SideNavLink
                    key={item.id}
                    href="#"
                    renderIcon={item.icon}
                    isActive={tab === item.id}
                    onClick={(e: React.MouseEvent) => {
                      e.preventDefault();
                      setTab(item.id);
                    }}
                  >
                    {item.label}
                  </SideNavLink>
                ))}
              </SideNavItems>
            </SideNav>
          </Header>
          <Content id="main-content" className="app-content">
            <div className="page-panel" key={tab}>
              {tab === "overview" && <TelemetryOverview onInspectSession={inspectSession} />}
              {tab === "kpis" && <KpiPanel />}
              {tab === "escalations" && <EscalationQueue onInspect={inspectSession} />}
              {tab === "callbacks" && <CallbackQueue />}
              {tab === "session" && <SessionInspector initialId={sessionId} />}
              {tab === "customer360" && <Customer360View />}
              {tab === "actions" && <ActionLedgerPanel onInspectSession={inspectSession} />}
              {tab === "rules" && <BusinessRuleRegistry />}
              {tab === "audit" && <AuditInspector />}
              {tab === "matrix" && <SystemMatrix />}
            </div>
          </Content>
        </>
      )}
    />
  );
}
export default function App() {
  return (
    <Theme theme="g100">
      <RefreshProvider>
        <Shell />
      </RefreshProvider>
    </Theme>
  );
}
