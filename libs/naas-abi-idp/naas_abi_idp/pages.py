"""The login pages and the sign-in mail, with the organization's branding.

Plain HTML with inline styles: no script, no external stylesheet, no font. The
only thing that loads from elsewhere is the logo, and the page's
Content-Security-Policy (``web.py``) allows images from https and this origin only.
Everything dynamic goes through ``escape``.
"""

from __future__ import annotations

from html import escape

from naas_abi_idp.configuration import Branding


def _attr(value: str) -> str:
    return escape(value, quote=True)


def _logo(branding: Branding, max_height: int = 48) -> str:
    if not branding.logo_url:
        return ""
    return (
        f'<img src="{_attr(branding.logo_url)}" alt="{_attr(branding.app_name)}" '
        f'style="max-height:{max_height}px;max-width:200px">'
    )


def _page(branding: Branding, title: str, body: str, *, status_note: str = "") -> str:
    tab = branding.tab_title or branding.app_name
    footer = (
        f'<p class="foot">{escape(branding.footer_text)}</p>'
        if branding.footer_text
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{escape(title)} - {escape(tab)}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:{branding.background_color};color:{branding.text_color};
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
main{{width:100%;max-width:420px;margin:24px;padding:36px 40px;background:{branding.card_color};
border-radius:{int(branding.border_radius)}px;box-shadow:0 1px 3px rgba(0,0,0,.12)}}
.logo{{text-align:center;margin-bottom:20px}}
h1{{font-size:22px;margin:0 0 6px;text-align:center}}
p.sub{{margin:0 0 22px;text-align:center;color:#737373;font-size:14px}}
label{{display:block;font-size:13px;margin:14px 0 6px}}
input[type=email],input[type=password],input[type=text]{{width:100%;padding:11px 12px;
font-size:15px;border:1px solid #c9c9c9;border-radius:{max(int(branding.border_radius) - 4, 2)}px;
background:#fff;color:#1a1a1a}}
input.code{{letter-spacing:8px;font-size:24px;text-align:center}}
button{{width:100%;margin-top:20px;padding:12px;font-size:15px;font-weight:600;color:#fff;
background:{branding.primary_color};border:0;border-radius:{max(int(branding.border_radius) - 4, 2)}px;cursor:pointer}}
.err{{margin:0 0 14px;padding:10px 12px;background:#fef2f2;color:#991b1b;border-radius:6px;font-size:14px}}
.note{{margin:0 0 14px;padding:10px 12px;background:#f0fdf4;color:#166534;border-radius:6px;font-size:14px}}
a{{color:{branding.primary_color}}}
.alt{{margin-top:18px;text-align:center;font-size:13px}}
.foot{{margin:18px 0 0;text-align:center;font-size:12px;color:#737373}}
</style></head>
<body><main>
<div class="logo">{_logo(branding)}</div>
{body}
{footer}
</main></body></html>
"""


def _messages(error: str | None, note: str | None) -> str:
    out = ""
    if error:
        out += f'<p class="err" role="alert">{escape(error)}</p>'
    if note:
        out += f'<p class="note">{escape(note)}</p>'
    return out


def email_page(
    branding: Branding,
    *,
    action: str,
    csrf: str,
    email: str = "",
    error: str | None = None,
    password_action: str | None = None,
) -> str:
    password = ""
    if password_action:
        password = f'<p class="alt"><a href="{_attr(password_action)}">Use a password instead</a></p>'
    body = f"""<h1>Welcome</h1>
<p class="sub">Sign in to continue to {escape(branding.app_name)}</p>
{_messages(error, None)}
<form method="post" action="{_attr(action)}" autocomplete="on">
<input type="hidden" name="csrf" value="{_attr(csrf)}">
<label for="email">Email</label>
<input id="email" name="email" type="email" value="{_attr(email)}" autocomplete="email" required autofocus>
<button type="submit">Email me a code</button>
</form>{password}"""
    return _page(branding, "Sign in", body)


def code_page(
    branding: Branding,
    *,
    action: str,
    again_action: str,
    csrf: str,
    email: str,
    error: str | None = None,
    note: str | None = None,
    code_length: int = 6,
) -> str:
    body = f"""<h1>Check your email</h1>
<p class="sub">If {escape(email)} is registered, we sent a {code_length}-digit code to it.</p>
{_messages(error, note)}
<form method="post" action="{_attr(action)}" autocomplete="off">
<input type="hidden" name="csrf" value="{_attr(csrf)}">
<input type="hidden" name="email" value="{_attr(email)}">
<label for="code">Sign-in code</label>
<input id="code" class="code" name="code" type="text" inputmode="numeric"
pattern="[0-9 ]*" maxlength="{code_length + 2}" autocomplete="one-time-code" required autofocus>
<button type="submit">Sign in</button>
</form>
<p class="alt"><a href="{_attr(again_action)}">Use another address, or send a new code</a></p>"""
    return _page(branding, "Enter your code", body)


def password_page(
    branding: Branding,
    *,
    action: str,
    email_action: str,
    csrf: str,
    email: str = "",
    error: str | None = None,
) -> str:
    body = f"""<h1>Welcome</h1>
<p class="sub">Sign in to continue to {escape(branding.app_name)}</p>
{_messages(error, None)}
<form method="post" action="{_attr(action)}">
<input type="hidden" name="csrf" value="{_attr(csrf)}">
<label for="email">Email</label>
<input id="email" name="email" type="email" value="{_attr(email)}" autocomplete="username" required autofocus>
<label for="password">Password</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<button type="submit">Sign in</button>
</form>
<p class="alt"><a href="{_attr(email_action)}">Email me a code instead</a></p>"""
    return _page(branding, "Sign in", body)


def message_page(branding: Branding, title: str, message: str) -> str:
    body = f'<h1>{escape(title)}</h1>\n<p class="sub">{escape(message)}</p>'
    return _page(branding, title, body)


# -- mail ----------------------------------------------------------------------


def code_subject(branding: Branding) -> str:
    return f"Your {branding.app_name} sign-in code"


def code_text(branding: Branding, code: str, minutes: int) -> str:
    return (
        f"Your {branding.app_name} sign-in code is: {code}\n\n"
        f"Enter this code on the sign-in page to continue.\n\n"
        f"It expires in {minutes} minutes. If you did not ask for it, you can "
        f"ignore this message."
    )


def code_html(branding: Branding, code: str, minutes: int) -> str:
    logo = _logo(branding)
    return (
        f'<!DOCTYPE html><html><body style="margin:0;padding:0;'
        f"background-color:{branding.background_color};"
        f'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background-color:{branding.background_color};padding:48px 16px;">'
        f'<tr><td align="center"><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" style="max-width:440px;background-color:{branding.card_color};'
        f'padding:40px 48px;border-radius:{int(branding.border_radius)}px;">'
        f'<tr><td align="center" style="padding-bottom:24px;">{logo}</td></tr>'
        f'<tr><td align="center" style="padding-bottom:8px;">'
        f'<p style="margin:0;font-size:14px;color:#737373;">Your sign-in code</p>'
        f'<p style="margin:12px 0 0;font-size:28px;letter-spacing:6px;font-weight:700;'
        f'color:{branding.text_color};">{escape(code)}</p></td></tr>'
        f'<tr><td align="center" style="padding-top:20px;">'
        f'<p style="margin:0;font-size:12px;color:#737373;">This code expires in '
        f"{minutes} minutes.</p></td></tr></table>"
        f'<p style="margin:24px 0 0;font-size:12px;color:#737373;">'
        f"{escape(branding.footer_text)}</p></td></tr></table></body></html>"
    )
