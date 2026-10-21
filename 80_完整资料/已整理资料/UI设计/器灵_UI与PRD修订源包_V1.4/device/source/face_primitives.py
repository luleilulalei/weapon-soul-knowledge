from html import escape
import math
C = {'bg': '#0B1020', 'white': '#F4F3ED', 'cyan': '#72E5DB', 'gold': '#E7BD79', 'muted': '#93A7B5', 'panel': '#111A2C'}

def text(x, y, txt, size=16, fill=None, weight=400, anchor='middle', extra=''):
    return f'''<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Noto Sans CJK SC, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill or C['white']}" {extra}>{escape(txt)}</text>'''
DEFS = '<defs>\n<radialGradient id="screen" cx="50%" cy="44%" r="68%"><stop stop-color="#15243A"/><stop offset=".64" stop-color="#0B1020"/><stop offset="1" stop-color="#050812"/></radialGradient>\n<linearGradient id="iris" x1="0" y1="0" x2=".3" y2="1"><stop stop-color="#D9FFF7"/><stop offset=".5" stop-color="#72E5DB"/><stop offset="1" stop-color="#279DAB"/></linearGradient>\n<linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#72E5DB" stop-opacity=".95"/><stop offset=".5" stop-color="#72E5DB" stop-opacity=".1"/><stop offset="1" stop-color="#E7BD79" stop-opacity=".6"/></linearGradient>\n<radialGradient id="aura"><stop stop-color="#72E5DB" stop-opacity=".16"/><stop offset="1" stop-color="#E7BD79" stop-opacity="0"/></radialGradient>\n<filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="4"/></filter>\n<clipPath id="round"><circle cx="120" cy="120" r="119"/></clipPath>\n</defs>'

def icon(name, x, y, size=18, color=None):
    color = color or C['cyan']
    a = f'<g transform="translate({x},{y}) scale({size / 24})" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    b = '</g>'
    v = {'mic': '<rect x="8" y="3" width="8" height="12" rx="4"/><path d="M5 11v2a7 7 0 0 0 14 0v-2M12 20v3M8 23h8"/>', 'micoff': '<path d="M8 6v5M16 12V7a4 4 0 0 0-7-3M5 11v2a7 7 0 0 0 10 6M19 13v-2M12 20v3M8 23h8M3 3l18 18"/>', 'offline': '<path d="M3 8q9-8 18 0M6 12q6-5 12 0M10 16q2-2 4 0M12 20h.01M3 3l18 18"/>', 'online': '<path d="M3 8q9-8 18 0M6 12q6-5 12 0M10 16q2-2 4 0M12 20h.01"/>', 'charge': '<path d="M14 2L5 14h7l-2 8 9-12h-7z"/>', 'nocharge': '<path d="M14 2L5 14h7l-2 8 9-12h-7M3 3l18 18"/>', 'battery': '<rect x="2" y="6" width="18" height="12" rx="3"/><path d="M22 10v4M5 9v6"/>', 'warning': '<path d="M12 3L1 21h22zM12 9v5M12 18h.01"/>', 'check': '<path d="M5 12l5 5L20 6"/>', 'memory': '<path d="M5 3h14v18l-7-4-7 4z"/>', 'retry': '<path d="M4 7A9 9 0 1 1 3 15M3 3v6h6"/>', 'dock': '<path d="M5 16v5h14v-5M9 3h6v12H9zM12 17v-2"/>', 'blade': '<path d="M15 2l5 1-1 5-8 8-4-4zM4 10l10 10M8 16l-4 4M2 18l4 4"/>', 'power': '<path d="M12 2v10M6 5a9 9 0 1 0 12 0"/>'}
    return a + v.get(name, '') + b

def eyes(mood):
    if mood == 'none':
        return ''
    if mood == 'sleep':
        return '<g fill="none" stroke="#72E5DB" stroke-width="6" stroke-linecap="round"><path d="M53 116Q79 127 104 116"/><path d="M136 116Q161 127 187 116"/></g><path d="M113 144q7 5 14 0" stroke="#72E5DB" stroke-opacity=".5" fill="none"/>'
    path = 'M54 103C56 83 69 77 86 82C102 86 110 99 108 116C106 134 95 142 79 140C61 138 51 123 54 103Z'
    if mood == 'happy':
        path = 'M53 115C57 92 69 86 83 86C97 86 106 95 110 116C96 106 93 100 82 100C70 100 62 107 53 115Z'
    if mood == 'focus':
        path = 'M53 99L109 112C107 132 94 141 79 138C62 135 54 124 53 99Z'
    if mood == 'concern':
        path = 'M54 109C57 94 73 86 106 86L107 115C106 132 93 139 79 136C62 133 53 126 54 109Z'
    if mood == 'drowsy':
        path = 'M53 111Q80 117 108 107C106 129 96 137 80 136C63 134 56 127 53 111Z'
    if mood == 'soft':
        path = 'M53 106C58 87 74 83 88 88C101 92 108 101 109 116C105 130 95 138 80 135C63 132 55 123 53 106Z'
    out = '<ellipse cx="120" cy="114" rx="95" ry="70" fill="url(#aura)"/>'
    gaze = {'think': (-4, -7), 'curious': (3, -4), 'listen': (6, 0), 'awake': (0, -3), 'calm': (-4, 2)}.get(mood, (0, 0))
    for side in range(2):
        tx = '' if side == 0 else 'translate(240 0) scale(-1 1)'
        out += f'<g transform="{tx}"><path d="{path}" fill="#72E5DB" opacity=".28" filter="url(#glow)"/><path d="{path}" fill="url(#iris)"/>'
        if mood not in ('happy',):
            px = 84 + gaze[0] * (1 if side == 0 else -1)
            py = 111 + gaze[1]
            if mood == 'focus':
                py = 122
            if mood == 'drowsy':
                py = 125
            out += f'<ellipse cx="{px}" cy="{py}" rx="11" ry="17" fill="#1E2630"/><ellipse cx="{px - 3}" cy="{py - 5}" rx="3.4" ry="6" fill="#F4F3ED"/><path d="M65 129Q80 139 95 130" stroke="#72E5DB" stroke-width="2.2" opacity=".9" fill="none"/>'
        out += '</g>'
    if mood == 'happy':
        out += '<path d="M49 78l2-5 2 5 5 2-5 2-2 5-2-5-5-2z" fill="#E7BD79"/><circle cx="190" cy="136" r="2" fill="#E7BD79"/>'
    if mood == 'curious':
        out += '<path d="M56 72q20-10 40-2" stroke="#E7BD79" opacity=".55" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
    out += '<path d="M120 149l3 4-3 4-3-4z" fill="#72E5DB" opacity=".65"/>'
    return out
MIC = {'wake': ('mic', '待唤醒采音'), 'input': ('mic', '会话采音中'), 'local': ('mic', '本地指令采音'), 'off': ('micoff', '麦克风关闭'), 'unknown': ('mic', '采音未确认'), 'sleep': ('micoff', '深眠不采音'), 'blocked': ('micoff', '采音已停止')}

