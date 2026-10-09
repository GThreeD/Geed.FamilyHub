"""Business logic for runtime settings (stored only in DB)."""
from dataclasses import asdict
from app.models.schemas import RuntimeConfig, ValidationError

class SettingsManager:
    def __init__(self, data):
        self.data = data

    def get(self):
        result=self.data.get_settings()
        result['armed']=bool(result['armed'])
        return result

    def update(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError('JSON-Objekt erwartet')
        allowed = set(RuntimeConfig.__dataclass_fields__) | {'armed'}
        if set(payload) != allowed:
            raise ValidationError('Alle Einstellungsfelder erforderlich')
        config = RuntimeConfig(**{key:payload[key] for key in RuntimeConfig.__dataclass_fields__}).validate()
        if type(payload['armed']) is not bool:
            raise ValidationError('armed muss bool sein')
        settings = {**asdict(config), 'armed': payload['armed']}
        self.data.save_settings(settings)
        return self.get()
