import argparse
import logging
import time

from . import __version__, converter, searcher


def search(database, target_composition, **options):
    print('目標組成:')
    for herb, amount in target_composition.items():
        print(f'    {herb}: {amount:.2f}')
    print('')

    print(f'品項總數: {len(database.keys())}')
    print('')

    start = time.time()
    best_matches = searcher.find_best_matches(database, target_composition, **options)
    elapsed = time.time() - start
    print(f'搜尋費時: {elapsed}')
    print('')

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
        print(f'匹配度: {match_percentage:.2f}%，組合: {combination_str} (總計: {total:.1f})')
        for herb, amount in herbs_amount:
            if herb in target_composition:
                herb = f'**{herb}**'
            print(f'    {herb}: {amount:.2f}')

        if missing_herbs:
            print('尚缺藥物:')
            for herb, amount in missing_herbs.items():
                print(f'    {herb}: {amount:.2f}')

        print('')


def cmd_search(args):
    searcher.log.setLevel(args.verbosity)
    try:
        database = searcher.load_formula_database(args.database)
    except OSError:
        print(f'無法載入資料庫檔案: {args.database}')
        return

    all_herbs = set()
    all_sformulas = set()
    all_cformulas = set()
    for name, data in database.items():
        if len(data) > 1:
            all_cformulas.add(name)
        else:
            all_sformulas.add(name)
        all_herbs |= data.keys()

    target_composition = {}
    excludes = set(args.excludes)

    if args.raw:
        unknowns = {}
        for herb, amount in args.items:
            if herb in all_herbs:
                target_composition[herb] = target_composition.get(herb, 0) + amount
            else:
                unknowns[herb] = None
        if unknowns:
            print(f'資料庫尚未收錄與以下中藥相關的科學中藥: {", ".join(unknowns)}')
            return
    else:
        unknowns = {}
        for item, dosage in args.items:
            if item in all_cformulas or item in all_sformulas:
                if item in all_cformulas:
                    excludes.add(item)
                adjusted = {herb: dosage * amount for herb, amount in database[item].items()}
                for herb, amount in adjusted.items():
                    target_composition[herb] = target_composition.get(herb, 0) + amount
            else:
                unknowns[item] = None
        if unknowns:
            print(f'資料庫尚未收錄以下品項: {", ".join(unknowns)}')
            return

    search(database, target_composition,
           excludes=excludes, max_cformulas=args.max_cformulas, max_sformulas=args.max_sformulas,
           penalty_factor=args.penalty, top_n=args.num)


def cmd_convert(args):
    converter.log.setLevel(args.verbosity)
    handler = converter.LicenseFileHandler()
    handler.load_config(args.config)
    data = handler.load(args.file, use_unit_dosage=args.unit_dosage, filter_vendor=args.vendor)
    handler.dump(data, args.output)


def parse_item(value):
    name, sep, dose = value.partition(':')
    return name, float(dose)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="""搜尋中藥配方的替代組合。""",
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
        help="""搜尋中藥配方的替代組合""",
        description="""搜尋中藥配方的替代組合。""",
    )
    parser_search.set_defaults(func=cmd_search)
    parser_search.add_argument(
        'items', metavar='NAME:DOSE', nargs='+', type=parse_item, action='store',
        help="""要搜尋的科學中藥品項及劑量。例如 '補中益氣湯:6.0 桂枝:1.0'""",
    )
    parser_search.add_argument(
        '-r', '--raw', default=False, action='store_true',
        help="""搜尋生藥劑量，加入此參數時每個 NAME:DOSE 代表配方中的生藥及劑量""",
    )
    parser_search.add_argument(
        '-e', '--exclude', dest='excludes', metavar='NAME', default=[], action='append',
        help="""要排除的科學中藥品項，使之不受評估與輸出。可多次指定此參數，例如
'-e 桂枝去芍藥湯 -e 芍藥甘草湯'。NAME:DOSE 輸入的科學中藥複方會自動排除，不必額外加入。""",
    )
    parser_search.add_argument(
        '--mc', '--max-cformulas', dest='max_cformulas', metavar='N', default=2, type=int, action='store',
        help="""最大科中複方數 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '--ms', '--max-sformulas', dest='max_sformulas', metavar='N', default=2, type=int, action='store',
        help="""最大科中單方數 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-p', '--penalty', metavar='FACTOR', default=2.0, type=float, action='store',
        help="""未配對項目的懲罰因子 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-n', '--num', metavar='N', default=5, type=int, action='store',
        help="""最佳匹配結果顯示筆數 (預設: %(default)s)""",
    )
    parser_search.add_argument(
        '-d', '--database', metavar='FILE', default=searcher.DEFAULT_DATAFILE, action='store',
        help="""使用自訂的資料庫檔案 (預設: %(default)s)""",
    )

    parser_convert = subparsers.add_parser(
        'convert', aliases=['c'],
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
