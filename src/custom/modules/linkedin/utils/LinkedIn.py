from datetime import datetime
import calendar

def get_last_day_of_month(year, month):
    # Check if the month is valid
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12")

    # Use calendar.monthrange to get the last day of the month
    last_day = calendar.monthrange(year, month)[1]
    return last_day

def get_date(data: dict, date_type: str) -> str:
    date_iso = None
    date_format_iso = "%Y-%m-%dT%H:%M:%S.%fZ"
    m = "01"
    d = "01"
    H = "00"
    M = "00"
    S = "00"
    if date_type == "end":
        m = "12"
        d = "31"
        H = "23"
        M = "59"
        S = "59"
    if data:
        year = data.get("year")
        month = data.get("month")
        day = data.get("day")
        if year and not month and not day:
            date_iso = datetime.strptime(
                f"{year}-{m}-{d}T{H}:{M}:{S}.000Z", date_format_iso
            )
        elif year and month and not day:
            date_iso = datetime.strptime(
                f"{year}-{month}-{get_last_day_of_month(year, month)}T{H}:{M}:{S}.000Z",
                date_format_iso,
            )
        elif year and month and day:
            date_iso = datetime.strptime(
                f"{year}-{month}-{day}T{H}:{M}:{S}.000Z", date_format_iso
            )
    return date_iso.strftime(date_format_iso)