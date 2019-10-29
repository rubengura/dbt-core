from test.integration.base import DBTIntegrationTest,  use_profile
import io
import json
import os
import sys
from dbt.version import __version__ as dbt_version
from dbt.logger import log_manager


class QueryComments(DBTIntegrationTest):
    @property
    def schema(self):
        return 'dbt_query_comments_051'

    @staticmethod
    def dir(value):
        return os.path.normpath(value)

    @property
    def models(self):
        return self.dir('models')

    def setUp(self):
        super().setUp()
        self.initial_stdout = log_manager.stdout
        self.initial_stderr = log_manager.stderr
        self.stringbuf = io.StringIO()
        log_manager.set_output_stream(self.stringbuf)

    def tearDown(self):
        log_manager.set_output_stream(self.initial_stdout, self.initial_stderr)
        super().tearDown()

    def run_get_json(self):
        self.run_dbt(['--debug', '--log-format=json', 'run'])
        logs = []
        for line in self.stringbuf.getvalue().split('\n'):
            try:
                log = json.loads(line)
            except ValueError:
                continue

            if log['extra'].get('run_state') != 'running':
                continue
            logs.append(log)
        self.assertGreater(len(logs), 0)
        return logs

    def query_comment(self, model_name, log):
        prefix = 'On {}: '.format(model_name)

        if log['message'].startswith(prefix):
            msg = log['message'][len(prefix):]
            if msg in {'COMMIT', 'BEGIN', 'ROLLBACK'}:
                return None
            return msg
        return None

    def matches_comment(self, msg) -> bool:
        raise NotImplementedError

    def run_assert_comments(self):
        logs = self.run_get_json()

        seen = False
        for log in logs:
            msg = self.query_comment('model.test.x', log)
            if msg is not None:
                self.matches_comment(msg)
                seen = True

        self.assertTrue(seen, 'Never saw a matching log message! Logs:\n{}'.format('\n'.join(l['message'] for l in logs)))


class TestQueryComments(QueryComments):
    @property
    def project_config(self):
        return {'query-comment': 'dbt\nrules!\n'}

    def matches_comment(self, msg) -> bool:
        self.assertTrue(
            msg.startswith('-- dbt\n-- rules!\n'),
            f'{msg} did not start with query comment'
        )

    @use_profile('postgres')
    def test_postgres_comments(self):
        self.run_assert_comments()

    @use_profile('redshift')
    def test_redshift_comments(self):
        self.run_assert_comments()

    @use_profile('snowflake')
    def test_snowflake_comments(self):
        self.run_assert_comments()

    @use_profile('bigquery')
    def test_bigquery_comments(self):
        self.run_assert_comments()


class TestDefaultQueryComments(QueryComments):
    def matches_comment(self, msg):
        if not msg.startswith('-- '):
            return False
        # our blob is the first line of the query comments, minus the '-- '
        json_str = msg.split('\n')[0][3:]
        data = json.loads(json_str)
        self.assertEqual(data['app'], 'dbt')
        self.assertEqual(data['dbt_version'], dbt_version)
        self.assertEqual(data['node_id'], 'model.test.x')

    @use_profile('postgres')
    def test_postgres_comments(self):
        self.run_assert_comments()

    @use_profile('redshift')
    def test_redshift_comments(self):
        self.run_assert_comments()

    @use_profile('snowflake')
    def test_snowflake_comments(self):
        self.run_assert_comments()

    @use_profile('bigquery')
    def test_bigquery_comments(self):
        self.run_assert_comments()
