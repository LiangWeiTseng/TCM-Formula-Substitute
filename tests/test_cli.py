import unittest
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from formula_altsearch import cli

DATABASE_SAMPLE = cli.searcher.FormulaDatabase({'桂枝湯': {'桂枝': 3, '白芍': 2}, '桂枝': {'桂枝': 4}})
DATABASE_SAMPLE2 = cli.searcher.FormulaDatabase({'桂枝湯': {'桂枝': 3, '白芍': 2}, '芍藥甘草湯': {'白芍': 2, '炙甘草': 2}})


class TestCmdSearch(unittest.TestCase):
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher.FormulaDatabase, 'from_file', return_value=DATABASE_SAMPLE)
    def test_cmd_search_formula(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            verbosity=50,
            database='custom_db.yaml',
            items=[('桂枝湯', 3)],
            raw=False,
            algorithm='exhaustive',
            max_cformulas=2,
            max_sformulas=3,
            min_cformula_dose=1.0,
            min_sformula_dose=0.3,
            max_cformula_dose=50.0,
            max_sformula_dose=50.0,
            penalty=3,
            num=6,
            excludes=[],
            beam_width_factor=0.5,
            beam_multiplier=2.0,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_called_once_with(
            m_load.return_value, {'桂枝': 9, '白芍': 6}, [('桂枝湯', 3)],
            algorithm='exhaustive', excludes={'桂枝湯'},
            penalty_factor=3, top_n=6,
            max_cformulas=2, max_sformulas=3,
            min_cformula_dose=1.0, min_sformula_dose=0.3,
            max_cformula_dose=50.0, max_sformula_dose=50.0,
            beam_width_factor=0.5, beam_multiplier=2.0,
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher.FormulaDatabase, 'from_file', return_value=DATABASE_SAMPLE)
    def test_cmd_search_formula_nonexist(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            verbosity=50,
            database='custom_db.yaml',
            items=[('麻黃湯', 3)],
            raw=False,
            algorithm='exhaustive',
            max_cformulas=2,
            max_sformulas=3,
            min_cformula_dose=1.0,
            min_sformula_dose=0.3,
            max_cformula_dose=50.0,
            max_sformula_dose=50.0,
            penalty=3,
            num=6,
            excludes=[],
            beam_width_factor=0.5,
            beam_multiplier=2.0,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_not_called()
        self.assertRegex(m_stdout.getvalue(), r'資料庫尚未收錄以下品項: 麻黃湯')

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher.FormulaDatabase, 'from_file', return_value=DATABASE_SAMPLE)
    def test_cmd_search_formulas(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            verbosity=50,
            database='custom_db.yaml',
            items=[('桂枝湯', 3), ('桂枝', 1)],
            raw=False,
            algorithm='exhaustive',
            max_cformulas=2,
            max_sformulas=3,
            min_cformula_dose=1.0,
            min_sformula_dose=0.3,
            max_cformula_dose=50.0,
            max_sformula_dose=50.0,
            penalty=3,
            num=6,
            excludes=[],
            beam_width_factor=0.5,
            beam_multiplier=2.0,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_called_once_with(
            m_load.return_value, {'桂枝': 13, '白芍': 6}, [('桂枝湯', 3), ('桂枝', 1)],
            algorithm='exhaustive', excludes={'桂枝湯'},
            penalty_factor=3, top_n=6,
            max_cformulas=2, max_sformulas=3,
            min_cformula_dose=1.0, min_sformula_dose=0.3,
            max_cformula_dose=50.0, max_sformula_dose=50.0,
            beam_width_factor=0.5, beam_multiplier=2.0,
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher.FormulaDatabase, 'from_file', return_value=DATABASE_SAMPLE)
    def test_cmd_search_formulas_nonexist(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            verbosity=50,
            database='custom_db.yaml',
            items=[('桂枝湯', 3), ('白芍', 1), ('生薑', 1)],
            raw=False,
            algorithm='exhaustive',
            max_cformulas=2,
            max_sformulas=3,
            min_cformula_dose=1.0,
            min_sformula_dose=0.3,
            max_cformula_dose=50.0,
            max_sformula_dose=50.0,
            penalty=3,
            num=6,
            excludes=[],
            beam_width_factor=0.5,
            beam_multiplier=2.0,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_not_called()
        self.assertRegex(m_stdout.getvalue(), r'資料庫尚未收錄以下品項: 白芍, 生薑')

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher.FormulaDatabase, 'from_file', return_value=DATABASE_SAMPLE)
    def test_cmd_search_herbs(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            verbosity=50,
            database='custom_db.yaml',
            items=[('桂枝', 4), ('白芍', 2)],
            raw=True,
            algorithm='exhaustive',
            max_cformulas=2,
            max_sformulas=3,
            min_cformula_dose=1.0,
            min_sformula_dose=0.3,
            max_cformula_dose=50.0,
            max_sformula_dose=50.0,
            penalty=5,
            num=10,
            excludes=[],
            beam_width_factor=0.5,
            beam_multiplier=2.0,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_called_once_with(
            m_load.return_value, {'桂枝': 4, '白芍': 2}, None,
            algorithm='exhaustive', excludes=set(),
            penalty_factor=5, top_n=10,
            max_cformulas=2, max_sformulas=3,
            min_cformula_dose=1.0, min_sformula_dose=0.3,
            max_cformula_dose=50.0, max_sformula_dose=50.0,
            beam_width_factor=0.5, beam_multiplier=2.0,
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'search')
    @mock.patch.object(cli.searcher.FormulaDatabase, 'from_file', return_value=DATABASE_SAMPLE)
    def test_cmd_search_herbs_nonexist(self, m_load, m_search, m_stdout):
        cli.cmd_search(SimpleNamespace(
            verbosity=50,
            database='custom_db.yaml',
            items=[('桂枝', 4), ('生薑', 3), ('炙甘草', 2)],
            raw=True,
            algorithm='exhaustive',
            max_cformulas=2,
            max_sformulas=3,
            min_cformula_dose=1.0,
            min_sformula_dose=0.3,
            max_cformula_dose=50.0,
            max_sformula_dose=50.0,
            penalty=5,
            num=10,
            excludes=[],
            beam_width_factor=0.5,
            beam_multiplier=2.0,
        ))
        m_load.assert_called_once_with('custom_db.yaml')
        m_search.assert_not_called()
        self.assertRegex(m_stdout.getvalue(), r'資料庫尚未收錄與以下中藥相關的科學中藥: 生薑, 炙甘草')

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli.searcher, 'find_best_matches', wraps=cli.searcher.find_best_matches)
    def test_search_herbs(self, m_find, m_stdout):
        cli.search(
            DATABASE_SAMPLE, {'桂枝': 9, '白芍': 6},
            excludes=None, max_cformulas=2, max_sformulas=3, penalty_factor=3, top_n=6,
        )
        m_find.assert_called_once_with(
            DATABASE_SAMPLE, {'桂枝': 9, '白芍': 6},
            excludes=None, max_cformulas=2, max_sformulas=3, penalty_factor=3, top_n=6,
        )

    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli.searcher, 'find_best_matches', wraps=cli.searcher.find_best_matches)
    def test_search_formula(self, m_find, m_stdout):
        cli.search(
            DATABASE_SAMPLE2, {'桂枝': 9, '白芍': 6},
            excludes={'桂枝湯'}, max_cformulas=2, max_sformulas=3, penalty_factor=3, top_n=6,
        )
        m_find.assert_called_once_with(
            DATABASE_SAMPLE2, {'桂枝': 9, '白芍': 6},
            excludes={'桂枝湯'}, max_cformulas=2, max_sformulas=3, penalty_factor=3, top_n=6,
        )


class TestCmdConvert(unittest.TestCase):
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch.object(cli, 'converter')
    def test_cmd_convert(self, m_converter, m_stdout):
        m_handler = mock.Mock(**{'load.return_value': {'dummy': 'value'}})
        m_converter.LicenseFileHandler.return_value = m_handler

        cli.cmd_convert(SimpleNamespace(
            verbosity=50,
            file='input.csv',
            output='output.yaml',
            vendor=None,
            unit_dosage=False,
            config='custom_conf.yaml',
        ))

        m_converter.log.setLevel.assert_called_once_with(50)
        m_converter.LicenseFileHandler.assert_called_once_with()
        m_handler.load_config.assert_called_once_with('custom_conf.yaml')
        m_handler.load.assert_called_once_with('input.csv', use_unit_dosage=False, filter_vendor=None)
        m_handler.dump.assert_called_once_with({'dummy': 'value'}, 'output.yaml')
