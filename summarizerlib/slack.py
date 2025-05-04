import logging
import re

import requests
from slack_bolt import App


class SlackThreadFinder:
    """
    A utility class to interact with Slack and extract specific threads,
    particularly those related to the "art-attention" label.
    """

    def __init__(self, slack_token, user_token):
        """
        Initialize the Slack client and request headers.

        :param slack_token: Bot token used for Slack API access.
        :param user_token: User token for searching messages.
        """
        self.logger = logging.getLogger(__name__)
        self.user_token = user_token
        self.headers = {
            'Authorization': f'Bearer {slack_token}'
        }
        self.app = App(token=slack_token)
        self.user_cache = {}  # Cache to store user_id -> username mappings

    def get_username(self, user_id: str) -> str:
        """
        Resolve a Slack user ID to a real name or username.

        :param user_id: The Slack user ID to resolve.
        :return: A human-readable username.
        """
        if user_id in self.user_cache:
            return self.user_cache[user_id]

        try:
            response = self.app.client.users_info(user=user_id)
            username = response['user']['real_name'] or response['user']['name']
            self.user_cache[user_id] = username
            return username

        except Exception as e:
            self.logger.warning('Failed retrieve user name for ID %s: %s', user_id, e)
            return user_id  # Fallback to user ID if lookup fails

    def gather_messages(self, query: str) -> list:
        """
        Search Slack for messages containing the 'art-attention' label
        and not marked as resolved.

        :param query: query used to select Slack messages
        :return: A list of matching Slack messages sorted by timestamp.
        """
        all_matches = []
        next_cursor = '*'

        while next_cursor:
            # Use Slack search API to find messages with label 'art-attention' and without 'art-attention-resolved'
            slack_response = self.app.client.search_messages(
                token=self.user_token,
                query=query,
                cursor=next_cursor
            )
            messages = slack_response.get('messages', {})
            all_matches.extend(messages.get('matches', []))

            # Handle pagination using response metadata
            response_metadata = slack_response.get('response_metadata', {})
            next_cursor = response_metadata.get('next_cursor', None)

        # Return messages sorted by timestamp
        return sorted(all_matches, key=lambda m: m.get('ts', '0.0'))

    def fetch_thread_conversation(self, channel: str, thread_ts: str) -> list:
        """
        Fetch the full thread of messages from a channel using a thread timestamp.

        :param channel: Slack channel ID where the thread resides.
        :param thread_ts: The thread timestamp (thread_ts) identifying the root message.
        :return: A list of messages in the thread.
        """
        url = 'https://slack.com/api/conversations.replies'
        params = {
            'channel': channel,
            'ts': thread_ts
        }
        response = requests.get(url, headers=self.headers, params=params).json()
        return response.get('messages', [])

    def format_thread_for_summary(self, thread: list) -> str:
        """
        Convert a list of Slack messages into a readable conversation string.

        :param thread: A list of Slack messages (as dicts).
        :return: A formatted string suitable for summarization.
        """
        parts = []
        for msg in thread:
            user_id = msg.get('user', None)
            username = self.get_username(user_id) if user_id else msg.get('username', None)
            text = msg.get('text', '')
            parts.append(f"{username}: {text}")
        return "\n".join(parts)

    def fetch_thread_by_permalink(self, permalink: str) -> list:
        """
        Fetch a Slack thread given its permalink URL.

        :param permalink: A URL to a Slack message.
        :return: A list of messages in the thread, or an empty list if parsing fails.
        """
        match = re.search(r'/archives/([A-Z0-9]+)/p(\d{16})', permalink)
        if not match:
            self.logger.warning("Invalid Slack message URL format.")
            return []

        # Extract and convert permalink timestamp to Slack format (e.g., 1234567890.123456)
        channel = match.group(1)
        ts_raw = match.group(2)
        ts = f"{ts_raw[:10]}.{ts_raw[10:]}"  # Format as Slack expects

        return self.fetch_thread_conversation(channel, ts)
