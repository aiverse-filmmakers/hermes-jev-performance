"""Complete-content eligibility, conservative decisions and recovery in mixed workflows."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from jevperf.compaction import STUB_PREFIX, build_state, candidate_questions, candidates_for
from jevperf.compaction_archive import OutputArchive
from jevperf.compaction_config import CompactionConfig
from tests.test_compaction import Evaluator, compactor, transcript


class RelevanceCompactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = OutputArchive(Path(self.temp.name).resolve() / 'drawer')
        self.config = CompactionConfig(mode='on', allow_external=True)

    def run_compact(self, rows, evaluator=None, config=None):
        return compactor(evaluator).compact(rows, config=config or self.config,
            model='typesafe/jev-1.13', timeout=2.5, archive=self.archive, session_id='synthetic-session')

    def test_complete_assessment_covers_every_character_in_order(self):
        rows = transcript()
        rows[4]['content'] = ''.join(f'{i:06d}: unique record\n' for i in range(6000))
        candidate = candidates_for(rows, self.config)[0]
        questions = candidate_questions(candidate, self.config, build_state(rows, self.config))
        parts = [q['instructions'].split('Content:\n', 1)[1] for q in questions.values()]
        self.assertEqual(''.join(parts), rows[4]['content'])
        self.assertGreater(len(parts), 2)

    def test_uncertain_part_retains_whole_output(self):
        rows = transcript()
        def unsure(**kwargs):
            response = Evaluator()(**kwargs)
            key = next(k for k in response['answers'] if k.endswith('_part_1'))
            response['answers'][key]['noul'] = 0.89
            return response
        out = self.run_compact(rows, unsure)
        self.assertEqual(out.outcome, 'keep_all')
        self.assertIs(out.messages, rows)
        self.assertFalse(self.archive.root.exists())

    def test_redaction_precedes_chunk_boundary(self):
        rows = transcript()
        rows[4]['content'] = 'INFO ' * 390 + 'password="synthetic secret phrase"\n' + 'INFO ' * 1000
        evaluator = Evaluator()
        out = self.run_compact(rows, evaluator, replace(self.config, chunk_chars=2000))
        self.assertEqual(out.outcome, 'applied')
        requests = json.dumps(evaluator.calls)
        self.assertNotIn('synthetic secret phrase', requests)
        assessed = ''.join(q['instructions'].split('Content:\n', 1)[1]
                           for call in evaluator.calls for q in call['questions'].values())
        self.assertNotIn('characters omitted', assessed)
        ref = out.messages[4]['content'][len(STUB_PREFIX):].split(';')[0]
        self.assertIn('synthetic secret phrase', self.archive.recover(ref)['text'])

    def test_oversized_user_constraints_are_not_silently_truncated(self):
        rows = transcript()
        rows[1]['content'] = 'Constraint ' * 10000 + 'KEEP_EXACT_ID=synthetic-final'
        evaluator = Evaluator()
        out = self.run_compact(rows, evaluator)
        self.assertIs(out.messages, rows)
        self.assertEqual(evaluator.calls, [])
        rows = transcript()
        rows[1]['content'] = [{'type': 'image_url', 'image_url': {'url': 'synthetic'}}]
        self.assertIs(self.run_compact(rows, evaluator).messages, rows)
        self.assertEqual(evaluator.calls, [])

    def test_partial_candidate_budget_keeps_whole_large_output_but_compacts_small_one(self):
        rows = transcript(2)
        rows[4]['content'] = 'INFO very large old log\n' * 20000
        rows[6]['content'] = 'INFO completed unique task\n' * 100
        out = self.run_compact(rows, config=replace(self.config, max_batches=1,
            min_reduction_ratio=0.001))
        self.assertEqual(out.outcome, 'applied')
        self.assertEqual(out.messages[4]['content'], rows[4]['content'])
        self.assertTrue(out.messages[6]['content'].startswith(STUB_PREFIX))

    def test_research_files_media_and_publishing_workflows_keep_critical_middle_and_recover_completed_output(self):
        for tool, fact in [('web_extract', 'SOURCE_QUOTE=synthetic citation'),
                           ('read_file', 'CONFIG_SHARDS=17'),
                           ('media_info', 'FRAME_RATE=24000/1001'),
                           ('publish_status', 'PUBLICATION_ID=synthetic-42')]:
            with self.subTest(tool=tool):
                rows = transcript(2)
                rows[1]['content'] = f'Keep {fact}. The old completed diagnostic log is no longer needed.'
                rows[3]['tool_calls'][0]['function']['name'] = tool
                rows[4]['content'] = 'neutral prefix\n' * 1200 + fact + '\n' + 'neutral suffix\n' * 1200
                rows[6]['content'] = 'obsolete completed diagnostic\n' * 1200
                evaluator = Evaluator()
                def relevance(**kwargs):
                    response = evaluator(**kwargs)
                    for name, question in kwargs['questions'].items():
                        if fact in question['instructions']:
                            response['answers'][name]['noul'] = 0.01
                    return response
                out = self.run_compact(rows, relevance)
                self.assertEqual(out.outcome, 'applied')
                self.assertEqual(out.messages[4]['content'], rows[4]['content'])
                self.assertEqual(out.messages[1], rows[1])
                ref = out.messages[6]['content'][len(STUB_PREFIX):].split(';')[0]
                resumed = OutputArchive(self.archive.root)
                recovered, offset = '', 0
                while offset is not None:
                    page = resumed.recover(ref, offset=offset, limit=1700)
                    recovered += page['text']
                    offset = page['next_offset']
                self.assertEqual(recovered, rows[6]['content'])
