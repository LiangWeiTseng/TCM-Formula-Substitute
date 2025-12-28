import os
import sys

try:
    import gradio as gr
except ModuleNotFoundError:
    print('找不到相關套件。請執行以下命令安裝: pip install .[gui]')
    sys.exit(1)

from . import __version__, cli, searcher


def get_db_file(dbname):
    if dbname and dbname != '順天堂':
        return os.path.normpath(os.path.join(searcher.DEFAULT_DATAFILE, '..', f'database_{dbname}.yaml'))
    else:
        return searcher.DEFAULT_DATAFILE


def load_db(dbname):
    dbfile = get_db_file(dbname)
    try:
        return searcher.FormulaDatabase.from_file(dbfile)
    except OSError as exc:
        raise gr.Error(f'無法載入資料庫 "{dbname}": {exc}')


def search(items, raw, excludes,
           max_cformulas, max_sformulas,
           min_cformula_dose, min_sformula_dose,
           max_cformula_dose, max_sformula_dose,
           penalty, num, dbname):
    database = load_db(dbname)

    try:
        parser = cli.name_value(cli.bounded_float(0.1))
        items = [parser(s) for s in items.split()]
        if not items:
            raise ValueError('請輸入至少一個品項')
    except Exception as exc:
        raise gr.Error(f'[目標組成] 錯誤: {exc}') from exc

    for val, name in (
        (num, '輸出筆數'),
        (max_cformulas, '最大複方數'),
        (max_sformulas, '最大單方數'),
        (min_cformula_dose, '最小科中複方劑量'),
        (min_sformula_dose, '最小科中單方劑量'),
        (max_cformula_dose, '最大科中複方劑量'),
        (max_sformula_dose, '最大科中單方劑量'),
        (penalty, '非目標藥材懲罰倍率'),
    ):
        if val is None:
            raise gr.Error(f'[{name}] 錯誤: 空白或格式不正確')

    excludes = set(excludes.split())

    try:
        yield gr.update(value='🔍 搜尋中...', visible=True)

        lines = []
        gen = cli.search(database, items, excludes, raw, top_n=num,
                         max_cformulas=max_cformulas, max_sformulas=max_sformulas,
                         min_cformula_dose=min_cformula_dose, min_sformula_dose=min_sformula_dose,
                         max_cformula_dose=max_cformula_dose, max_sformula_dose=max_sformula_dose,
                         penalty_factor=penalty)

        for msg in gen:
            if msg is None:
                yield '\n'.join(lines) + '\n\n' + '🔍 搜尋中...'
                continue
            lines.append(msg)

        yield '\n'.join(lines)
    except Exception as exc:
        raise gr.Error(f'錯誤: {exc}') from exc


def list_formulas(dbname):
    database = load_db(dbname)
    value = '\n'.join(sorted(database))
    return gr.update(value=value, visible=True)


def list_herbs(dbname):
    database = load_db(dbname)
    value = '\n'.join(sorted(database.herbs))
    return gr.update(value=value, visible=True)


def create_app():
    with gr.Blocks(title=f'缺藥救星 v{__version__}') as app:
        gr.Markdown(f'# 🌿 缺藥救星 v{__version__}')
        gr.Markdown('搜尋中藥配方的替代組合。')

        with gr.Row():
            with gr.Column():
                items = gr.Textbox(
                    label='目標組成',
                    placeholder="""要搜尋的科學中藥品項及劑量。例如 '補中益氣湯:6.0 白芍:1.0'""",
                    lines=3,
                )
                raw = gr.Checkbox(
                    label='查詢生藥組成',
                )
                excludes = gr.Textbox(
                    label='排除品項',
                    placeholder="""要排除的科學中藥品項。例如 '小建中湯 桂枝去芍藥湯'""",
                    lines=2,
                )
                num = gr.Number(value=5, minimum=0, maximum=25, step=1, label='輸出筆數')
                dbname = gr.Dropdown(
                    label='資料庫來源',
                    choices=['順天堂', '科達', '天一', '天明', '仙豐', '莊松榮', '勝昌', '港香蘭'],
                )

                with gr.Accordion('進階參數設定', open=False):
                    with gr.Row():
                        max_cformulas = gr.Number(value=2, minimum=0, maximum=10, step=1, label='最大複方數')
                        max_sformulas = gr.Number(value=3, minimum=0, maximum=50, step=1, label='最大單方數')
                        min_cformula_dose = gr.Number(value=1.0, minimum=0.1, step=0.1, label='最小科中複方劑量')
                        min_sformula_dose = gr.Number(value=0.3, minimum=0.1, step=0.1, label='最小科中單方劑量')
                        max_cformula_dose = gr.Number(value=50.0, minimum=1.0, step=1.0, label='最大科中複方劑量')
                        max_sformula_dose = gr.Number(value=50.0, minimum=1.0, step=1.0, label='最大科中單方劑量')
                    penalty = gr.Number(value=2.0, minimum=0.0, step=0.1, label='非目標藥材懲罰倍率')
                with gr.Row():
                    btn = gr.Button('開始搜尋', variant='primary')
                    btn_list_formulas = gr.Button('列出所有方劑')
                    btn_list_herbs = gr.Button('列出所有藥材')

            with gr.Column():
                output_txt = gr.Code(
                    label='查詢結果',
                    language=None,
                    show_label=False,
                    container=False,
                    show_line_numbers=False,
                    wrap_lines=True,
                    lines=3,
                    buttons=[],
                    visible=False,
                )

        btn.click(
            fn=search,
            inputs=[
                items, raw, excludes,
                max_cformulas, max_sformulas,
                min_cformula_dose, min_sformula_dose,
                max_cformula_dose, max_sformula_dose,
                penalty, num,
                dbname,
            ],
            outputs=output_txt,
        )
        btn_list_formulas.click(
            fn=list_formulas,
            inputs=[dbname],
            outputs=output_txt,
        )
        btn_list_herbs.click(
            fn=list_herbs,
            inputs=[dbname],
            outputs=output_txt,
        )

    return app


def main(share=True, inbrowser=True, debug=False):
    app = create_app()
    return app.launch(share=share, inbrowser=inbrowser, debug=debug)
