import argparse
import logging
import time

from wcwidth import wcwidth

from . import __version__, converter, searcher


class CJKRawDescriptionHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _split_lines(self, text, width):
        lines = []
        buf = ''
        cur_width = 0

        for ch in text:
            w = wcwidth(ch)
            if w < 0:
                w = 1
            if ch == '\n':
                lines.append(buf)
                buf = ''
                cur_width = 0
                continue
            if cur_width + w > width:
                lines.append(buf)
                buf = ch
                cur_width = w
            else:
                buf += ch
                cur_width += w
        if buf:
            lines.append(buf)
        return lines


def _bound_str(lower=None, upper=None, lower_open=False, upper_open=False):
    lb = '∞' if lower is None else lower
    ub = '∞' if upper is None else lower
    lm = '(' if lower_open or lower is None else '['
    um = ')' if upper_open or upper is None else ']'
    return f'{lm}{lb}, {ub}{um}'


def name_value(value_type):
    def validator(value):
        name, sep, dose_str = value.rpartition(':')

        if not sep:
            raise argparse.ArgumentTypeError("value must contain ':'")

        try:
            parsed_value = value_type(dose_str)
        except Exception as exc:
            raise argparse.ArgumentTypeError(f'invalid value: {exc}')

        return name, parsed_value

    validator.__name__ = f'name_value({value_type.__name__})'
    return validator


def bounded_float(lower=None, upper=None, lower_open=False, upper_open=False):
    def validator(value):
        try:
            value = float(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' is not a valid float number")

        if lower is not None:
            if lower_open:
                if not value > lower:
                    raise argparse.ArgumentTypeError(f'value must > {lower}')
            else:
                if not value >= lower:
                    raise argparse.ArgumentTypeError(f'value must >= {lower}')

        if upper is not None:
            if upper_open:
                if not value < upper:
                    raise argparse.ArgumentTypeError(f'value must < {upper}')
            else:
                if not value <= upper:
                    raise argparse.ArgumentTypeError(f'value must <= {upper}')

        return value

    validator.__name__ = f'float{_bound_str(lower, upper, lower_open, upper_open)}'
    return validator


def bounded_int(lower=None, upper=None, lower_open=False, upper_open=False):
    def validator(value):
        try:
            value = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' is not a valid integer")

        if lower is not None:
            if lower_open:
                if not value > lower:
                    raise argparse.ArgumentTypeError(f'value must > {lower}')
            else:
                if not value >= lower:
                    raise argparse.ArgumentTypeError(f'value must >= {lower}')

        if upper is not None:
            if upper_open:
                if not value < upper:
                    raise argparse.ArgumentTypeError(f'value must < {upper}')
            else:
                if not value <= upper:
                    raise argparse.ArgumentTypeError(f'value must <= {upper}')

        return value

    validator.__name__ = f'int{_bound_str(lower, upper, lower_open, upper_open)}'
    return validator


def search(database, composition, excludes=None, raw=False, **opts):
    excludes = set() if excludes is None else set(excludes)

    target_composition = {}
    unknowns = {}
    if raw:
        for herb, amount in composition:
            if herb in database.herbs:
                target_composition[herb] = target_composition.get(herb, 0) + amount
            else:
                unknowns[herb] = None

        if unknowns:
            yield f'資料庫尚未收錄與以下中藥相關的科學中藥: {", ".join(unknowns)}'
            return

        combo_str = ''
    else:
        for formula, dosage in composition:
            if formula in database:
                if formula in database.cformulas:
                    excludes.add(formula)
                adjusted = {herb: dosage * amount for herb, amount in database[formula].items()}
                for herb, amount in adjusted.items():
                    target_composition[herb] = target_composition.get(herb, 0) + amount
            else:
                unknowns[formula] = None

        if unknowns:
            yield f'資料庫尚未收錄以下品項: {", ".join(unknowns)}'
            return

        combo_str = ' '.join(f'{formula}:{dosage:.1f}' for formula, dosage in composition)
        total = sum(dosage for _, dosage in composition)
        combo_str = f'{combo_str} (總計: {total:.1f})'

    yield f'目標組成: {combo_str}'
    for herb, amount in target_composition.items():
        yield f'    {herb}: {amount:.2f}'
    yield ''

    yield f'品項總數: {len(database.keys())}'

    # None as flush signal
    yield None

    yield ''
    start = time.time()
    best_matches = searcher.find_best_matches(database, target_composition, excludes=excludes, **opts)
    elapsed = time.time() - start
    yield f'搜尋費時: {elapsed}'
    yield ''

    for match in best_matches:
        match_percentage, combination, dosages = match

        combined_composition = {}
        for dosage, formula in zip(dosages, combination):
            for herb, amount in database[formula].items():
                combined_composition[herb] = combined_composition.get(herb, 0) + dosage * amount

        herbs_amount = sorted(combined_composition.items(), key=lambda item: (item[0] not in target_composition, item[0]))

        missing_herbs = {
            herb: amount
            for herb in target_composition
            if (amount := target_composition.get(herb)) and not combined_composition.get(herb)
        }

        combination_str = ' '.join(f'{formula}:{dosage:.1f}' for formula, dosage in zip(combination, dosages))
        total = sum(dosages)
        yield f'匹配度: {match_percentage:.2f}%，組合: {combination_str} (總計: {total:.1f})'
        for herb, amount in herbs_amount:
            if herb in target_composition:
                herb = f'**{herb}**'
            yield f'    {herb}: {amount:.2f}'

        if missing_herbs:
            yield '尚缺藥物:'
            for herb, amount in missing_herbs.items():
                yield f'    {herb}: {amount:.2f}'

        yield ''


def cmd_search(args):
    searcher.log.setLevel(args.verbosity)
    try:
        database = searcher.FormulaDatabase.from_file(args.database)
    except OSError:
        print(f'無法載入資料庫檔案: {args.database}')
        return

    gen = search(database, args.items, args.excludes, args.raw, top_n=args.num,
                 max_cformulas=args.max_cformulas, max_sformulas=args.max_sformulas,
                 min_cformula_dose=args.min_cformula_dose, min_sformula_dose=args.min_sformula_dose,
                 max_cformula_dose=args.max_cformula_dose, max_sformula_dose=args.max_sformula_dose,
                 penalty_factor=args.penalty, algorithm=args.algorithm,
                 beam_width_factor=args.beam_width_factor, beam_multiplier=args.beam_multiplier)

    for msg in gen:
        if msg is not None:
            print(msg)


def cmd_list(args):
    searcher.log.setLevel(args.verbosity)
    try:
        database = searcher.FormulaDatabase.from_file(args.database)
    except OSError:
        print(f'無法載入資料庫檔案: {args.database}')
        return

    if args.raw:
        names = sorted({k for c in database.values() for k in c})
    else:
        names = sorted(database)

    if args.keywords:
        keywords = set(args.keywords)
        fn = any if args.any else all
        for name in (n for n in names if fn(k in n for k in keywords)):
            print(name)
    else:
        for name in names:
            print(name)


def cmd_gui(args):
    from . import gui
    gui.main(share=args.share, inbrowser=args.inbrowser)


def cmd_convert(args):
    converter.log.setLevel(args.verbosity)
    handler = converter.LicenseFileHandler()
    handler.load_config(args.config)
    data = handler.load(args.file, use_unit_dosage=args.unit_dosage, filter_vendor=args.vendor)
    handler.dump(data, args.output)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="""搜尋中藥配方的替代組合。""",
        formatter_class=CJKRawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--version', action='version', version=f'{__package__} {__version__}',
        help="""顯示版本資訊並離開""",
    )
    parser.add_argument(
        '-v', '--verbose', dest='verbosity', const=logging.DEBUG, default=logging.INFO, action='store_const',
        help="""顯示除錯及細節資訊""",
    )
    subparsers = parser.add_subparsers(
        metavar='COMMAND',
        help="""執行子命令，可用如 %(prog)s search -h 取得相關說明""",
    )

    parser_search = subparsers.add_parser(
        'search', aliases=['s'],
        formatter_class=CJKRawDescriptionHelpFormatter,
        help="""搜尋中藥配方的替代組合""",
        description="""搜尋中藥配方的替代組合。""",
        epilog="""ALGORITHM 演算法可用選項:
  - beam (集束演算法): 利用快捷算式及多層篩選避開探索潛力偏低的組合，能很快找出許多接近最佳的組合，\
但有機會錯過某些有價值的組合。
  - exhaustive (窮舉演算法): 窮舉測試所有可能組合，可保證找出最佳的組合，但組合數較多時運算速度極慢。""",
    )
    parser_search.set_defaults(func=cmd_search)
    parser_search.add_argument(
        'items', metavar='NAME:DOSE', nargs='+', action='store',
        type=name_value(bounded_float(0.1)),
        help="""要搜尋的科學中藥品項及劑量。例如 '補中益氣湯:6.0 桂枝:1.0'""",
    )
    parser_search.add_argument(
        '-r', '--raw', default=False, action='store_true',
        help="""搜尋生藥劑量，加入此參數時每個 NAME:DOSE 代表配方中的生藥及劑量""",
    )
    parser_search.add_argument(
        '-e', '--exclude', dest='excludes', metavar='NAME', default=[], action='append',
        help="""要排除的科學中藥品項，使之不受評估與輸出。可多次指定此參數，例如 \
'-e 桂枝去芍藥湯 -e 芍藥甘草湯'。NAME:DOSE 輸入的科學中藥複方會自動排除，不必額外加入。""",
    )
    parser_search.add_argument(
        '-C', '--max-cformulas', dest='max_cformulas', metavar='N', default=2,
        type=bounded_int(0), action='store',
        help="""最大科中複方數 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-S', '--max-sformulas', dest='max_sformulas', metavar='N', default=2,
        type=bounded_int(0), action='store',
        help="""最大科中單方數 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-cd', '--min-cformula-dose', metavar='N', default=1.0,
        type=bounded_float(0.1), action='store',
        help="""最小科中複方劑量 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-sd', '--min-sformula-dose', metavar='N', default=0.3,
        type=bounded_float(0.1), action='store',
        help="""最小科中單方劑量 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-Cd', '--max-cformula-dose', metavar='N', default=50.0,
        type=bounded_float(0.1), action='store',
        help="""最大科中複方劑量 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-Sd', '--max-sformula-dose', metavar='N', default=50.0,
        type=bounded_float(0.1), action='store',
        help="""最大科中單方劑量 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-p', '--penalty', metavar='FACTOR', default=2.0,
        type=bounded_float(0.0), action='store',
        help="""非目標藥材的懲罰倍率 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-n', '--num', metavar='N', default=5,
        type=bounded_int(0), action='store',
        help="""最佳匹配結果輸出筆數 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-d', '--database', metavar='FILE', default=searcher.DEFAULT_DATAFILE, action='store',
        help="""使用自訂的資料庫檔案 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-a', '--algorithm', default='beam', metavar='ALGORITHM', action='store',
        help="""要使用的搜尋演算法 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '--bwf', '--beam-width-factor', dest='beam_width_factor', metavar='FACTOR', default=2.0,
        type=bounded_float(0.0, lower_open=True), action='store',
        help="""集束搜尋演算法的集束寬度倍率。例如當此值為 2.0，而最佳匹配結果輸出筆數為 5 時，集束寬度為 10 \
(= 5 * 2.0)，演算法會篩選出 10 個最佳的 1 個複方解，對這些最佳解做加上第 2 個複方的測試，再篩選出 10 個最佳解做\
加上第 3 個複方的測試，依此類推。縮小此值可提高運算速度，但會降低輸出的多樣性，也可能導致輸出結果少於設定值。\
一般建議用在最佳匹配結果輸出筆數較大，導致運算速度過慢時，適當降低此值。 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '--bm', '--beam-mutliplier', dest='beam_multiplier', metavar='FACTOR', default=5.0,
        type=bounded_float(0.0), action='store',
        help="""集束搜尋演算法的集束擴充倍率。例如當集束寬度為 10，而此值為 3.0 時，精算取樣上限為 30 \
(= 10 * 3.0)，演算法會在篩選每層最佳結果時，先用快捷算式搜集 30 個最佳樣本，再對這些樣本做精確匹配度計算\
以取得 10 個局部最佳解。提高此值可減少遺漏最佳解的機會，但會降低運算速度。此值為 0 時，程式會直接略過快捷\
算式對所有可能組合使用精算 (優於設定非常大的值)。一般建議用在確認或懷疑某些最佳匹配被遺漏時，適當加大此值。 \
(預設: %(default)s)""",
    )

    parser_list = subparsers.add_parser(
        'list', aliases=['l'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="""列出資料庫中的相關品項""",
        description="""列出資料庫中的相關品項。""",
    )
    parser_list.set_defaults(func=cmd_list)
    parser_list.add_argument(
        'keywords', metavar='KEYWORD', nargs='*', action='store',
        help="""要查詢的關鍵字詞片段。例如 '苓 桂' 可列出所有含「苓」及「桂」的品項""",
    )
    parser_list.add_argument(
        '-r', '--raw', action='store_true',
        help="""查詢資料庫中的生藥品項""",
    )
    parser_list.add_argument(
        '--any', action='store_true',
        help="""列出符合任一關鍵字詞片段的品項""",
    )
    parser_list.add_argument(
        '-d', '--database', metavar='FILE', default=searcher.DEFAULT_DATAFILE, action='store',
        help="""使用自訂的資料庫檔案 (預設: %(default)s)""",
    )

    parser_gui = subparsers.add_parser(
        'gui', aliases=['g'],
        formatter_class=CJKRawDescriptionHelpFormatter,
        help="""開啟圖形操作介面""",
        description="""啟動本地伺服器，並在瀏覽器開啟圖形操作介面。""",
    )
    parser_gui.set_defaults(func=cmd_gui)
    parser_gui.add_argument(
        '-s', '--share', action='store_true',
        help="""允許他人透過公開的 https://*.gradio.live/ 網址存取圖形介面""",
    )
    parser_gui.add_argument(
        '--no-browse', dest='inbrowser', action='store_false',
        help="""不要自動在瀏覽器開啟圖形介面""",
    )

    parser_convert = subparsers.add_parser(
        'convert', aliases=['c'],
        formatter_class=CJKRawDescriptionHelpFormatter,
        help="""將 CSV 格式的中藥許可證資料檔轉換為 YAML 資料檔""",
        description="""將 CSV 格式的中藥許可證資料檔轉換為 YAML 資料檔。

中藥許可證資料檔取得方法：
  1. 前往衛生福利部中醫藥司的中醫藥許可證查詢頁面：
     https://service.mohw.gov.tw/DOCMAP/CusSite/TCMLQueryForm.aspx
  2. 在 [查詢類別] 勾選想查詢的項目，一般建議選擇 [效期內]。
  3. 點選表單中的 [匯出 CSV] 超連結，將匯出的 XLS 檔案儲存至本機。
  4. 用 Excel 或 LibreOffice 等軟體開啟 XLS 檔案，並轉存為 UTF-8 編碼的 CSV 檔案。""",
    )
    parser_convert.set_defaults(func=cmd_convert)
    parser_convert.add_argument(
        'file', action='store',
        help="""要轉換的檔案""",
    )
    parser_convert.add_argument(
        'output', action='store',
        help="""要輸出的檔案""",
    )
    parser_convert.add_argument(
        '--vendor', metavar='NAME', action='store',
        help="""篩選特定廠商名稱（正規表示式）""",
    )
    parser_convert.add_argument(
        '--unit-dosage', action='store_true',
        help="""儲存換算後的每克生藥含量""",
    )
    parser_convert.add_argument(
        '-c', '--config', metavar='FILE', default=converter.DEFAULT_CONFIG_FILE, action='store',
        help="""使用自訂的配置檔 (預設: %(default)s)""",
    )

    return parser.parse_args(argv)


def main():
    args = parse_args()

    if not hasattr(args, 'func'):
        parse_args(['-h'])
        return

    args.func(args)
