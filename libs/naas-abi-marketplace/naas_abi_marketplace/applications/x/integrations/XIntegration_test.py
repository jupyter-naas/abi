import pytest
from naas_abi_core import logger
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
    XIntegrationConfiguration,
)

module = ABIModule.get_instance()
bearer_token = module.configuration.bearer_token

# Stable public fixtures used across tests.
NASA_USERNAME = "NASA"
NASA_USER_ID = "11348282"
FIRST_TWEET_ID = "20"  # @jack — "just setting up my twttr"


@pytest.fixture
def x_integration() -> XIntegration:
    configuration = XIntegrationConfiguration(bearer_token=bearer_token)
    return XIntegration(configuration)


def test_get_user_by_id(x_integration: XIntegration):
    user = x_integration.get_user_by_id(NASA_USER_ID)

    assert user.get("data") is not None, f"Expected user data, got {user}"
    logger.info(f"User: {user['data']}")


def test_get_user_by_username(x_integration: XIntegration):
    user = x_integration.get_user_by_username(NASA_USERNAME)

    assert user.get("data") is not None, f"Expected user data, got {user}"
    logger.info(f"User: {user['data']}")


def test_get_users_by_ids(x_integration: XIntegration):
    users = x_integration.get_users_by_ids([NASA_USER_ID])

    assert users.get("data"), f"Expected non-empty users data, got {users}"
    logger.info(f"Total users: {len(users['data'])}")
    logger.info(f"User[0]: {users['data'][0]}")


def test_get_users_by_usernames(x_integration: XIntegration):
    users = x_integration.get_users_by_usernames([NASA_USERNAME])

    assert users.get("data"), f"Expected non-empty users data, got {users}"
    logger.info(f"Total users: {len(users['data'])}")
    logger.info(f"User[0]: {users['data'][0]}")


def test_get_user_tweets(x_integration: XIntegration):
    tweets = x_integration.get_user_tweets(NASA_USER_ID)

    assert len(tweets) > 0, f"Expected more than 0 tweets, got {len(tweets)}"
    logger.info(f"Total tweets: {len(tweets)}")
    logger.info(f"Tweet[0]: {tweets[0]}")


def test_get_user_mentions(x_integration: XIntegration):
    mentions = x_integration.get_user_mentions(NASA_USER_ID)

    assert len(mentions) > 0, f"Expected more than 0 mentions, got {len(mentions)}"
    logger.info(f"Total mentions: {len(mentions)}")
    logger.info(f"Mention[0]: {mentions[0]}")


def test_get_user_liked_tweets(x_integration: XIntegration):
    liked = x_integration.get_user_liked_tweets(NASA_USER_ID)

    # NASA may not have liked tweets at any given moment — only assert the call
    # succeeded and returned a list.
    assert isinstance(liked, list), f"Expected list, got {type(liked)}"
    logger.info(f"Total liked tweets: {len(liked)}")


def test_get_user_followers(x_integration: XIntegration):
    followers = x_integration.get_user_followers(NASA_USER_ID)

    assert len(followers) > 0, f"Expected more than 0 followers, got {len(followers)}"
    logger.info(f"Total followers fetched: {len(followers)}")
    logger.info(f"Follower[0]: {followers[0]}")


def test_get_user_following(x_integration: XIntegration):
    following = x_integration.get_user_following(NASA_USER_ID)

    assert len(following) > 0, f"Expected more than 0 following, got {len(following)}"
    logger.info(f"Total following fetched: {len(following)}")
    logger.info(f"Following[0]: {following[0]}")


def test_get_tweet_by_id(x_integration: XIntegration):
    tweet = x_integration.get_tweet_by_id(FIRST_TWEET_ID)

    assert tweet.get("data") is not None, f"Expected tweet data, got {tweet}"
    logger.info(f"Tweet: {tweet['data']}")


def test_get_tweets_by_ids(x_integration: XIntegration):
    tweets = x_integration.get_tweets_by_ids([FIRST_TWEET_ID])

    assert tweets.get("data"), f"Expected non-empty tweets data, got {tweets}"
    logger.info(f"Total tweets: {len(tweets['data'])}")
    logger.info(f"Tweet[0]: {tweets['data'][0]}")


def test_search_recent_tweets(x_integration: XIntegration):
    tweets = x_integration.search_recent_tweets("python lang:en")

    assert len(tweets) > 0, f"Expected more than 0 tweets, got {len(tweets)}"
    logger.info(f"Total tweets: {len(tweets)}")
    logger.info(f"Tweet[0]: {tweets[0]}")
