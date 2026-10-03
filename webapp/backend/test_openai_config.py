import json
import os
import unittest
from unittest.mock import MagicMock, patch

import ia_parser
import previsao


class OpenAIConfigTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'PREVISAO_IA_PROVEDOR': 'openai',
            'PREVISAO_IA_REASONING_EFFORT': 'high',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.failed = patch.object(previsao, '_PROVEDOR_FALHOU', set())
        self.failed.start()
        self.addCleanup(self.failed.stop)

    def response(self, content='{"ok": true}', finish_reason='stop'):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'choices': [{'message': {'content': content}, 'finish_reason': finish_reason}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 200},
        }).encode()
        return response

    def test_sol_sends_high_without_temperature_and_preserves_output_budget(self):
        with patch.object(previsao, 'OPENAI_MODEL', 'gpt-6.1-sol'), \
             patch.object(previsao, '_openai_key', return_value='test-key'), \
             patch('urllib.request.urlopen', return_value=self.response()) as call:
            result = previsao._openai_chat('system', 'input', 8000, temperature=0.2)
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(body['model'], 'gpt-6.1-sol')
        self.assertEqual(body['reasoning_effort'], 'high')
        self.assertGreater(body['max_completion_tokens'], 8000)
        self.assertNotIn('temperature', body)
        self.assertEqual(result, '{"ok": true}')

    def test_sol_defaults_to_high_and_honors_override(self):
        with patch.object(previsao, 'OPENAI_MODEL', 'gpt-6.1-sol'):
            os.environ.pop('PREVISAO_IA_REASONING_EFFORT')
            self.assertEqual(previsao._openai_reasoning_effort(), 'high')
            os.environ['PREVISAO_IA_REASONING_EFFORT'] = 'medium'
            self.assertEqual(previsao._openai_reasoning_effort(), 'medium')
            os.environ['PREVISAO_IA_REASONING_EFFORT'] = 'invalid'
            with self.assertRaises(ValueError):
                previsao._openai_reasoning_effort()

    def test_legacy_model_keeps_temperature_without_reasoning(self):
        with patch.object(previsao, 'OPENAI_MODEL', 'gpt-4.1'), \
             patch.object(previsao, '_openai_key', return_value='test-key'), \
             patch('urllib.request.urlopen', return_value=self.response()) as call:
            previsao._openai_chat('system', 'input', 2000, temperature=0.2)
        body = json.loads(call.call_args.args[0].data)
        self.assertNotIn('reasoning_effort', body)
        self.assertEqual(body['max_completion_tokens'], 2000)
        self.assertEqual(body['temperature'], 0.2)

    def test_incomplete_or_empty_response_is_not_used(self):
        for content, finish in [('partial', 'length'), ('', 'stop'), (None, 'stop')]:
            with self.subTest(content=content, finish=finish), \
                 patch.object(previsao, '_openai_key', return_value='test-key'), \
                 patch('urllib.request.urlopen', return_value=self.response(content, finish)):
                with self.assertRaises(RuntimeError):
                    previsao._openai_chat('system', 'input', 2000)

    def test_forced_openai_never_calls_anthropic_even_after_failure(self):
        with patch.object(previsao, '_openai_key', return_value='test-key'), \
             patch.object(previsao, '_claude_key', return_value='other-key'), \
             patch.object(previsao, '_openai_chat', side_effect=RuntimeError('unavailable')) as openai, \
             patch.object(previsao, '_anthropic_chat') as anthropic:
            self.assertIsNone(previsao._claude_chat('system', 'input'))
            self.assertIsNone(previsao._claude_chat('system', 'input'))
            self.assertEqual(previsao._ia_modelo(), previsao.OPENAI_MODEL)
        openai.assert_called_once()
        anthropic.assert_not_called()

    def test_auto_selection_still_allows_fallback(self):
        os.environ.pop('PREVISAO_IA_PROVEDOR')
        with patch.object(previsao, '_openai_key', return_value='test-key'), \
             patch.object(previsao, '_claude_key', return_value='other-key'), \
             patch.object(previsao, '_anthropic_chat', side_effect=RuntimeError('unavailable')), \
             patch.object(previsao, '_openai_chat', return_value='ok') as openai:
            self.assertEqual(previsao._claude_chat('system', 'input'), 'ok')
        openai.assert_called_once()

    def test_parser_does_not_bypass_provider_on_error(self):
        with patch.object(previsao, '_ia_disponivel', return_value=True), \
             patch.object(previsao, '_claude_chat', side_effect=RuntimeError('unavailable')), \
             patch('urllib.request.urlopen') as network:
            self.assertIsNone(ia_parser._call_ia('system', 'input'))
        network.assert_not_called()

    def test_parser_uses_same_model_and_effort_as_classifier(self):
        with patch.object(previsao, 'OPENAI_MODEL', 'gpt-6.1-sol'), \
             patch.object(previsao, '_openai_key', return_value='test-key'), \
             patch('urllib.request.urlopen', return_value=self.response()) as call:
            self.assertEqual(ia_parser._call_ia('system', 'input'), '{"ok": true}')
        body = json.loads(call.call_args.args[0].data)
        self.assertEqual(body['model'], 'gpt-6.1-sol')
        self.assertEqual(body['reasoning_effort'], 'high')


if __name__ == '__main__':
    unittest.main()
