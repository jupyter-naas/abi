from naas_abi_apps.x.ontologies.processes.XCountRecentTweetsProcess import (
    TweetCountBucket as _TweetCountBucket,
)


class TweetCountBucket(_TweetCountBucket):
    """Action class for TweetCountBucket"""

    def actions(self):
        """Action method - implement your logic here"""
