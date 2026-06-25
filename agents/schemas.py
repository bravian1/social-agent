#!/usr/bin/env python3
"""
Pydantic v2 output schemas for browser-use agents.

Passed to Agent(output_model_schema=...) so the agent's final result is
validated structured data instead of free-form text we have to parse by hand.
"""

from pydantic import BaseModel, Field


class Tweet(BaseModel):
	"""A single tweet captured from a feed."""

	author: str = Field(default='', description='Handle or display name')
	content: str = Field(default='', description='Full tweet text')
	timestamp: str = Field(default='', description='When it was posted, or relative age')
	engagement: str = Field(default='', description='Likes/retweets/etc. if visible')


class ScrapedTweets(BaseModel):
	"""Result of the X `scrape` mode."""

	tweets: list[Tweet] = Field(default_factory=list, description='Tweets extracted from the feed')


class OriginalTweet(BaseModel):
	"""The root tweet of a thread."""

	author: str = Field(default='', description='Handle or display name')
	content: str = Field(default='', description='Full tweet text')


class Reply(BaseModel):
	"""A single reply within a thread."""

	reply_author: str = Field(default='', description='Handle or display name of the replier')
	reply_content: str = Field(default='', description='Full reply text')
	timestamp: str = Field(default='', description='When the reply was posted, or relative age')


class TweetReplies(BaseModel):
	"""Result of the X `replies` mode."""

	original_tweet: OriginalTweet = Field(default_factory=OriginalTweet)
	replies: list[Reply] = Field(default_factory=list, description='Replies in the thread')


# Map agent mode -> output schema. Modes not listed return free-form text.
X_OUTPUT_SCHEMAS = {
	'scrape': ScrapedTweets,
	'replies': TweetReplies,
}
