import { useEffect, useState, type ReactNode } from 'react';
import {
  LayoutDashboard,
  CalendarClock,
  Gift,
  Users,
  Settings,
  LogOut,
  Tv,
  RefreshCw,
  BarChart3,
  MonitorCog,
  Download,
} from 'lucide-react';
import type { TV, TVStatus, User } from './api';
import { AuthService } from './services/AuthService';
import { TvService } from './services/TvService';
import { SettingsService } from './services/SettingsService';
import { UserService, type ManagedUser } from './services/UserService';
import Access from './components/Access';
import DashboardView from './views/DashboardView';
import ScheduleView from './views/ScheduleView';
import BonusView from './views/BonusView';
import SettingsView from './views/SettingsView';
import UsersView from './views/UsersView';
import DevicesView from './views/DevicesView';
import StatisticsView from './views/StatisticsView';
import TvActionsModal from './components/TvActionsModal';
import UpdateView from './views/UpdateView';

type View =
  'dashboard' | 'schedule' | 'bonus' | 'users' | 'settings' | 'devices' | 'statistics' | 'updates';

export default function App() {
  const [user, U] = useState<User | null>(null),
    [setup, S] = useState<boolean | null>(null),
    [view, V] = useState<View>('dashboard'),
    [tvs, T] = useState<TV[]>([]),
    [status, ST] = useState<Record<string, TVStatus>>({}),
    [settings, SE] = useState<any>(null),
    [users, US] = useState<ManagedUser[]>([]),
    [selected, SEL] = useState(''),
    [bonus, B] = useState(30),
    [expires, EX] = useState(180),
    [error, E] = useState(''),
    [notice, NO] = useState(''),
    [actionTvId, SET_ACTION_TV] = useState<string | null>(null);
  useEffect(() => {
    AuthService.setupStatus()
      .then((x) => {
        S(x.needs_setup);
        if (!x.needs_setup)
          AuthService.currentUser()
            .then((x) => {
              U(x.user);
            })
            .catch(() => {});
      })
      .catch((e) => E(e.message));
  }, []);
  async function refresh() {
    if (!user) return;
    try {
      const all = await TvService.list();
      T(all);
      SEL((previous) =>
        all.some((tv) => tv.tv_id === previous) ? previous : (all[0]?.tv_id ?? ''),
      );
      if (user.role !== 'viewer') SE(await SettingsService.get());
      if (user.role === 'admin') US(await UserService.list());
      await refreshStatus(all);
    } catch (e) {
      E((e as Error).message);
    }
  }
  async function refreshStatus(devices: TV[]) {
    const results = await Promise.allSettled(
      devices.map(async (tv) => [tv.tv_id, await TvService.status(tv.tv_id)] as const),
    );
    ST((previous) => {
      const next = { ...previous };
      for (const result of results) {
        if (result.status === 'fulfilled') next[result.value[0]] = result.value[1];
      }
      return next;
    });
  }
  useEffect(() => {
    if (!user) return;
    void refresh();
  }, [user?.id]);
  useEffect(() => {
    if (!user || tvs.length === 0) return;
    const timer = setInterval(() => void refreshStatus(tvs).catch(console.error), 15000);
    return () => clearInterval(timer);
  }, [user?.id, tvs]);
  async function act(f: () => Promise<unknown>) {
    E('');
    NO('');
    try {
      await f();
      NO('Gespeichert.');
      await refresh();
    } catch (e) {
      E((e as Error).message);
    }
  }
  async function logout() {
    try {
      await AuthService.logout();
    } catch {}
    U(null);
  }
  if (setup === null)
    return <div className="loading">Verbindung zum Backend wird hergestellt… {error}</div>;
  if (!user)
    return (
      <Access
        setup={setup}
        onDone={(u) => {
          U(u);
          S(false);
        }}
      />
    );
  const canEdit = user.role !== 'viewer';
  const tv = tvs.find((t) => t.tv_id === selected);
  const nav: Array<[View, string, ReactNode]> = [
    ['dashboard', 'Übersicht', <LayoutDashboard />],
    ['schedule', 'Zeitpläne', <CalendarClock />],
    ['bonus', 'Bonuszeit', <Gift />],
    ['statistics', 'Statistik', <BarChart3 />],
    ...(user.role === 'admin'
      ? [['devices', 'Geräte', <MonitorCog />] as [View, string, ReactNode]]
      : []),
    ...(user.role === 'admin'
      ? [['updates', 'Updates', <Download />] as [View, string, ReactNode]]
      : []),
    ...(user.role === 'admin'
      ? [['users', 'Benutzer', <Users />] as [View, string, ReactNode]]
      : []),
    ...(canEdit ? [['settings', 'Einstellungen', <Settings />] as [View, string, ReactNode]] : []),
  ];
  return (
    <div className="app">
      <aside>
        <div className="brand">
          <span className="brand-icon">
            <Tv size={22} />
          </span>
          <div>
            TV Control<small>HOME AUTOMATION</small>
          </div>
        </div>
        <nav>
          {nav.map(([v, n, icon]) => (
            <button
              key={v}
              className={
                (view === v ? 'nav active' : 'nav') + (v === 'devices' ? ' desktop-nav' : '')
              }
              onClick={() => {
                V(v);
                NO('');
                E('');
              }}
            >
              {icon}
              {n}
            </button>
          ))}
        </nav>
        <div className="aside-bottom">
          <div className="identity">
            <span className="avatar">{user.display_name.charAt(0).toUpperCase()}</span>
            <div>
              {user.display_name}
              <small>{user.role}</small>
            </div>
          </div>
          <button className="nav" onClick={logout}>
            <LogOut /> Abmelden
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <span className="eyebrow">SAMSUNG TV CONTROL</span>
            <h1>{nav.find(([v]) => v === view)?.[1]}</h1>
            <p className="muted">Verwalte Fernseher und Nutzungszeiten in deinem Heimnetz.</p>
          </div>
          <button className="secondary" onClick={() => void refresh()}>
            <RefreshCw size={17} /> Aktualisieren
          </button>
        </header>
        {error && <div className="alert">{error}</div>}
        {notice && <div className="notice">{notice}</div>}
        {view === 'dashboard' && (
          <DashboardView tvs={tvs} status={status} onSelectTv={SET_ACTION_TV} />
        )}
        {view === 'schedule' && (
          <ScheduleView
            tv={tv}
            tvs={tvs}
            canEdit={canEdit}
            onSelect={SEL}
            save={(body) => void act(() => TvService.update(body))}
          />
        )}
        {view === 'bonus' && (
          <BonusView
            tvs={tvs}
            status={status}
            selected={selected}
            setSelected={SEL}
            bonus={bonus}
            setBonus={B}
            expires={expires}
            setExpires={EX}
            canEdit={canEdit}
            act={act}
          />
        )}
        {view === 'statistics' && <StatisticsView tvs={tvs} />}
        {view === 'updates' && user.role === 'admin' && <UpdateView />}
        {view === 'devices' && user.role === 'admin' && <DevicesView tvs={tvs} act={act} />}
        {view === 'settings' && canEdit && settings && (
          <SettingsView settings={settings} setSettings={SE} act={act} />
        )}
        {view === 'users' && user.role === 'admin' && (
          <UsersView users={users} user={user} act={act} />
        )}
      </main>
      {actionTvId && (
        <TvActionsModal
          tv={tvs.find((entry) => entry.tv_id === actionTvId)}
          canEdit={canEdit}
          onClose={() => SET_ACTION_TV(null)}
          onBonus={(id) => {
            SEL(id);
            V('bonus');
            SET_ACTION_TV(null);
          }}
          act={act}
        />
      )}
    </div>
  );
}
