from src import secret
from abi import logger

def requirements():
    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    linkedin_profile_url = secret.get('LINKEDIN_PROFILE_URL')
    if li_at is not None and JSESSIONID is not None and linkedin_profile_url is not None:
        logger.debug("LinkedIn cookies li_at:")
        logger.debug(li_at)
        logger.debug("LinkedIn cookies JSESSIONID:")
        logger.debug(JSESSIONID)
        logger.debug("LinkedIn profile URL:")
        logger.debug(linkedin_profile_url)
        return True
    return False