from naas_abi import secret


def requirements():
    SENDGRID_API_KEY = secret.get("SENDGRID_API_KEY")
    if SENDGRID_API_KEY:
        return True
    return False
