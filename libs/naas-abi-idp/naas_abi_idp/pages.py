"""The login pages and the sign-in mail, with the organization's branding.

Plain HTML with inline styles: no script, no external stylesheet, no font. The
only things that load from elsewhere are the logo and the tab icon, and the page's
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
        f'style="max-height:{max_height}px;max-width:100%">'
    )


def _is_light(color: str) -> bool:
    hex_ = color.lstrip("#")
    if len(hex_) in (3, 4):
        hex_ = "".join(c * 2 for c in hex_)
    r, g, b = (int(hex_[i : i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6


def _page(branding: Branding, title: str, body: str, *, status_note: str = "") -> str:
    tab = branding.tab_title or branding.app_name
    footer = (
        f'<p class="foot">{escape(branding.footer_text)}</p>'
        if branding.footer_text
        else ""
    )
    logo = _logo(branding)
    icon = (
        f'<link rel="icon" href="{_attr(branding.favicon_url)}">\n'
        if branding.favicon_url
        else ""
    )
    radius = f"{int(branding.border_radius)}px"
    ink = "0,0,0" if _is_light(branding.card_color) else "255,255,255"
    page_ink = "0,0,0" if _is_light(branding.background_color) else "255,255,255"
    hover = (
        f"background:{branding.accent_color}"
        if branding.accent_color
        else "filter:brightness(.9)"
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{escape(title)} - {escape(tab)}</title>
{icon}<style>
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;
justify-content:center;padding:24px 16px;background:{branding.background_color};
color:{branding.text_color};
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased}}
main{{width:100%;max-width:440px;padding:40px 48px 48px;background:{branding.card_color};
border-radius:{radius}}}
.logo{{display:flex;justify-content:center;margin-bottom:24px}}
h1{{font-size:24px;font-weight:700;line-height:1.2;margin:0;text-align:center}}
p.sub{{margin:8px 0 24px;text-align:center;color:rgba({ink},.55);font-size:14px;line-height:1.5}}
label{{display:block;font-size:14px;font-weight:500;margin:16px 0 8px}}
input[type=email],input[type=password],input[type=text]{{display:block;width:100%;height:44px;
padding:8px 16px;font:inherit;font-size:14px;border:0;border-radius:{radius};
background:{branding.input_color};color:{branding.text_color}}}
input:focus{{outline:none;box-shadow:0 0 0 2px {branding.primary_color}33}}
input.code{{letter-spacing:8px;font-size:22px;text-align:center}}
button{{display:flex;align-items:center;justify-content:center;width:100%;height:44px;
margin-top:16px;padding:0 16px;font:inherit;font-size:14px;font-weight:500;color:#fff;
background:{branding.primary_color};border:0;border-radius:{radius};cursor:pointer;
transition:background-color .15s,filter .15s}}
button:hover{{{hover}}}
button:focus-visible{{outline:2px solid {branding.primary_color};outline-offset:2px}}
.err,.note{{margin:0 0 16px;padding:12px;border-radius:{radius};font-size:14px;line-height:1.4}}
.err{{background:rgba(239,68,68,.1);color:#dc2626}}
.note{{background:rgba(34,197,94,.1);color:#15803d}}
a{{color:{branding.primary_color};text-decoration:none}}
a:hover{{text-decoration:underline}}
.alt{{margin:24px 0 0;text-align:center;font-size:13px}}
.foot{{margin:32px 0 0;text-align:center;font-size:12px;color:rgba({page_ink},.45)}}
</style></head>
<body><main>
{f'<div class="logo">{logo}</div>' if logo else ""}
{body}
</main>
{footer}
</body></html>
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
