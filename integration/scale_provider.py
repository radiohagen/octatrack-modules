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
format can represent only the seven exact diatonic masks. Its adapters must
enforce their declared finite choices, including at load/edit boundaries;
unsupported callbacks are not an alternative Harmony playback mode.

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
)
UNADAPTED = {
    'SCALES': 'SCALES needs a qualified MIDI scale adapter: its setup byte +0x12 '
              'overlaps Harmony CHRD/SIZE and its KEY hooks conflict with Follow; '
              'the current prototype is not compatible with these consumers',
}


def scale_provider(modules):
    keys, selected = set(), []
    for provider in PROVIDERS:
        key = provider['key']
        masks = provider['masks']
        if (not key or key in keys or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',
                                                      provider['reader'])
                or not masks or any(type(mask) is not int or mask <= 0 or mask > 0xfff
                                    for mask in masks)):
            raise ValueError(f'invalid MIDI scale adapter: {key!r}')
        keys.add(key)
        if key in modules:
            selected.append(provider)
    for key, message in UNADAPTED.items():
        if key in modules and key not in keys:
            raise ValueError(message)
    if len(selected) > 1:
        raise ValueError('MIDI scale consumers permit only one selected adapter')
    provider = selected[0] if selected else STOCK
    if 'MIDI HARMONY' in modules and not set(provider['masks']) <= DIATONIC_MASKS:
        raise ValueError('MIDI Harmony preserves its saved format and requires an adapter '
                         'restricted to the seven existing diatonic mode masks')
    return provider


def scale_inc(modules, remix=None):
    provider = scale_provider(modules)
    out = [f'.set SCALE_OWNS_KEY_UI,{int(provider["owns_key_ui"])}']
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
