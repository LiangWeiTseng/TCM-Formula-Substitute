import unittest
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from formula_altsearch import cli

DATABASE_SAMPLE = {'桂枝湯': {'桂枝': 3, '白芍': 2}}
DATABASE_SAMPLE2 = {'桂枝湯': {'桂枝': 3, '白芍': 2}, '芍藥甘草湯': {'白芍': 2, '炙甘草': 2}}


class TestCmdSearch(unittest.TestCase):
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher, 'load_formula_database', return_value=DATABASE_SAMPLE)
    def test_cmd_search_formula(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            database='custom_db.yaml',
            items=[('桂枝湯', 3)],
            penalty=3,
            num=6,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_called_once_with(
            m_load.return_value, {'桂枝': 9, '白芍': 6},
            excludes={'桂枝湯'}, penalty_factor=3, top_n=6,
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher, 'load_formula_database', return_value=DATABASE_SAMPLE)
    def test_cmd_search_formula_nonexist(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            database='custom_db.yaml',
            items=[('麻黃湯', 3)],
            penalty=3,
            num=6,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_not_called()
        self.assertRegex(m_stdout.getvalue(), r'資料庫尚未收錄此方劑。')

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher, 'load_formula_database', return_value=DATABASE_SAMPLE)
    def test_cmd_search_herbs(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            database='custom_db.yaml',
            items=[('桂枝', 4), ('白芍', 2)],
            penalty=5,
            num=10,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_called_once_with(
            m_load.return_value, {'桂枝': 4, '白芍': 2},
            excludes=None, penalty_factor=5, top_n=10,
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher, 'load_formula_database', return_value=DATABASE_SAMPLE)
    def test_cmd_search_herbs_nonexist(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            database='custom_db.yaml',
            items=[('桂枝', 4), ('生薑', 3), ('炙甘草', 2)],
            penalty=5,
            num=10,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_not_called()
        self.assertRegex(m_stdout.getvalue(), r'資料庫尚未收錄以下藥物：生薑, 炙甘草')

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli.searcher, 'find_best_matches', wraps=cli.searcher.find_best_matches)
    def test_search_herbs(self, m_find, m_stdout):
        cli.search(
            DATABASE_SAMPLE, {'桂枝': 9, '白芍': 6},
            excludes=None, penalty_factor=3, top_n=6,
        )
        m_find.assert_called_once_with(
            DATABASE_SAMPLE, {'桂枝': 9, '白芍': 6},
            excludes=None, penalty_factor=3, top_n=6,
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli.searcher, 'find_best_matches', wraps=cli.searcher.find_best_matches)
    def test_search_formula(self, m_find, m_stdout):
        cli.search(
            DATABASE_SAMPLE2, {'桂枝': 9, '白芍': 6},
            excludes={'桂枝湯'}, penalty_factor=3, top_n=6,
        )
        m_find.assert_called_once_with(
            DATABASE_SAMPLE2, {'桂枝': 9, '白芍': 6},
            excludes={'桂枝湯'}, penalty_factor=3, top_n=6,
        )
