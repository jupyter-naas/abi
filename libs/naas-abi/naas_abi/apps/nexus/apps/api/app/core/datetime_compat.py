from datetime import datetime, timedelta, timezone

UTC = getattr(datetime, "UTC", timezone(timedelta(0)))
