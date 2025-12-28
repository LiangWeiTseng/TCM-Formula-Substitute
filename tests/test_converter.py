import csv
import unittest
from decimal import Decimal
from io import StringIO
from textwrap import dedent
from unittest import mock

from formula_altsearch import converter


class TestLicenseFileHandler(unittest.TestCase):
    def _generate_csv(self, rows):
        fh = StringIO()
        writer = csv.DictWriter(fh, ['許可證字號', '藥品名稱', '處方成分', '藥商名稱'])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        fh.seek(0)
        return fh

    def generate_dummy_csv(self):
        return self._generate_csv([
            {
                '許可證字號': '衛部藥製字第000000號',
                '藥商名稱': '張三製藥股份有限公司',
                '藥品名稱': '“張三”桂枝湯濃縮細粒\nGUI ZHI TANG EXTRACT GRANULE "ZHANG SAN"',
                '處方成分': dedent(
                    """\
                    處方:每12公克中含有
                    桂枝 (6.0 g)
                    白芍 (6.0 g)
                    炙甘草 (4.0 g)
                    生薑 (6.0 g)
                    大棗 (5.0 g)
                    以上生藥製成浸膏6.0g(生藥與浸膏比例27:6=4.5:1) ( )
                    澱粉 (5.88 g)
                    羧甲基纖維素鈉 (0.12 g)
                    """
                ),
            },
        ])

    def test_load_config(self):
        data = {
            'herb_remapper': {
                '澱粉': None,
                '大黃末': '大黃',
            },
        }
        handler = converter.LicenseFileHandler()
        handler._load_config(data)
        self.assertEqual(handler.herb_remapper, {
            '澱粉': None,
            '大黃末': '大黃',
        })

    def test_load(self):
        fh = self.generate_dummy_csv()
        handler = converter.LicenseFileHandler()
        result = handler._load(fh, use_unit_dosage=False, filter_vendor=None)
        self.assertEqual(result, [
            {
                'name': '“張三”桂枝湯濃縮細粒',
                'key': '桂枝湯',
                'vendor': '張三製藥股份有限公司',
                'url': 'https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLResultDetail.aspx?LICEWORDID=01&LICENUM=000000',
                'unit_dosage': Decimal('12'),
                'composition': {
                    '桂枝': Decimal('6.0'),
                    '白芍': Decimal('6.0'),
                    '炙甘草': Decimal('4.0'),
                    '生薑': Decimal('6.0'),
                    '大棗': Decimal('5.0'),
                },
            },
        ])

    def test_load_use_unit_dosage(self):
        fh = self.generate_dummy_csv()
        handler = converter.LicenseFileHandler()
        result = handler._load(fh, use_unit_dosage=True, filter_vendor=None)
        self.assertEqual(result, [
            {
                'name': '“張三”桂枝湯濃縮細粒',
                'key': '桂枝湯',
                'vendor': '張三製藥股份有限公司',
                'url': 'https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLResultDetail.aspx?LICEWORDID=01&LICENUM=000000',
                'composition': {
                    '桂枝': Decimal('0.5'),
                    '白芍': Decimal('0.5'),
                    '炙甘草': Decimal('0.3333333333333333333333333333'),
                    '生薑': Decimal('0.5'),
                    '大棗': Decimal('0.4166666666666666666666666667'),
                },
            },
        ])

    @mock.patch.object(converter, 'log')
    def test_load_filter_vendor(self, m_log):
        handler = converter.LicenseFileHandler()

        # filter with regex
        fh = self._generate_csv([
            {
                '許可證字號': '衛部藥製字第000000號',
                '藥商名稱': '張三製藥股份有限公司',
                '藥品名稱': '“張三”桂枝湯濃縮細粒\nGUI ZHI TANG EXTRACT GRANULE "ZHANG SAN"',
                '處方成分': dedent(
                    """\
                    處方:每12公克中含有
                    桂枝 (6.0 g)
                    以上生藥製成浸膏6.0g
                    澱粉 (5.88 g)
                    """
                ),
            },
            {
                '許可證字號': '衛部藥製字第000001號',
                '藥商名稱': '李四製藥股份有限公司',
                '藥品名稱': '“李四”桂枝湯濃縮細粒\nGUI ZHI TANG EXTRACT GRANULE "LI SI"',
                '處方成分': dedent(
                    """\
                    處方:每12公克中含有
                    桂枝 (6.0 g)
                    以上生藥製成浸膏6.0g
                    澱粉 (5.88 g)
                    """
                ),
            },
        ])
        result = handler._load(fh, use_unit_dosage=False, filter_vendor=r'張[一二三]')
        self.assertEqual(result, [
            {
                'name': mock.ANY,
                'key': mock.ANY,
                'vendor': '張三製藥股份有限公司',
                'url': mock.ANY,
                'unit_dosage': mock.ANY,
                'composition': mock.ANY,
            },
        ])

        # filter as plain text if regex syntax invalid
        fh = self._generate_csv([
            {
                '許可證字號': '衛部藥製字第000000號',
                '藥商名稱': '????公司',
                '藥品名稱': '“????”桂枝湯濃縮細粒\nGUI ZHI TANG EXTRACT GRANULE "ZHANG SAN"',
                '處方成分': dedent(
                    """\
                    處方:每12公克中含有
                    桂枝 (6.0 g)
                    以上生藥製成浸膏6.0g
                    澱粉 (5.88 g)
                    """
                ),
            },
            {
                '許可證字號': '衛部藥製字第000001號',
                '藥商名稱': 'XXXX公司',
                '藥品名稱': '“XXXX”桂枝湯濃縮細粒\nGUI ZHI TANG EXTRACT GRANULE "ZHANG SAN"',
                '處方成分': dedent(
                    """\
                    處方:每12公克中含有
                    桂枝 (6.0 g)
                    以上生藥製成浸膏6.0g
                    澱粉 (5.88 g)
                    """
                ),
            },
        ])
        result = handler._load(fh, use_unit_dosage=False, filter_vendor=r'??公司')
        self.assertEqual(result, [
            {
                'name': mock.ANY,
                'key': mock.ANY,
                'vendor': '????公司',
                'url': mock.ANY,
                'unit_dosage': mock.ANY,
                'composition': mock.ANY,
            },
        ])

    def test_dump(self):
        data = [
            {
                'name': '“張三”桂枝湯濃縮細粒',
                'key': '桂枝湯',
                'vendor': '張三製藥股份有限公司',
                'url': 'https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLResultDetail.aspx?LICEWORDID=01&LICENUM=000000',
                'unit_dosage': Decimal('12'),
                'composition': {
                    '桂枝': Decimal('6.0'),
                    '白芍': Decimal('6.0'),
                    '炙甘草': Decimal('4.0'),
                    '生薑': Decimal('6.0'),
                    '大棗': Decimal('5.0'),
                },
            },
            {
                'name': '“張三”桂枝湯濃縮細粒',
                'key': '桂枝湯',
                'vendor': '張三製藥股份有限公司',
                'url': 'https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLResultDetail.aspx?LICEWORDID=01&LICENUM=000000',
                'composition': {
                    '桂枝': Decimal('0.5'),
                    '白芍': Decimal('0.5'),
                    '炙甘草': Decimal('0.3333333333333333333333333333'),
                    '生薑': Decimal('0.5'),
                    '大棗': Decimal('0.4166666666666666666666666667'),
                },
            },
        ]

        fh = StringIO()
        handler = converter.LicenseFileHandler()
        handler._dump(data, fh, indent=2)
        self.assertEqual(fh.getvalue(), dedent(
            """\
            - name: “張三”桂枝湯濃縮細粒
              key: 桂枝湯
              vendor: 張三製藥股份有限公司
              url: https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLResultDetail.aspx?LICEWORDID=01&LICENUM=000000
              unit_dosage: 12.0
              composition:
                桂枝: 6.0
                白芍: 6.0
                炙甘草: 4.0
                生薑: 6.0
                大棗: 5.0
            - name: “張三”桂枝湯濃縮細粒
              key: 桂枝湯
              vendor: 張三製藥股份有限公司
              url: https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLResultDetail.aspx?LICEWORDID=01&LICENUM=000000
              composition:
                桂枝: 0.5
                白芍: 0.5
                炙甘草: 0.333
                生薑: 0.5
                大棗: 0.417
            """
        ))
