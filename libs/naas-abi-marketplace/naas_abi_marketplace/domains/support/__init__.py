from naas_abi import secret


def requirements():
    github_access_token = secret.get("GITHUB_ACCESS_TOKEN")
    if github_access_token:
        return True
    return False
