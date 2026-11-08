"""Builds 'Doom Box.amxd' (Max for Live audio effect) around the generated gen~ code."""
import json, struct, sys

CODE = open(__import__('sys').argv[2] if len(__import__('sys').argv) > 2 else 'dsp.genexpr').read()

boxes, lines = [], []
_id = [0]


def nid():
    _id[0] += 1
    return f'obj-{_id[0]}'


def add(box):
    box.setdefault('id', nid())
    boxes.append({'box': box})
    return box['id']


def wire(a, ao, b, bi):
    lines.append({'patchline': {'source': [a, ao], 'destination': [b, bi]}})


def rgba(h, a=1.0):
    h = h.lstrip('#')
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [a]


INK = '#e9dfc4'
BODY = '#2a2c22'
EDGE = '#121309'
LED_OFF = [0.24, 0.03, 0.02, 1.0]
LED_ON = [1.0, 0.16, 0.08, 1.0]
FONT = 'Ableton Sans Bold'


def panel(rect, color, rounded=0, border=0, bordercolor=None, pres=True, name=None):
    b = {'maxclass': 'panel', 'numinlets': 1, 'numoutlets': 0, 'mode': 0,
         'bgcolor': color, 'bgfillcolor_type': 'color', 'bgfillcolor_color': color,
         'rounded': rounded, 'border': border, 'bordercolor': bordercolor or [0, 0, 0, 0],
         'ignoreclick': 1, 'background': 0,
         'patching_rect': [900 + rect[0], 40 + rect[1], rect[2], rect[3]]}
    if pres:
        b['presentation'] = 1
        b['presentation_rect'] = rect
    if name:
        b['varname'] = name
    return add(b)


def text(rect, s, size=10, color=INK, just=1, font=FONT):
    return add({'maxclass': 'comment', 'text': s, 'numinlets': 1, 'numoutlets': 0,
                'fontname': font, 'fontsize': size, 'textcolor': rgba(color),
                'textjustification': just, 'ignoreclick': 1,
                'patching_rect': [900 + rect[0], 40 + rect[1], rect[2], rect[3]],
                'presentation': 1, 'presentation_rect': rect})


# ---------------------------------------------------------------- audio core
plugin = add({'maxclass': 'newobj', 'text': 'plugin~', 'numinlets': 2, 'numoutlets': 2,
              'outlettype': ['signal', 'signal'], 'patching_rect': [30, 30, 60, 22]})
gen_patcher = {
    'fileversion': 1,
    'appversion': {'major': 8, 'minor': 6, 'revision': 0, 'architecture': 'x64', 'modernui': 1},
    'classnamespace': 'dsp.gen',
    'rect': [80, 80, 900, 600],
    'boxes': [
        {'box': {'id': 'obj-1', 'maxclass': 'newobj', 'text': 'in 1', 'numinlets': 0, 'numoutlets': 1,
                 'outlettype': [''], 'patching_rect': [30, 20, 30, 22]}},
        {'box': {'id': 'obj-2', 'maxclass': 'newobj', 'text': 'in 2', 'numinlets': 0, 'numoutlets': 1,
                 'outlettype': [''], 'patching_rect': [400, 20, 30, 22]}},
        {'box': {'id': 'obj-3', 'maxclass': 'codebox', 'code': CODE, 'numinlets': 2, 'numoutlets': 3,
                 'outlettype': ['', '', ''], 'fontface': 0, 'fontname': '<Monospaced>', 'fontsize': 12.0,
                 'patching_rect': [30, 60, 780, 460]}},
        {'box': {'id': 'obj-4', 'maxclass': 'newobj', 'text': 'out 1', 'numinlets': 1, 'numoutlets': 0,
                 'patching_rect': [30, 540, 37, 22]}},
        {'box': {'id': 'obj-5', 'maxclass': 'newobj', 'text': 'out 2', 'numinlets': 1, 'numoutlets': 0,
                 'patching_rect': [400, 540, 37, 22]}},
        {'box': {'id': 'obj-6', 'maxclass': 'newobj', 'text': 'out 3', 'numinlets': 1, 'numoutlets': 0,
                 'patching_rect': [770, 540, 37, 22]}},
    ],
    'lines': [
        {'patchline': {'source': ['obj-1', 0], 'destination': ['obj-3', 0]}},
        {'patchline': {'source': ['obj-2', 0], 'destination': ['obj-3', 1]}},
        {'patchline': {'source': ['obj-3', 0], 'destination': ['obj-4', 0]}},
        {'patchline': {'source': ['obj-3', 1], 'destination': ['obj-5', 0]}},
        {'patchline': {'source': ['obj-3', 2], 'destination': ['obj-6', 0]}},
    ],
}
gen = add({'maxclass': 'newobj', 'text': 'gen~', 'numinlets': 2, 'numoutlets': 3,
           'outlettype': ['signal', 'signal', 'signal'], 'patching_rect': [30, 330, 200, 22],
           'patcher': gen_patcher})
plugout = add({'maxclass': 'newobj', 'text': 'plugout~', 'numinlets': 2, 'numoutlets': 2,
               'outlettype': ['signal', 'signal'], 'patching_rect': [30, 400, 60, 22]})
wire(plugin, 0, gen, 0)
wire(plugin, 1, gen, 1)
wire(gen, 0, plugout, 0)
wire(gen, 1, plugout, 1)


def to_gen(src, outlet, pname, x, y, scale10=False):
    prev, po = src, outlet
    if scale10:
        d = add({'maxclass': 'newobj', 'text': '/ 10.', 'numinlets': 2, 'numoutlets': 1,
                 'outlettype': ['float'], 'patching_rect': [x, y, 40, 22]})
        wire(prev, po, d, 0)
        prev, po, y = d, 0, y + 30
    p = add({'maxclass': 'newobj', 'text': f'prepend {pname}', 'numinlets': 1, 'numoutlets': 1,
             'outlettype': [''], 'patching_rect': [x, y, 110, 22]})
    wire(prev, po, p, 0)
    wire(p, 0, gen, 0)


# ---------------------------------------------------------------- enclosure
W, H = 404, 169
EX, EY, EW, EH = 18, 3, 368, 162
# jacks (OUT on the left, IN on the right, like a pedal) and DC socket
for jx, lbl in ((2, 'OUT'), (EX + EW, 'IN')):
    panel([jx, 64, 16, 30], rgba('#9a9a94'), rounded=3, border=1, bordercolor=rgba('#4a4a46'))
    panel([jx + 3, 72, 10, 14], rgba('#1a1a18'), rounded=7)
    text([jx - 2, 96, 22, 12], lbl, 7, '#8d8a80')
panel([EX + EW // 2 - 12, 0, 24, 6], rgba('#1a1a18'), rounded=2)
panel([EX, EY, EW, EH], rgba(BODY), rounded=16, border=2, bordercolor=rgba(EDGE))
panel([EX + 5, EY + 5, EW - 10, EH - 10], rgba(BODY), rounded=12, border=1, bordercolor=rgba(INK, 0.18))

# section divider between the DIST side and the BOOST side
DIV = 284
panel([DIV, 16, 1, 136], rgba(INK, 0.28))

# ---------------------------------------------------------------- knobs
def knob(cx, name, short, init, label):
    panel([cx - 19, 15, 38, 38], rgba('#0d0d0b'), rounded=19, border=2, bordercolor=rgba('#3c3d35'))
    d = add({'maxclass': 'live.dial', 'varname': name, 'numinlets': 1, 'numoutlets': 2,
             'outlettype': ['', 'float'], 'parameter_enable': 1,
             'showname': 0, 'shownumber': 0,
             'activedialcolor': rgba(INK), 'dialcolor': rgba(INK, 0.22),
             'needlecolor': rgba(INK), 'activeneedlecolor': rgba(INK),
             'patching_rect': [300 + len(boxes) * 3, 60, 44, 44],
             'presentation': 1, 'presentation_rect': [cx - 22, 12, 44, 44],
             'saved_attribute_attributes': {'valueof': {
                 'parameter_longname': name, 'parameter_shortname': short,
                 'parameter_type': 0, 'parameter_unitstyle': 1,
                 'parameter_mmin': 0.0, 'parameter_mmax': 10.0,
                 'parameter_initial_enable': 1, 'parameter_initial': [init]}}})
    text([cx - 34, 57, 68, 13], label, 9)
    return d


knobs = [
    (64, 'Octave', 'Octave', 5.0, 'OCTAVE', 'octave'),
    (126, 'Distortion', 'Dist', 5.0, 'DISTORTION', 'distortion'),
    (188, 'Filter', 'Filter', 3.0, 'FILTER', 'filter'),
    (250, 'Amps', 'Amps', 6.0, 'AMPS', 'amps'),
    (336, 'Boost', 'Boost', 5.0, 'BOOST', 'boost'),
]
for n, (cx, name, short, init, label, pname) in enumerate(knobs):
    d = knob(cx, name, short, init, label)
    to_gen(d, 0, pname, 300 + n * 125, 120, scale10=True)

# ---------------------------------------------------------------- SW1 clip toggle + D6
text([94, 80, 64, 12], 'CLIP', 8)
tab = add({'maxclass': 'live.tab', 'varname': 'Clip', 'numinlets': 1, 'numoutlets': 3,
           'outlettype': ['', '', 'float'], 'parameter_enable': 1,
           'num_lines_patching': 3, 'num_lines_presentation': 3,
           'fontname': FONT, 'fontsize': 8.0,
           'bgcolor': rgba('#14150f'), 'bgoncolor': rgba(INK),
           'activebgcolor': rgba('#14150f'), 'activebgoncolor': rgba(INK),
           'textcolor': rgba(INK, 0.75), 'textoncolor': rgba('#14150f'),
           'bordercolor': rgba(INK, 0.35), 'focusbordercolor': rgba(INK, 0.35),
           'patching_rect': [950, 260, 40, 50],
           'presentation': 1, 'presentation_rect': [108, 93, 36, 44],
           'saved_attribute_attributes': {'valueof': {
               'parameter_longname': 'Clip', 'parameter_shortname': 'Clip', 'parameter_type': 2,
               'parameter_enum': ['LED', 'OFF', 'SI'], 'parameter_mmax': 2,
               'parameter_initial_enable': 1, 'parameter_initial': [0]}}})
to_gen(tab, 0, 'clipmode', 950, 330)

# D6 (red 3 mm LED in the clipping network) — glows with its current
d6 = panel([149, 97, 8, 8], LED_OFF, rounded=4, border=1, bordercolor=rgba('#0a0a08'), name='d6')
text([142, 106, 22, 10], 'D6', 6, '#8d8a80')
snap = add({'maxclass': 'newobj', 'text': 'snapshot~ 30', 'numinlets': 2, 'numoutlets': 1,
            'outlettype': ['float'], 'patching_rect': [230, 400, 80, 22]})
wire(gen, 2, snap, 0)
trig = add({'maxclass': 'newobj', 'text': 't f f', 'numinlets': 1, 'numoutlets': 2,
            'outlettype': ['float', 'float'], 'patching_rect': [230, 430, 40, 22]})
ex_r = add({'maxclass': 'newobj', 'text': 'expr 0.24 + 0.76*$f1', 'numinlets': 1, 'numoutlets': 1,
            'outlettype': [''], 'patching_rect': [230, 460, 130, 22]})
ex_g = add({'maxclass': 'newobj', 'text': 'expr 0.03 + 0.13*$f1', 'numinlets': 1, 'numoutlets': 1,
            'outlettype': [''], 'patching_rect': [370, 460, 130, 22]})
pk = add({'maxclass': 'newobj', 'text': 'pack 0. 0. 0.03 1.', 'numinlets': 4, 'numoutlets': 1,
          'outlettype': [''], 'patching_rect': [230, 490, 110, 22]})
pp = add({'maxclass': 'newobj', 'text': 'prepend bgfillcolor', 'numinlets': 1, 'numoutlets': 1,
          'outlettype': [''], 'patching_rect': [230, 520, 120, 22]})
wire(snap, 0, trig, 0)
wire(trig, 1, ex_g, 0)
wire(trig, 0, ex_r, 0)
wire(ex_g, 0, pk, 1)
wire(ex_r, 0, pk, 0)
wire(pk, 0, pp, 0)
wire(pp, 0, d6, 0)

# ---------------------------------------------------------------- footswitches + status LEDs
def footswitch(cx, name, init, pname, label, x):
    led = panel([cx - 5, 84, 10, 10], LED_ON if init else LED_OFF, rounded=5, border=1,
                bordercolor=rgba('#0a0a08'), name=f'{pname}_led')
    panel([cx - 21, 108, 42, 42], rgba('#4b4c46'), rounded=21, border=1, bordercolor=rgba('#16160f'))
    panel([cx - 15, 114, 30, 30], rgba('#c9c9c2'), rounded=15, border=2, bordercolor=rgba('#85857d'))
    panel([cx - 9, 120, 18, 18], rgba('#e4e4de'), rounded=9)
    text([cx - 30, 150, 60, 11], label, 7, '#b8af97')
    clear = [0, 0, 0, 0]
    t = add({'maxclass': 'live.text', 'varname': name, 'numinlets': 1, 'numoutlets': 2,
             'outlettype': ['', ''], 'parameter_enable': 1, 'mode': 1,
             'text': '', 'texton': '',
             'bgcolor': clear, 'bgoncolor': clear, 'activebgcolor': clear, 'activebgoncolor': clear,
             'bordercolor': clear, 'focusbordercolor': clear, 'textcolor': clear, 'textoncolor': clear,
             'activetextcolor': clear, 'activetextoncolor': clear,
             'patching_rect': [x, 260, 44, 20],
             'presentation': 1, 'presentation_rect': [cx - 21, 108, 42, 42],
             'saved_attribute_attributes': {'valueof': {
                 'parameter_longname': name, 'parameter_shortname': name, 'parameter_type': 2,
                 'parameter_enum': ['off', 'on'], 'parameter_mmax': 1,
                 'parameter_initial_enable': 1, 'parameter_initial': [init]}}})
    to_gen(t, 0, pname, x, 330)
    sel = add({'maxclass': 'newobj', 'text': 'sel 0 1', 'numinlets': 2, 'numoutlets': 3,
               'outlettype': ['bang', 'bang', ''], 'patching_rect': [x, 380, 50, 22]})
    off = add({'maxclass': 'message', 'text': 'bgfillcolor ' + ' '.join(f'{v:g}' for v in LED_OFF),
               'numinlets': 2, 'numoutlets': 1, 'outlettype': [''], 'patching_rect': [x, 410, 150, 22]})
    on = add({'maxclass': 'message', 'text': 'bgfillcolor ' + ' '.join(f'{v:g}' for v in LED_ON),
              'numinlets': 2, 'numoutlets': 1, 'outlettype': [''], 'patching_rect': [x, 440, 150, 22]})
    wire(t, 0, sel, 0)
    wire(sel, 0, off, 0)
    wire(sel, 1, on, 0)
    wire(off, 0, led, 0)
    wire(on, 0, led, 0)


footswitch(64, 'Dist On', 1, 'dist_on', 'DIST', 1100)
footswitch(336, 'Boost On', 0, 'boost_on', 'BOOST', 1300)

# ---------------------------------------------------------------- graphics / name
text([166, 86, 116, 12], 'THE', 9, '#c9452f')
text([166, 97, 116, 28], 'DOOM', 24, INK)
text([166, 123, 116, 28], 'BOX', 24, INK)

patcher = {'patcher': {
    'fileversion': 1,
    'appversion': {'major': 8, 'minor': 6, 'revision': 0, 'architecture': 'x64', 'modernui': 1},
    'classnamespace': 'box',
    'rect': [60, 100, 1500, 700],
    'openrect': [0, 0, W, H],
    'bglocked': 0, 'openinpresentation': 1,
    'default_fontsize': 10.0, 'default_fontface': 0, 'default_fontname': 'Arial',
    'gridonopen': 1, 'gridsize': [8.0, 8.0], 'gridsnaponopen': 1, 'objectsnaponopen': 1,
    'statusbarvisible': 2, 'toolbarvisible': 1,
    'boxanimatetime': 200, 'enablehscroll': 1, 'enablevscroll': 1,
    'devicewidth': float(W),
    'description': 'Octave-up > LM308 distortion > BS170 MOSFET boost, modelled component-by-component from the schematic.',
    'digest': '', 'tags': '', 'style': '', 'subpatcher_template': '',
    'assistshowspatchername': 0,
    # Max stores boxes front-to-back (first = drawn on top), so reverse our back-to-front build order
    'boxes': boxes[::-1], 'lines': lines,
    'dependency_cache': [], 'latency': 0, 'is_mpe': 0, 'autosave': 0,
}}


def write_amxd(path):
    data = json.dumps(patcher, indent=1, ensure_ascii=False).encode('utf-8') + b'\n\x00'
    blob = (b'ampf' + struct.pack('<I', 4) + b'aaaa' +
            b'meta' + struct.pack('<I', 4) + b'\x00\x00\x00\x00' +
            b'ptch' + struct.pack('<I', len(data)) + data)
    open(path, 'wb').write(blob)


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'Doom Box.amxd'
    write_amxd(out)
    json.dump(patcher, open(out.replace('.amxd', '.maxpat'), 'w'), indent=1, ensure_ascii=False)
    print('wrote', out, len(boxes), 'boxes', len(lines), 'lines')
