import { useEffect, useRef, useState, type ReactNode, type TouchEvent } from 'react';
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
  Download,
  MonitorCog,
} from 'lucide-react';
import type { TV, TVStatus, User } from './api';
import { AuthService } from './services/AuthService';
import { TvService } from './services/TvService';
import DashboardPreferences from './components/DashboardPreferences';
import { PreferencesService, DEFAULT_PREFERENCES } from './services/PreferencesService';
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
    [error, E] = useState(''),
    [notice, NO] = useState(''),
    [actionTvId, SET_ACTION_TV] = useState<string | null>(null),
    [accountOpen, setAccountOpen] = useState(false);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const accountRef = useRef<HTMLDivElement>(null);
  const swipeStart = useRef<{
    x: number;
    y: number;
    active: boolean;
    textField: boolean;
    startedAt: number;
  } | null>(null);
  const pagerRef = useRef<HTMLDivElement>(null);
  const [pageHeight, setPageHeight] = useState<number>();

  useEffect(() => {
    const page = pagerRef.current?.querySelector<HTMLElement>('[data-active="true"]');
    if (!page) return;
    const measure = () => setPageHeight(page.getBoundingClientRect().height);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(page);
    return () => observer.disconnect();
  }, [view, user?.id]);
  const tabRefs = useRef<Partial<Record<View, HTMLButtonElement | null>>>({});

  useEffect(() => {
    if (['dashboard', 'schedule', 'bonus', 'statistics'].includes(view)) {
      tabRefs.current[view]?.scrollIntoView({
        block: 'nearest',
        inline: 'center',
        behavior: 'smooth',
      });
    }
  }, [view]);

  useEffect(() => {
    if (!accountOpen) return;
    const closeOutside = (event: PointerEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    const closeEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setAccountOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeEscape);
    };
  }, [accountOpen]);
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
      setPreferences(await PreferencesService.get());
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
    const timer = setInterval(() => {
      if (!document.hidden) void refreshStatus(tvs).catch(console.error);
    }, 3000);
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
  ];
  const activeIndex = nav.findIndex(([tab]) => tab === view);
  const isPagerView = activeIndex >= 0;
  const tabWidth = () => pagerRef.current?.clientWidth || window.innerWidth;
  function swipeTarget(target: EventTarget | null) {
    const element = target instanceof Element ? target : null;
    // Controls with their own gestures (e.g. sliders and the bonus wheel) stay protected.
    if (
      element?.closest(
        'select, button, a, [role="slider"], [data-no-swipe], .modal, .wheel, [contenteditable="true"]',
      )
    )
      return { blocked: true, textField: false };
    const field = element?.closest('input, textarea');
    if (field instanceof HTMLInputElement) {
      const textTypes = ['text', 'search', 'email', 'url', 'tel', 'number', 'password'];
      return { blocked: !textTypes.includes(field.type), textField: true };
    }
    return { blocked: false, textField: field instanceof HTMLTextAreaElement };
  }
  function onTouchStart(event: TouchEvent<HTMLElement>) {
    if (event.touches.length !== 1 || actionTvId || accountOpen || !isPagerView) return;
    const target = swipeTarget(event.target);
    if (target.blocked) return;
    swipeStart.current = {
      x: event.touches[0].clientX,
      y: event.touches[0].clientY,
      active: false,
      textField: target.textField,
      startedAt: Date.now(),
    };
  }
  function onTouchMove(event: TouchEvent<HTMLElement>) {
    const start = swipeStart.current;
    const track = pagerRef.current;
    if (!start || !track || event.touches.length !== 1) return;
    const dx = event.touches[0].clientX - start.x;
    const dy = event.touches[0].clientY - start.y;
    if (!start.active && Math.abs(dy) > Math.abs(dx)) {
      swipeStart.current = null;
      return;
    }
    // A short horizontal drag pages even over text inputs; long presses still select text.
    if (start.textField && !start.active && Date.now() - start.startedAt > 450) {
      swipeStart.current = null;
      return;
    }
    const threshold = start.textField ? 28 : 12;
    if (Math.abs(dx) > threshold && Math.abs(dx) > Math.abs(dy) * 1.25) start.active = true;
    if (!start.active) return;
    const boundary = (dx > 0 && activeIndex === 0) || (dx < 0 && activeIndex === nav.length - 1);
    const offset = boundary ? dx * 0.2 : dx;
    track.style.transition = 'none';
    track.style.transform = `translate3d(${-(activeIndex * tabWidth()) + offset}px, 0, 0)`;
  }
  function onTouchEnd(event: TouchEvent<HTMLElement>) {
    const start = swipeStart.current;
    swipeStart.current = null;
    if (!start || !start.active || !pagerRef.current || event.changedTouches.length !== 1) return;
    const dx = event.changedTouches[0].clientX - start.x;
    const next = activeIndex + (dx < 0 ? 1 : -1);
    const shouldChange =
      Math.abs(dx) > Math.min(90, tabWidth() * 0.22) && next >= 0 && next < nav.length;
    const track = pagerRef.current;
    track.style.transition = 'transform 240ms cubic-bezier(0.2, 0.75, 0.25, 1)';
    track.style.transform = `translate3d(-${(shouldChange ? next : activeIndex) * tabWidth()}px, 0, 0)`;
    if (shouldChange) {
      V(nav[next][0]);
      E('');
      NO('');
    }
  }
  function onTouchCancel() {
    swipeStart.current = null;
    if (pagerRef.current && isPagerView) {
      pagerRef.current.style.transition = 'transform 240ms ease-out';
      pagerRef.current.style.transform = `translate3d(-${activeIndex * tabWidth()}px, 0, 0)`;
    }
  }
  function switchView(next: View) {
    swipeStart.current = null;
    V(next);
    E('');
    NO('');
    setAccountOpen(false);
  }
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
        <div className="account-bar">
          <div className="account-menu-wrapper" ref={accountRef}>
            <button
              type="button"
              className="account-trigger"
              aria-expanded={accountOpen}
              aria-label="Benutzermenü"
              onClick={() => setAccountOpen((value) => !value)}
            >
              <span className="avatar">{user.display_name.charAt(0).toUpperCase()}</span>
              <span className="account-identity">
                <strong>{user.display_name}</strong>
                <small>{user.role}</small>
              </span>
            </button>
            {accountOpen && (
              <div className="account-menu">
                <div className="account-menu-user">
                  <strong>{user.display_name}</strong>
                  <small>{user.role}</small>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setAccountOpen(false);
                    void refresh();
                  }}
                >
                  <RefreshCw size={17} /> Aktualisieren
                </button>
                <button
                  type="button"
                  onClick={() => {
                    switchView('settings');
                    setAccountOpen(false);
                  }}
                >
                  <Settings size={17} /> Einstellungen
                </button>
                {user.role === 'admin' && (
                  <button
                    type="button"
                    className="account-submenu"
                    onClick={() => {
                      switchView('devices');
                    }}
                  >
                    <MonitorCog size={17} /> Geräte
                  </button>
                )}
                {user.role === 'admin' && (
                  <button
                    type="button"
                    className="account-submenu"
                    onClick={() => {
                      switchView('users');
                      setAccountOpen(false);
                    }}
                  >
                    <Users size={17} /> Benutzer
                  </button>
                )}
                {user.role === 'admin' && (
                  <button
                    type="button"
                    onClick={() => {
                      switchView('updates');
                    }}
                  >
                    <Download size={17} /> Updates
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setAccountOpen(false);
                    void logout();
                  }}
                >
                  <LogOut size={17} /> Abmelden
                </button>
              </div>
            )}
          </div>
        </div>
        <nav>
          {nav.map(([v, n, icon]) => (
            <button
              key={v}
              ref={(element) => {
                tabRefs.current[v] = element;
              }}
              className={view === v ? 'nav active' : 'nav'}
              onClick={() => switchView(v)}
            >
              {icon}
              {n}
            </button>
          ))}
        </nav>
      </aside>
      <main>
        {error && <div className="alert">{error}</div>}
        {notice && <div className="notice">{notice}</div>}
        {isPagerView && (
          <div
            className="pager-viewport"
            style={{
              width: '100%',
              height: pageHeight,
              overflow: 'hidden',
              minWidth: 0,
              touchAction: 'pan-y',
            }}
            onTouchStart={onTouchStart}
            onTouchMove={onTouchMove}
            onTouchEnd={onTouchEnd}
            onTouchCancel={onTouchCancel}
          >
            <div
              ref={pagerRef}
              className="pager-track"
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                width: '100%',
                transition: 'transform 240ms cubic-bezier(0.2, 0.75, 0.25, 1)',
                transform: `translate3d(-${activeIndex * 100}%, 0, 0)`,
              }}
            >
              <section
                className="pager-page"
                data-active={view === 'dashboard'}
                aria-hidden={view !== 'dashboard'}
                inert={view !== 'dashboard'}
              >
                <DashboardView
                  tvs={tvs}
                  status={status}
                  preferences={preferences}
                  onSelectTv={SET_ACTION_TV}
                />
              </section>
              <section
                className="pager-page"
                data-active={view === 'schedule'}
                aria-hidden={view !== 'schedule'}
                inert={view !== 'schedule'}
              >
                <ScheduleView
                  tv={tv}
                  tvs={tvs}
                  canEdit={canEdit}
                  onSelect={SEL}
                  save={(body) => void act(() => TvService.update(body))}
                />
              </section>
              <section
                className="pager-page"
                data-active={view === 'bonus'}
                aria-hidden={view !== 'bonus'}
                inert={view !== 'bonus'}
              >
                <BonusView
                  tvs={tvs}
                  status={status}
                  selected={selected}
                  setSelected={SEL}
                  bonus={bonus}
                  setBonus={B}
                  canEdit={canEdit}
                  act={act}
                />
              </section>
              <section
                className="pager-page"
                data-active={view === 'statistics'}
                aria-hidden={view !== 'statistics'}
                inert={view !== 'statistics'}
              >
                <StatisticsView tvs={tvs} />
              </section>
            </div>
          </div>
        )}
        {view === 'updates' && user.role === 'admin' && <UpdateView />}
        {view === 'settings' && (
          <div className="settings-layout">
            <DashboardPreferences preferences={preferences} onSaved={setPreferences} act={act} />
            {canEdit && settings && <SettingsView settings={settings} setSettings={SE} act={act} />}
          </div>
        )}
        {view === 'devices' && user.role === 'admin' && <DevicesView tvs={tvs} act={act} />}
        {view === 'users' && user.role === 'admin' && (
          <UsersView users={users} user={user} act={act} />
        )}
      </main>
      {actionTvId && (
        <TvActionsModal
          tv={tvs.find((entry) => entry.tv_id === actionTvId)}
          canEdit={canEdit}
          onClose={() => SET_ACTION_TV(null)}
          status={status[actionTvId]}
          act={act}
        />
      )}
    </div>
  );
}
