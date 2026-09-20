import unittest

from quota_monitor.conversation_detail import ConversationDetail


def message(role, text):
    return {'type': 'response_item', 'timestamp': '2026-09-21T00:00:00Z',
            'payload': {'type': 'message', 'role': role, 'content': text}}


def tokens(total=40, context=100):
    return {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {
        'total_token_usage': {'total_tokens': total},
        'last_token_usage': {'input_tokens': context, 'total_tokens': total,
                             'cached_input_tokens': 20, 'output_tokens': 10,
                             'reasoning_output_tokens': 2},
        'model_context_window': 200}}}


class ConversationDetailTests(unittest.TestCase):
    def test_only_visible_assistant_messages_receive_usage(self):
        trace = ConversationDetail()
        trace.accept(message('user', '<environment_context>private'))
        trace.accept(message('user', '请检查这个任务'))
        trace.accept(message('assistant', '这是回复内容'))
        trace.accept(tokens())
        snapshot = trace.snapshot('one')
        self.assertEqual(len(snapshot['assistantItems']), 1)
        item = snapshot['assistantItems'][0]
        self.assertEqual(item['textPrefix'], '这是回复内容')
        self.assertEqual(item['tokenUsage']['latest_context_tokens'], 100)
        self.assertEqual(item['assistantTotalTurns'], 1)

    def test_pending_assistant_is_not_reused(self):
        trace = ConversationDetail()
        trace.accept(message('assistant', 'first'))
        trace.accept(tokens())
        trace.accept(message('assistant', 'second'))
        trace.accept(message('user', 'new turn'))
        trace.accept(tokens(total=60, context=120))
        items = trace.snapshot('one')['assistantItems']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['tokenUsage']['latest_context_tokens'], 100)

    def test_long_text_is_bounded_and_reset_clears_state(self):
        trace = ConversationDetail()
        trace.accept(message('assistant', 'x' * 500))
        trace.accept(tokens())
        self.assertLessEqual(len(trace.snapshot('one')['assistantItems'][0]['textPrefix']), 120)
        trace.reset()
        self.assertEqual(trace.snapshot('one')['assistantItems'], [])


if __name__ == '__main__':
    unittest.main()
