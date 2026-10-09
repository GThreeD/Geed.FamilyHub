import json
from app.models.schemas import TVConfig

class TVManager:
    def __init__(self, data):
        self.data = data

    def save(self, tv: TVConfig):
        tv.validate()
        self.data.upsert_tv(tv, json.dumps(tv.schedule, separators=(',', ':')))

    def delete(self, tv_id):
        if not self.data.delete_tv(tv_id):
            raise ValueError("TV nicht gefunden")

    def list(self):
        result = []
        for row in self.data.list_tvs():
            result.append(TVConfig(row['tv_id'],row['name'],row['ip'],bool(row['enabled']),
                 json.loads(row['schedule_json']),row['daily_limit_minutes'],
                 row['weekly_limit_minutes'],row['timezone']).validate())
        return result

    def get(self, tv_id):
        return next((tv for tv in self.list() if tv.tv_id == tv_id), None)
