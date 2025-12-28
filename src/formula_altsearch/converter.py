import csv
import logging
import os
import re
from decimal import Decimal

import yaml

DEFAULT_CONFIG_FILE = os.path.normpath(os.path.join(__file__, '..', 'converter.yaml'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
log = logging.getLogger(__name__)


def decimal_representer(dumper, value):
    s = f'{value:.3f}'.rstrip('0').rstrip('.')
    if '.' not in s:
        s += '.0'
    return dumper.represent_scalar('tag:yaml.org,2002:float', s)


class LicenseFileDumper(yaml.SafeDumper):
    pass


LicenseFileDumper.add_representer(Decimal, decimal_representer)


class LicenseFileHandler:
    def load_config(self, file):
        with open(file, encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
        self._load_config(data)

    def _load_config(self, data):
        for key in ('herb_remapper', 'key_remapper', 'patch'):
            try:
                setattr(self, key, data[key])
            except KeyError:
                pass

    def load(self, file, use_unit_dosage=False, filter_vendor=None):
        with open(file, encoding='utf-8-sig') as fh:
            return self._load(fh, use_unit_dosage, filter_vendor)

    def _load(self, fh, use_unit_dosage, filter_vendor):
        if filter_vendor is not None:
            try:
                filter_vendor = re.compile(filter_vendor, flags=re.M)
            except re.error:
                log.warning('正規表示式格式錯誤，將視為純文字比對: %s', filter_vendor)
                filter_vendor = re.compile(re.escape(filter_vendor), flags=re.M)

        data = []
        reader = csv.DictReader(fh)
        for row in reader:
            log.debug('處理品項: %s', repr(row['藥品名稱']))

            try:
                self._apply_patch(row)

                type_ = row.get('劑型與類別')
                if type_ is not None and not re.match(r'濃縮顆粒劑', type_):
                    continue

                vendor = row.get('藥商名稱').strip() or self.retrieve_vendor_from_name(row['藥品名稱'])
                if filter_vendor and not filter_vendor.search(vendor):
                    log.debug('略過藥商名稱不符合的品項: %s', repr(row['藥品名稱']))
                    continue

                name = self.retrieve_item_name(row['藥品名稱'])
                key = row.get('_key', self.retrieve_item_key(row['藥品名稱']))
                url = self.retrieve_url(row['許可證字號'])
                composition, unit_dosage = self.retrieve_composition(row['處方成分'])

                item = {
                    'name': name,
                    'key': key,
                    'vendor': vendor,
                    'url': url,
                    'unit_dosage': unit_dosage,
                    'composition': composition,
                }

                if use_unit_dosage:
                    del item['unit_dosage']
                    for name, dosage in item['composition'].items():
                        item['composition'][name] = dosage / unit_dosage

                data.append(item)
            except Exception as exc:
                log.error('無法解析品項 %s: %s', repr(row['藥品名稱']), exc)

        return data

    def dump(self, data, file, indent=2):
        with open(file, 'w', encoding='utf-8') as fh:
            self._dump(data, fh, indent)

    def _dump(self, data, fh, indent):
        yaml.dump(data, fh, Dumper=LicenseFileDumper, allow_unicode=True, indent=indent, sort_keys=False)

    def retrieve_item_name(self, text):
        return text.split('\n')[0]

    def retrieve_item_key(self, text):
        m = re.search(r'([^”〞"]*)濃縮(?:顆|細)粒', text, flags=re.M)
        if m:
            return self._retrieve_item_key_fix_name(m[1].strip())

        log.warning('無法解析藥品名稱，取全名作為索引值: %s', repr(text))
        return self._retrieve_item_key_fix_name(text.split('\n')[0])

    def _retrieve_item_key_fix_name(self, name):
        return self.key_remapper.get(name, name)

    def retrieve_vendor_from_name(self, text):
        m = re.search(r'“([^”]*)”', text)
        if m:
            return m[1].strip()

        m = re.search(r'〝([^〞]*)〞', text)
        if m:
            return m[1].strip()

        m = re.search(r'"([^"]*)"', text)
        if m:
            return m[1].strip()

        # handle some bad quote formats
        m = re.search(r'”([^”]*)”', text)
        if m:
            return m[1].strip()

        log.warning('無法解析藥品名稱，無法取得藥廠名稱: %s', repr(text))
        return ''

    def retrieve_url(self, text):
        m = re.search(r'\d+', text)
        num = m[0]
        return f'https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLResultDetail.aspx?LICEWORDID=01&LICENUM={num}'

    def retrieve_composition(self, text):
        comp = {}
        lines = text.split('\n')

        m = re.search(r'處方:.*?每\s*([\d.]*)\s*(?:gm?\s*)?(?:公?克\s*)?中?含有?', lines[0])
        if not m:
            raise ValueError(f'無法從第 1 行解析單位克數: {lines[0]!r}')

        unit_dosage = Decimal(m[1]) if m[1] else 1

        for i in range(1, len(lines)):
            m = re.search(r'生藥|製成|浸膏|比例', lines[i])
            if m:
                break

            name, dosage = self._retrieve_composition_line(lines, i)
            if name:
                comp[name] = comp.get(name, 0) + dosage

        _i = i + 1
        for i in range(_i, len(lines)):
            if lines[i] == '':
                break

            # this may happen due to extra bad line breaking
            m = re.search(r'生藥與浸膏', lines[i])
            if m:
                continue

            name, dosage = self._retrieve_composition_line(lines, i)
            if name:
                comp[name] = comp.get(name, 0) + dosage

        return comp, unit_dosage

    def _retrieve_composition_line(self, lines, i):
        m = re.search(r'^(.*?)\s*\(([\d.]+)\s*(?:gm?|公?克)\)', lines[i])
        if m:
            return self._retrieve_composition_line_fix_name(m[1]), Decimal(m[2])

        m = re.search(r'^(.*?)\s*\(([\d.]+)\s*mg\)', lines[i])
        if m:
            return self._retrieve_composition_line_fix_name(m[1]), Decimal(m[2]) / 1000

        raise ValueError(f'無法從第 {i + 1!r} 行解析組成中藥: {lines[i]!r}')

    def _retrieve_composition_line_fix_name(self, name):
        # fix possible percentage info
        m = re.search(r'\s*\([\d.]+%\)$', name)
        if m:
            name = name[:m.start()]

        return self.herb_remapper.get(name, name)

    def _apply_patch(self, row):
        id_ = row['許可證字號']
        name = row.get('藥品名稱')
        try:
            patches = self.patch[id_]
        except KeyError:
            return

        log.debug('套用補綴: %s (%s)', repr(id_), repr(name))
        for patch in patches:
            try:
                self._apply_patch_row(row, patch)
            except Exception as exc:
                log.error('無法套用補綴 %s: %s', patch, exc)

    def _apply_patch_row(self, row, patch):
        action = patch['action']

        if action == 'replace':
            field = patch['field']
            pattern = patch['pattern']
            repl = patch['repl']
            count = patch.get('count')
            opts = {k: v for k, v in (
                ('count', count),
            ) if v is not None}
            row[field] = row[field].replace(pattern, repl, **opts)
        elif action == 'replace_re':
            field = patch['field']
            pattern = patch['pattern']
            repl = patch['repl']
            count = patch.get('count', 0)
            flags = patch.get('flags', re.M)
            row[field] = re.sub(pattern, repl, row[field], count=count, flags=flags)
        elif action == 'set_key':
            row['_key'] = patch['value']

    herb_remapper = {
        '': None,
        '乳糖': None,
        '二氧化矽': None,
        '澱粉': None,
        '玉米澱粉': None,
        '糊精': None,
        '羧甲基纖維素鈉': None,
        '麥芽糊精': None,
    }

    key_remapper = {}

    patch = {}
