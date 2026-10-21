#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RELATORIO DOCX PARA O CONDOMINIO

Mesmo conteúdo e ordem do PDF (relatorio_pdf), editável no Word. Consome o
contexto de `montar_contexto_relatorio`, então toda regra do relatório
(fundo de reserva, despesas, opções) vale igual nos dois formatos.
Os gráficos entram como imagem PNG (desenhados com Pillow).
"""
import io
import math

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

from relatorio_pdf import montar_contexto_relatorio

AZUL = RGBColor(0x1C, 0x35, 0x5E)
CINZA = RGBColor(0x52, 0x51, 0x4E)
FONTE = 'Arial'
STATUS_TXT = {'superavit': 'Superávit', 'superavit_insuficiente': 'Superávit insuficiente',
              'deficit': 'Déficit'}
STATUS_COR = {'superavit': RGBColor(0x0F, 0x6B, 0x2B),
              'superavit_insuficiente': RGBColor(0x8A, 0x63, 0x00),
              'deficit': RGBColor(0xA1, 0x26, 0x26)}


def _fonte_img(tamanho):
    for caminho in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/System/Library/Fonts/Supplemental/Arial.ttf'):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanho)


def _hex(cor):
    cor = cor.lstrip('#')
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def _png_pizza(fatias, lado=600):
    img = Image.new('RGB', (lado, lado), 'white')
    d = ImageDraw.Draw(img)
    caixa = (20, 20, lado - 20, lado - 20)
    ini = -90.0
    for f in fatias:
        fim = ini + f['frac'] * 360
        d.pieslice(caixa, ini, fim, fill=_hex(f['cor']), outline='white', width=4)
        ini = fim
    fonte = _fonte_img(36)
    centro, raio = lado / 2, (lado - 40) / 2 * 0.66
    ini = -90.0
    for f in fatias:
        fim = ini + f['frac'] * 360
        if f['frac'] >= 0.08:
            meio = math.radians((ini + fim) / 2)
            d.text((centro + raio * math.cos(meio), centro + raio * math.sin(meio)),
                   f'{round(f["frac"] * 100)}%', font=fonte, fill=(20, 17, 12), anchor='mm')
        ini = fim
    return _png_bytes(img)


def _png_mensal(fluxo, largura=1600, altura=460):
    img = Image.new('RGB', (largura, altura), 'white')
    d = ImageDraw.Draw(img)
    topo, base = 20, altura - 50
    maximo = max((max(m.get('receita') or 0, m.get('despesa') or 0) for m in fluxo), default=1) or 1
    col = largura / len(fluxo)
    fonte = _fonte_img(26)
    for i, m in enumerate(fluxo):
        x0 = i * col
        bw = col * 0.32
        for desloc, chave, cor in ((0.14, 'receita', (0x1C, 0x35, 0x5E)),
                                   (0.54, 'despesa', (0xC3, 0xC2, 0xB7))):
            h = max(6, (m.get(chave) or 0) / maximo * (base - topo))
            x = x0 + col * desloc
            d.rounded_rectangle((x, base - h, x + bw, base), radius=3, fill=cor)
        d.text((x0 + col / 2, base + 24), str(m.get('mes') or ''), font=fonte,
               fill=(0x52, 0x51, 0x4E), anchor='mm')
    return _png_bytes(img)


def _png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def _sombrear(celula, hex_cor):
    pr = celula._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_cor)
    pr.append(shd)


def _bordas(celula, topo=None):
    pr = celula._tc.get_or_add_tcPr()
    b = OxmlElement('w:tcBorders')
    for lado in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{lado}')
        if lado == 'bottom':
            el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), '4'); el.set(qn('w:color'), 'E1E0D9')
        elif lado == 'top' and topo:
            el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(topo)); el.set(qn('w:color'), '14110C')
        else:
            el.set(qn('w:val'), 'nil')
        b.append(el)
    pr.append(b)


def _texto(par, txt, negrito=False, tamanho=10, cor=None):
    run = par.add_run(txt)
    run.bold = negrito
    run.font.size = Pt(tamanho)
    run.font.name = FONTE
    if cor is not None:
        run.font.color.rgb = cor
    return run


def _titulo(doc, txt):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    _texto(p, txt, True, 13, AZUL)
    pPr = p._p.get_or_add_pPr()
    borda = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '4'); b.set(qn('w:color'), 'E1E0D9')
    borda.append(b)
    pPr.append(borda)


def _tabela_valores(doc, cab, linhas, destaques=()):
    """linhas = [(label, valor)]; destaques = {indice: 'total'|'subtotal'}."""
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    larguras = (Cm(12.4), Cm(4.6))
    for i, txt in enumerate(cab):
        c = t.rows[0].cells[i]
        c.width = larguras[i]
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if i else WD_ALIGN_PARAGRAPH.LEFT
        _texto(p, txt, True, 10, CINZA)
        _bordas(c)
    for idx, (label, valor) in enumerate(linhas):
        tipo = dict(destaques).get(idx)
        cels = t.add_row().cells
        for i, txt in enumerate((label, valor)):
            cels[i].width = larguras[i]
            p = cels[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if i else WD_ALIGN_PARAGRAPH.LEFT
            _texto(p, txt, tipo is not None, 10, CINZA if tipo == 'subtotal' else None)
            _bordas(cels[i], topo=12 if tipo == 'total' else 6 if tipo == 'subtotal' else None)
    return t


def gerar_relatorio_docx(estado, logo_path=None, com_fundo_override=None):
    ctx = montar_contexto_relatorio(estado, logo_path, com_fundo_override)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(1.8)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(1.8)
    estilo = doc.styles['Normal']
    estilo.font.name = FONTE
    estilo.font.size = Pt(10)
    estilo.paragraph_format.space_after = Pt(0)

    # Rodapé: Página X de Y
    rodape = sec.footer.paragraphs[0]
    rodape.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for pedaco in ('Página ', 'PAGE', ' de ', 'NUMPAGES'):
        if pedaco.isupper():
            run = rodape.add_run()
            run.font.size = Pt(9)
            for tipo, txt in (('begin', None), (None, pedaco), ('end', None)):
                if tipo:
                    el = OxmlElement('w:fldChar'); el.set(qn('w:fldCharType'), tipo)
                else:
                    el = OxmlElement('w:instrText'); el.set(qn('xml:space'), 'preserve'); el.text = txt
                run._r.append(el)
        else:
            _texto(rodape, pedaco, False, 9, CINZA)

    # Cabeçalho: logo + título
    cab = doc.add_table(rows=1, cols=2)
    cab.autofit = False
    c_logo, c_tit = cab.rows[0].cells
    c_logo.width, c_tit.width = Cm(4), Cm(13)
    if logo_path:
        try:
            c_logo.paragraphs[0].add_run().add_picture(logo_path, height=Cm(1.8))
        except Exception:
            pass
    p = c_tit.paragraphs[0]
    _texto(p, f'{ctx["nome_condominio"]} — {ctx["ano_previsao"]}', True, 18, AZUL)
    p2 = c_tit.add_paragraph()
    _texto(p2, f'Previsão orçamentária · {ctx["data_extenso"]}', False, 11, CINZA)

    _titulo(doc, 'Receitas')
    _tabela_valores(doc, ('Conta', 'Valor mensal previsto'),
                    list(ctx['receitas']) + [('Total mensal', ctx['total_receitas'])],
                    {len(ctx['receitas']): 'total'})

    _titulo(doc, 'Despesas')
    desp = list(ctx['despesas'])
    n = len(desp)
    desp += [('SUBTOTAL', ctx['subtotal_mensal']),
             (f'Aumento Previsto (Salários, tarifas, serviços) = {ctx["inflacao_pct"]}% sobre o SUBTOTAL',
              ctx['aumento_mensal']),
             ('TOTAL PREVISTO', ctx['total_despesas'])]
    _tabela_valores(doc, ('Conta', 'Valor mensal previsto'), desp, {n: 'subtotal', n + 2: 'total'})

    _titulo(doc, 'Quadro de leitura')
    for o in ctx['opcoes']:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.keep_with_next = True
        _texto(p, o['label'], True, 11, AZUL)
        t = _tabela_valores(doc, ('Item', 'Valor'), [
            ('Receita mensal', o['receita_mensal']),
            ('Despesa mensal', o['despesa_mensal']),
            ('Resultado mensal', o['resultado_mensal']),
            ('Reajuste necessário', o['reajuste']),
        ])
        c = t.add_row().cells
        c[0].merge(c[1])
        _texto(c[0].paragraphs[0], STATUS_TXT[o['status']], True, 10, STATUS_COR[o['status']])

    pizza = ctx.get('pizza')
    if pizza:
        _titulo(doc, 'Composição das despesas')
        t = doc.add_table(rows=1, cols=2)
        t.autofit = False
        a, b = t.rows[0].cells
        a.width, b.width = Cm(6.5), Cm(10.5)
        a.paragraphs[0].add_run().add_picture(_png_pizza(pizza['fatias']), width=Cm(5.8))
        primeiro = True
        for f in pizza['fatias']:
            par = b.paragraphs[0] if primeiro else b.add_paragraph()
            primeiro = False
            par.paragraph_format.space_after = Pt(4)
            _texto(par, '■ ', True, 11, RGBColor(*_hex(f['cor'])))
            _texto(par, f'{f["label"]} — {f["frac"] * 100:.1f}%'.replace('.', ','), False, 10)

    if ctx.get('grafico_mensal') and ctx.get('fluxo_mensal'):
        _titulo(doc, 'Evolução mensal')
        doc.add_paragraph().add_run().add_picture(_png_mensal(ctx['fluxo_mensal']), width=Cm(17))
        p = doc.add_paragraph()
        _texto(p, '■ ', True, 10, AZUL); _texto(p, 'Receita atual   ', False, 9, CINZA)
        _texto(p, '■ ', True, 10, RGBColor(0xC3, 0xC2, 0xB7)); _texto(p, 'Despesa', False, 9, CINZA)
        if ctx['grafico_mensal'].get('pior_mes_txt'):
            _texto(p, '    ' + ctx['grafico_mensal']['pior_mes_txt'], True, 9)

    _titulo(doc, 'Conclusão')
    p = doc.add_paragraph()
    _texto(p, ctx['status_label'], True, 10, STATUS_COR[ctx['status_geral']])
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    _texto(p, ctx['conclusao_texto'], False, 10)

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    _texto(p, 'CONSIDERAÇÕES IMPORTANTES', True, 13, AZUL)
    for texto in ctx['consideracoes']:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        _texto(p, texto, False, 10)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    _texto(p, f'Cabo Frio, {ctx["data_extenso"]}', False, 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _texto(p, 'PORTO REAL IMÓVEIS', True, 10.5)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
