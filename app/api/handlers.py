"""Transport-neutral API facade for a future HTTP UI; no HTTP server exposed yet."""
from dataclasses import asdict
from datetime import datetime
from app.models.schemas import TVConfig, ValidationError

class TVApi:
    def __init__(self, tv_manager, schedule_manager, data, observation_provider=None):
        self.tvs=tv_manager
        self.schedules=schedule_manager
        self.data=data
        self.observation_provider=observation_provider

    def get_tvs(self):
        return [asdict(tv) for tv in self.tvs.list()]

    def get_status(self, tv_id):
        tv=self.tvs.get(tv_id)
        if tv is None:
            raise ValidationError('TV nicht gefunden')
        status=self.schedules.evaluate(tv,datetime.now().astimezone())
        observation=(self.observation_provider(tv_id)
                     if self.observation_provider else None)
        status['power_detection']='lan_ports_8002_and_9197_estimate'
        status['usage_is_estimate']=True
        status['online_observation']=observation or {
            'state':'unknown','last_checked_at':None,
            'reachable':None,'confirmed_online':False,
        }
        return status

    def put_tv(self, payload):
        if not isinstance(payload,dict):
            raise ValidationError('JSON object erwartet')
        required=set(TVConfig.__dataclass_fields__)
        if set(payload)!=required:
            raise ValidationError('Felder stimmen nicht mit TVConfig ueberein')
        tv=TVConfig(**payload).validate()
        self.tvs.save(tv)
        return asdict(tv)

    def delete_tv(self, tv_id):
        self.tvs.delete(tv_id)
        return {'ok':True}

    def get_statistics(self,tv_id):
        if self.tvs.get(tv_id) is None:
            raise ValidationError('TV nicht gefunden')
        return self.data.usage_statistics(tv_id)

    def get_lock(self,tv_id):
        if self.tvs.get(tv_id) is None:
            raise ValidationError('TV nicht gefunden')
        return self.schedules.locks.get(tv_id)

    def set_lock(self,tv_id,mode):
        tv=self.tvs.get(tv_id)
        if tv is None:
            raise ValidationError('TV nicht gefunden')
        return self.schedules.locks.set(tv,mode)

    def clear_lock(self,tv_id):
        if self.tvs.get(tv_id) is None:
            raise ValidationError('TV nicht gefunden')
        self.schedules.locks.clear(tv_id)
        return {'ok':True}

    def add_bonus(self,tv_id,minutes,expires_at):
        if self.tvs.get(tv_id) is None:
            raise ValidationError('TV nicht gefunden')
        self.schedules.add_bonus(tv_id,minutes,datetime.fromisoformat(expires_at))
        return self.get_status(tv_id)

    def list_bonus(self, tv_id):
        if self.tvs.get(tv_id) is None:
            raise ValidationError('TV nicht gefunden')
        return self.data.list_bonus_grants(tv_id)

    def revoke_bonus(self, tv_id, grant_id):
        if self.tvs.get(tv_id) is None:
            raise ValidationError('TV nicht gefunden')
        if not self.data.revoke_bonus_grant(tv_id,grant_id):
            raise ValidationError('Bonusgutschrift nicht gefunden oder bereits verbraucht')
        self.data.log_event(tv_id, datetime.now().astimezone().isoformat(), 'bonus_revoked', str(grant_id))
        return {'ok':True}

    def get_events(self,tv_id,limit=100):
        if self.tvs.get(tv_id) is None:
            raise ValidationError('TV nicht gefunden')
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValidationError('Limit 1..200')
        return self.data.events(tv_id,limit)

    def get_exceptions(self,tv_id):
        return self.schedules.list_exceptions(tv_id)

    def create_exception(self,tv_id,payload):
        self.schedules.create_exception(tv_id,payload)
        return self.schedules.list_exceptions(tv_id)

    def delete_exception(self,tv_id,exception_id):
        self.schedules.delete_exception(tv_id,exception_id)
        return {'ok':True}
