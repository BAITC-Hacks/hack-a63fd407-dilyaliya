import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from email.message import Message

from aml_assistant.agent import investigate
from aml_assistant.runtime import ModelUnavailable
from aml_assistant.service import AssistantService
from aml_assistant.tools import CATALOG, GraphTools, ToolError, action_schema
from scripts.setup_llm import unpack, sha256, check
import serve


def fixture():
    nodes = []
    for gid in ('1', '2', '3', '4'):
        nodes.append(dict(gid=gid, role='peripheral', role_score=.4, priority_score=.1,
                          evidence='Гипотеза peripheral', rule_text='Нет признаков', sum_in=10000., sum_out=0.,
                          fan_in=2, fan_out=0, cluster_id=0, fifo_strict_share=0.,
                          fifo_same_day_possible_share=0., is_seed=gid == '1', is_depth4_leaf=gid == '4'))
    return {'nodes': nodes, 'edges': [dict(src=a, dst=b, sum_kzt=amount, n_tx=1)
                                     for a, b, amount in [('1', '3', 5000), ('2', '3', 7000), ('1', '4', 6000)]],
            'clusters': [], 'cases': {g: {'paths': [], 'requests': [{'reason': 'Неполные данные.', 'request': 'Запросить выписку.'}]}
                                     for g in ('1', '2', '3', '4')},
            'analytics': {'patterns': {'cycles': [], 'repeated_routes': []}},
            'fingerprint': 'raw-hash', 'analysis_sha256': 'analysis-hash', 'rule_version': 'test'}


class ScriptedModel:
    """Only for control-flow tests; never represented as a live LLM benchmark."""
    def __init__(self, actions):
        # A scripted plan precedes scripted actions; this does not test language understanding.
        tasks = list(dict.fromkeys(a['action'] for a in actions if isinstance(a, dict) and a.get('action') in CATALOG))
        if tasks:
            actions = [{'tasks': tasks, 'clarify_reason': 'none'}, *actions]
        self.actions = iter(actions)
        self.messages = []
        self.info = {'model': 'unit-test-double', 'engine_version': 'test'}

    def complete(self, messages, schema, timeout):
        self.messages.append(list(messages))
        action = next(self.actions)
        if isinstance(action, Exception):
            raise action
        return action, {'total_tokens': 5}

    def status(self):
        return {'available': True, 'installed': True}


class AssistantTests(unittest.TestCase):
    def test_broken_optional_installation_does_not_break_main_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'.local_ai';directory.mkdir()
            for raw in ('{broken', '{}', '[]'):
                (directory/'installed.json').write_text(raw)
                self.assertFalse(check(tmp)['installed'])

    def test_finish_cannot_drop_a_requested_check_or_its_facts(self):
        model=ScriptedModel([{'action':'node_details','gids':['1','2']},
                             {'action':'finish','refs':['E1','E2']},
                             {'action':'missing_data','gids':['1','2']},
                             {'action':'finish','refs':['E1']},
                             {'action':'finish','refs':['E1','E2','E3','E4']}])
        result=investigate(fixture(),model,'Сравни 1 и 2 и запроси данные')
        self.assertEqual(result['status'],'answered')
        self.assertEqual(len(result['findings']),4)
        self.assertEqual(sum(s['status']=='rejected' for s in result['trace']),2)

    def test_schema_constrains_long_ids_and_argument_lengths(self):
        gid = '100000000000000017'
        variants = {v['properties']['action']['const']: v for v in action_schema(['E1'], [gid])['oneOf']}
        self.assertEqual(variants['node_details']['properties']['gids']['items']['enum'], [gid])
        self.assertEqual(variants['missing_data']['properties']['gids']['maxItems'], 3)
        self.assertEqual(variants['finish']['properties']['refs']['items']['enum'], ['E1'])
        empty = {v['properties']['action']['const'] for v in action_schema([], [])['oneOf']}
        self.assertNotIn('node_details', empty)
        self.assertIn('top_nodes', empty)

    def test_duplicate_senders_are_not_a_two_sender_query(self):
        with self.assertRaises(ToolError):
            GraphTools(fixture()).call({'action': 'shared_recipients', 'gids': ['1', '1'], 'limit': 3})

    def test_agent_rejects_unobserved_but_existing_node(self):
        model = ScriptedModel([{'action': 'node_details', 'gids': ['4']}])
        result = investigate(fixture(), model, 'Объясни узел 1', max_steps=2)
        self.assertEqual(result['trace'][1]['status'], 'rejected')
        self.assertEqual(result['findings'], [])

    def test_shared_recipients_requires_every_sender_and_exact_sum(self):
        tools = GraphTools(fixture())
        facts = tools.call({'action': 'shared_recipients', 'gids': ['1', '2'], 'limit': 5})
        self.assertEqual(facts[0]['values']['total'], 1)
        self.assertEqual(facts[1]['values']['recipient'], '3')
        self.assertEqual(facts[1]['values']['sum_kzt'], 12000)

    def test_unknown_and_numeric_ids_are_rejected(self):
        for ids in (['999'], [1], '1'):
            with self.subTest(ids=ids), self.assertRaises(ToolError):
                GraphTools(fixture()).call({'action': 'node_details', 'gids': ids})

    def test_tool_allowlist_and_argument_bounds(self):
        for action in ({'action': 'shell', 'command': 'anything'},
                       {'action': 'top_nodes', 'limit': 500, 'role': 'all'},
                       {'action': 'neighbors', 'gid': '1', 'direction': 'bad', 'limit': 3},
                       {'action': 'node_details', 'gids': ['1'], 'url': 'https://example.com'}):
            with self.subTest(action=action), self.assertRaises(ToolError):
                GraphTools(fixture()).call(action)

    def test_agent_observes_results_and_calls_second_tool(self):
        model = ScriptedModel([{'action': 'shared_recipients', 'gids': ['1', '2'], 'limit': 3},
                               {'action': 'node_details', 'gids': ['3']},
                               {'action': 'finish', 'refs': ['E1', 'E2', 'E3']}])
        result = investigate(fixture(), model, 'Найди общих получателей этих отправителей и объясни их роли: 1, 2')
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(result['model_calls'], 4)
        self.assertEqual([f['ref'] for f in result['findings']], ['E1', 'E2', 'E3'])
        self.assertIn('12000', model.messages[2][-2]['content'].replace(',', ''))
        self.assertEqual(result['analysis_sha256'], 'analysis-hash')

    def test_hallucinated_reference_never_becomes_a_finding(self):
        model = ScriptedModel([{'action': 'node_details', 'gids': ['1']},
                               {'action': 'finish', 'refs': ['E999']}, {'action': 'finish', 'refs': ['E1']}])
        result = investigate(fixture(), model, 'Объясни узел 1')
        self.assertEqual(result['trace'][2]['status'], 'rejected')
        self.assertEqual(result['findings'][0]['ref'], 'E1')

    def test_repeated_queries_do_not_create_fake_new_evidence(self):
        action = {'action': 'node_details', 'gids': ['1']}
        model = ScriptedModel([action, action, action])
        result = investigate(fixture(), model, 'Проверь 1', max_steps=4)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['evidence']), 1)
        self.assertEqual(result['trace'][-1]['status'], 'rejected')

    def test_model_timeout_is_not_a_successful_answer(self):
        result = investigate(fixture(), ScriptedModel([ModelUnavailable('timeout')]), 'Проверь граф')
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['findings'], [])

    def test_no_model_call_for_unknown_long_gid(self):
        result = investigate(fixture(), ScriptedModel([]), 'Проверь 100000000000000009')
        self.assertEqual(result['status'], 'clarification')
        self.assertEqual(result['model_calls'], 0)

    def test_service_rejects_old_analysis_and_busy_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);(root/'output').mkdir()
            (root/'output/assistant_data.json').write_text(json.dumps(fixture()))
            service = AssistantService(root, ScriptedModel([]))
            body = {'question': 'Проверь', 'dataset_sha256': 'raw-hash', 'analysis_sha256': 'old'}
            self.assertEqual(service.ask(body)[0], 409)
            service.busy.acquire()
            try:
                self.assertEqual(service.ask(body)[0], 429)
            finally:
                service.busy.release()

    def test_http_rejects_cross_origin_and_non_json(self):
        for origin, mime in [('https://unrelated.example', 'application/json'), ('http://127.0.0.1:8765', 'text/plain')]:
            handler = serve.Handler.__new__(serve.Handler)
            handler.path='/api/assistant/ask';handler.headers=Message()
            for key, value in {'Host':'127.0.0.1:8765', 'Origin':origin, 'Content-Type':mime, 'X-AML-Request':'1'}.items():
                handler.headers[key]=value
            captured=[];handler.send_json=lambda status, value:captured.append(status)
            handler.do_POST()
            self.assertEqual(captured,[403])

    def test_archive_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'unsafe.tar.gz'
            with tarfile.open(archive,'w:gz') as out:
                info=tarfile.TarInfo('../escape');info.size=1;out.addfile(info,io.BytesIO(b'x'))
            with self.assertRaises(RuntimeError):unpack(archive,root/'target')
            self.assertFalse((root/'escape').exists())

    def test_hash_detects_changed_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'runtime';path.write_bytes(b'a');before=sha256(path);path.write_bytes(b'b')
            self.assertNotEqual(before,sha256(path))
