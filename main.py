#!/usr/bin/env python3
"""Start the permanent TV monitoring worker and localhost-only HTTP API."""
import json
import logging
import os
import threading
from dataclasses import asdict
from pathlib import Path
from app.data.database_data import DatabaseData
from app.managers.tv_manager import TVManager
from app.managers.schedule_manager import ScheduleManager
from app.managers.settings_manager import SettingsManager
from app.managers.automation_manager import AutomationManager
from app.services.samsung_service import SamsungService
from app.api.handlers import TVApi
from app.api.http_api import HttpApi
from app.managers.auth_manager import AuthManager
from app.models.schemas import RuntimeConfig, TVConfig, ValidationError

BASE = Path(__file__).resolve().parent

class SamsungApplication:
    def __init__(self, directory=BASE):
        self.directory=Path(directory)
        self.data=DatabaseData(self.directory/'private'/'samsung.db')
        self.tvs=TVManager(self.data)
        self.schedules=ScheduleManager(self.data)
        self.settings=SettingsManager(self.data)
        self._import_legacy_config()
        self._engine=None
        self.facade=TVApi(self.tvs,self.schedules,self.data,self.get_observation)
        self.auth=AuthManager(self.data)
        self.http=HttpApi(self.facade,self.settings,self.data,self.auth,self.directory/'frontend'/'dist')
        self.samsung=SamsungService(self.directory/'private'/'tokens')
        self.stop_event=threading.Event()

    def _import_legacy_config(self):
        path=self.directory/'config.json'
        if not path.exists() or self.tvs.list():
            return
        raw=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw,dict) or not isinstance(raw.get('tvs'),list):
            raise ValidationError('Legacy-Konfiguration ungültig')
        runtime=RuntimeConfig(**{k:raw[k] for k in RuntimeConfig.__dataclass_fields__ if k in raw}).validate()
        entries=[]
        for value in raw['tvs']:
            if not isinstance(value,dict):
                raise ValidationError('Ungültiger TV-Eintrag')
            entries.append(TVConfig(**value).validate())
        if len({tv.tv_id for tv in entries})!=len(entries) or len({tv.ip for tv in entries})!=len(entries):
            raise ValidationError('TV-IDs und IPs müssen eindeutig sein')
        if self.data.initial_import(entries,runtime):
            logging.info('Alte config.json einmalig in die DB importiert')
            path.rename(self.directory/'config.json.imported')

    def get_observation(self, tv_id):
        engine=self._engine
        if engine is None:
            return None
        st=engine.state.get(tv_id)
        if st is None or st.last_checked_at is None:
            return None
        return {
            'state':('online' if st.confirmed_online else
                     'offline' if st.offline_count >= engine.settings.confirm_offline_checks
                     else 'unknown'),
            'reachable':st.last_reachable,
            'confirmed_online':st.confirmed_online,
            'last_checked_at':st.last_checked_at,
        }

    def monitor(self):
        while not self.stop_event.is_set():
            settings=self.settings.get()
            config=RuntimeConfig(**{k:settings[k] for k in RuntimeConfig.__dataclass_fields__}).validate()
            # Live changes via API take effect in the next monitoring cycle.
            engine=AutomationManager(self.tvs,self.schedules,self.data,self.samsung,config,armed=bool(settings['armed']))
            # Preserve observations across cycles to prevent repeated power toggles.
            if self._engine is None:
                self._engine=engine
            else:
                self._engine.settings=config
                self._engine.armed=bool(settings['armed'])
            try:
                self._engine.tick()
            except Exception:
                logging.exception('Fehler im Monitor; Überwachung wird fortgesetzt')
            self.stop_event.wait(config.poll_seconds)

    def run(self):
        thread=threading.Thread(target=self.monitor,name='tv-monitor',daemon=True)
        thread.start()
        logging.warning('HTTP-API ausschließlich auf 0.0.0.0:8765; armed standardmäßig false')
        try:
            self.http.serve(host=os.getenv('STC_HOST','0.0.0.0'),port=8765)
        finally:
            self.stop_event.set()
            thread.join(timeout=5)

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    SamsungApplication().run()
