import asyncio
import logging
import os
from string import Template
from typing import Optional, List, Dict

import aiohttp

from summarizerlib.slack import SlackThreadFinder


class SummaryGenerator:
    """
    A class to generate summaries of Slack threads using a locally hosted LLaMA model.
    """

    def __init__(self, llama_server_endpoint):
        """
        Initialize the SummaryGenerator with connection details for the LLaMA server.
        :param llama_server_endpoint: The URL of the LLaMA inference server.
        """

        self.logger = logging.getLogger(__name__)
        self.prompt_template = Template(
            "[INST] Summarize this conversation taken from Slack:\n\n"
            "$text [/INST]"
        )
        self.endpoint = llama_server_endpoint
        self.headers = {'Content-Type': 'application/json'}

        # Initialize the Slack thread finder utility with environment tokens
        self.slack_finder = SlackThreadFinder(
            slack_token=os.environ['SLACK_TOKEN'],
            user_token=os.environ['USER_TOKEN'],
        )

    async def summarize(self, text: str) -> Optional[str]:
        """
        Generate a summary of the given text using the LLaMA model.

        :param text: Raw text to be summarized.
        :return: A string containing the summary, or None if the request fails.
        """

        self.logger.info('Summarizing text: %s', text)
        prompt = self.prompt_template.substitute(text=text.strip())
        payload = {
            "prompt": prompt,
            "n_predict": 512
        }

        async with aiohttp.ClientSession() as session:
            try:
                self.logger.info('Querying model at %s', self.endpoint)
                async with session.post(self.endpoint, headers=self.headers, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data['content']
            except Exception as e:
                self.logger.warning('Encountered error while querying the model: %s', e)
                return None

    async def summarize_art_attention_threads(self) -> List[Dict[str, str]]:
        """
        Summarize all Slack threads that reference "@release-artists".

        :return: A list of dictionaries with 'permalink' and corresponding 'summary'.
        """

        self.logger.info('Summarizing :art-attention: threads...')

        # Find messages mentioning @release-artists
        messages = self.slack_finder.gather_messages('has::art-attention: -has::art-attention-resolved:')
        self.logger.info('Found %s messages to summarize', len(messages))
        permalinks = []
        threads = []

        for msg in messages:
            # Determine thread timestamp (thread_ts) or fallback to message timestamp
            thread_ts = msg['thread_ts'] if 'thread_ts' in msg else msg['ts']
            channel = msg['channel']['id']

            # Fetch full conversation of the thread
            conversation = self.slack_finder.fetch_thread_conversation(channel, thread_ts)
            formatted = self.slack_finder.format_thread_for_summary(conversation)

            threads.append(formatted)
            permalinks.append(msg['permalink'])

            # Throttle requests to respect Slack rate limits
            await asyncio.sleep(1)

        # Generate summaries concurrently
        results = await asyncio.gather(*[self.summarize(thread) for thread in threads])
        return [{'permalink': k, 'summary': v} for k, v in zip(permalinks, results)]

    async def summarize_thread_by_permalink(self, permalink: str) -> Dict[str, str]:
        """
        Summarize a single Slack thread given its permalink.

        :param permalink: The Slack permalink of the thread.
        :return: A dictionary with 'permalink' and corresponding 'summary'.
        """

        self.logger.info('Summarizing thread by permalink: %s', permalink)

        conversation = self.slack_finder.fetch_thread_by_permalink(permalink)
        thread = self.slack_finder.format_thread_for_summary(conversation)
        summary = await self.summarize(thread)

        return {
            'permalink': permalink,
            'summary': summary
        }
