"""Direct bindings for a local, explicit-Part MIDI scale reader.

Readers preserve every register except d0. read_at takes d0=track 0..7 and
d1=context: 0..63 working bank*4+Part, 64..127 saved bank*4+Part. It never
resolves a Follow route or reads the selected UI track. Its result is OFF=0,
or mask[11:0] | tonic[15:12] | native-snap[16]. A failed read is -1.
Native snapping is only legal for Major/natural Minor; other masks use
nearest playable MIDI pitch, lower on ties. No provider owns MIDI output.

The common quant/legacy callbacks preserve all registers except d0. quant
takes d0=pitch,d1=descriptor. legacy takes d0=descriptor and returns the old
tonic<<2 | mode<<6 identity, OFF=-1, unsupported/invalid=-2. Harmony's saved
format can represent only the seven exact diatonic masks. The consumer rejects unsupported masks at edit and playback boundaries,
without changing stored degree intent. masks=None declares an open catalogue.

An adapter's owns_key_ui promise includes Follow's inherited, read-only KEY
and Harmony's ownership of generated pitches. New storage, hooks and Part
lifecycle must be qualified by the adapter before registering it here.
This uses existing Linked/include selection only: no runtime registration.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
DIATONIC_MASKS = frozenset((0xab5, 0x6ad, 0x5ab, 0xad5, 0x6b5, 0x5ad, 0x56b))
STOCK = dict(key=None, reader='msp_key_read', source=ROOT / 'scale_key.s',
             owns_key_ui=False, masks=frozenset((0xab5, 0x5ad)),
             include='.set SCALE_KEY_EXTENDED,0\n')
PROVIDERS = (
    dict(key='MIDI SCALES', reader='msp_key_read', source=ROOT / 'scale_key.s',
         owns_key_ui=True, masks=DIATONIC_MASKS,
         include='.set SCALE_KEY_EXTENDED,1\n'),
    dict(key='SCALES', reader='msp_scales_read', source=ROOT / 'scale_scales.s',
         owns_key_ui=True, masks=None, include=''),
)


def scale_provider(modules):
    keys, selected = set(), []
    for provider in PROVIDERS:
        key = provider['key']
        masks = provider['masks']
        if (not key or key in keys or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',
                                                      provider['reader'])
                or (masks is not None and (not masks or any(
                    type(mask) is not int or mask <= 0 or mask > 0xfff for mask in masks)))):
            raise ValueError(f'invalid MIDI scale adapter: {key!r}')
        keys.add(key)
        if key in modules:
            selected.append(provider)
    if len(selected) > 1:
        raise ValueError('MIDI scale consumers permit only one selected adapter')
    provider = selected[0] if selected else STOCK
    return provider


def scale_inc(modules, remix=None):
    provider = scale_provider(modules)
    unrestricted = provider['masks'] is None or not provider['masks'] <= DIATONIC_MASKS
    out = [f'.set SCALE_OWNS_KEY_UI,{int(provider["owns_key_ui"])}',
           f'.set SCALE_HAS_UNSUPPORTED,{int(unrestricted)}']
    for callback, symbol in (('read', provider['reader']),
                             ('quant', 'msp_quant'), ('legacy', 'msp_legacy')):
        out += [f'.macro scale_{callback}', f'    jsr {symbol}', '.endm']
    return '\n'.join(out) + '\n'


def _reader_inc(modules, remix=None):
    return scale_provider(modules)['include']


def scale_links(modules, owner):
    """Link one reader and one arithmetic unit across Follow/Harmony."""
    provider = scale_provider(modules)
    if owner == 'MIDI HARMONY' and 'MIDI FOLLOW' in modules:
        return ()
    from remix.schema import Linked
    return (Linked('midiscaleprovider', str(provider['source']), dram=True, include=_reader_inc),
            Linked('midiscalemath', str(ROOT / 'scale_math.s'), dram=True))
