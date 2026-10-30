# -*- coding: utf-8 -*-
"""
publish_draft.py — 把生成的文章推送到微信公众号【草稿箱】（不群发，人工核验后自行发布）
用法:
    python publish_draft.py                          # 默认发布 output/article + output/report
    python publish_draft.py --article output/article/article.md
    python publish_draft.py --title "自定义标题" --digest "自定义摘要"

前置条件:
    1. assets/mp_config.json 填入 appid 和 secret（公众号后台-设置与开发-基本配置）
    2. 本机公网 IP 已加入公众号后台的 IP 白名单
    3. 公众号需为已认证账号（未认证订阅号无草稿/素材 API 权限）
"""
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MP_CFG = os.path.join(BASE, 'assets', 'mp_config.json')
TOKEN_CACHE = os.path.join(BASE, '.mp_token.json')


# ---------- HTTP 基础 ----------

def http_json(url, data=None, method='GET'):
    req = urllib.request.Request(
        url, data=json.dumps(data, ensure_ascii=False).encode('utf-8')
        if data is not None else None, method=method)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def upload_multipart(url, filepath, field='media'):
    """multipart/form-data 上传文件，返回 json"""
    boundary = '----%s' % uuid.uuid4().hex
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as f:
        content = f.read()
    body = bytearray()
    body += ('--%s\r\nContent-Disposition: form-data; name="%s"; '
             'filename="%s"\r\nContent-Type: application/octet-stream\r\n\r\n'
             % (boundary, field, filename)).encode('utf-8')
    body += content
    body += ('\r\n--%s--\r\n' % boundary).encode('utf-8')
    req = urllib.request.Request(url, data=bytes(body), method='POST')
    req.add_header('Content-Type',
                   'multipart/form-data; boundary=%s' % boundary)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_token(appid, secret, force=False):
    if not force and os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        if cache.get('expires_at', 0) > time.time() + 120:
            return cache['token']
    url = ('https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential'
           '&appid=%s&secret=%s' % (urllib.parse.quote(appid),
                                    urllib.parse.quote(secret)))
    r = http_json(url)
    if 'access_token' not in r:
        raise RuntimeError('获取 access_token 失败: %s %s\n'
                           '（40001/40125=AppSecret错误；40164=本机IP未加白名单，'
                           '去公众号后台"基本配置-IP白名单"添加）' % (
                               r.get('errcode'), r.get('errmsg')))
    with open(TOKEN_CACHE, 'w', encoding='utf-8') as f:
        json.dump({'token': r['access_token'],
                   'expires_at': time.time() + r.get('expires_in', 7200)}, f)
    return r['access_token']


# ---------- 文章组装 ----------

def load_article(article_path):
    """从 article.md 拆出：标题 / 文案段落数组 / 图片路径数组"""
    with open(article_path, 'r', encoding='utf-8') as f:
        md = f.read()
    lines = md.split('\n')
    title = ''
    paras = []
    images = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith('# ') and not title:
            title = s[2:].strip()
            continue
        m = re.match(r'!\[(.*?)\]\((.*?)\)\s*$', s)
        if m:
            p = os.path.normpath(os.path.join(os.path.dirname(article_path),
                                              m.group(2)))
            images.append(p)
        elif s == '---':
            continue
        elif s.startswith('*') and s.endswith('*') and not s.startswith('**'):
            continue  # 页脚元信息行
        else:
            paras.append(s)
    return title, paras, images


def md_inline(s):
    """极简 markdown 行内转换（加粗）"""
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)


def build_content(paras, img_urls):
    p_style = ('style="margin:0 0 20px;font-size:16px;line-height:1.9;'
               'color:#333;text-align:justify;letter-spacing:.5px;"')
    html = []
    for p in paras:
        t = md_inline(p)
        if t.startswith('<strong>'):
            html.append('<p %s>%s</p>' % (p_style, t))
        else:
            html.append('<p %s>%s</p>' % (p_style, t))
    # article.md 自带「阅读报告全文」引导行（md_inline 已转 <strong>），不再重复追加
    for u in img_urls:
        html.append('<p style="margin:8px 0;"><img src="%s" '
                    'style="width:100%%;display:block;"></p>' % u)
    return ''.join(html)


def slim_image(path):
    """微信上传图片限 10MB，超限转 JPG 压缩"""
    if os.path.getsize(path) <= 9 * 1024 * 1024:
        return path
    from PIL import Image
    out = os.path.splitext(path)[0] + '_slim.jpg'
    Image.open(path).convert('RGB').save(out, quality=82)
    print('  [压缩] %s -> %s (%.1fMB)' % (
        os.path.basename(path), os.path.basename(out),
        os.path.getsize(out) / 1048576))
    return out


# ---------- 分享卡片封面 ----------

CARD_COLORS = {
    'bg_top': (15, 33, 103),    # 深海军蓝
    'bg_bottom': (30, 58, 138), # 亮一档
    'orange': (249, 115, 22),   # 点缀橙
    'white': (255, 255, 255),
    'grey': (203, 213, 225),
}


def theme_colors(name):
    """按 assets/themes.json 取卡片封面配色（bg=封面渐变两端，点缀=accent）"""
    import json as _json
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'assets', 'themes.json')
    with open(path, 'r', encoding='utf-8') as f:
        themes = _json.load(f)
    if name not in themes or name.startswith('_'):
        raise RuntimeError('未知主题 %s：%s' % (
            name, '、'.join(k for k in themes if not k.startswith('_'))))
    t = themes[name]
    rgb = lambda h: tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    return {
        'bg_top': rgb(t['cover1']), 'bg_bottom': rgb(t['cover3']),
        'orange': rgb(t['accent']),
        'white': (255, 255, 255), 'grey': (203, 213, 225),
    }


def _font(size, bold=True):
    from PIL import ImageFont
    candidates = [
        os.environ.get('WECHAT_REPORT_FONT'),
        'C:\\Windows\\Fonts\\msyhbd.ttc' if bold else 'C:\\Windows\\Fonts\\msyh.ttc',
        'C:\\Windows\\Fonts\\msyh.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc' if bold else
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return ImageFont.truetype(path, size)
    raise RuntimeError('未找到中文字体；请设置 WECHAT_REPORT_FONT')


def make_card_cover(title, lead_para, brand_org, out_path, size=900,
                    theme='zhengwu'):
    """合成 900x900 正方形分享卡片封面。

    微信卡片缩略图取封面居中正方形裁剪，长图封面会被裁出奇怪区域；
    这里专门合成一张：主题色渐变底 + 报告名 + 三个关键数 + 落款，
    居中正方形裁剪与整图一致，卡片/后台封面两用。
    """
    from PIL import Image, ImageDraw
    CARD_COLORS = theme_colors(theme)
    W = size
    top, bot = CARD_COLORS['bg_top'], CARD_COLORS['bg_bottom']
    im = Image.new('RGB', (W, W), top)
    d = ImageDraw.Draw(im)
    for y in range(W):  # 垂直渐变
        t = y / (W - 1)
        d.line([(0, y), (W, y)], fill=tuple(
            int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

    def center(text, y, font, fill):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)

    # 报告名：去掉栏目前缀、书名号和"发布"后缀，按实际字宽折行（最多两行）
    center('产业观察', int(W * 0.11), _font(34), CARD_COLORS['orange'])
    d.line([(W * 0.36, int(W * 0.18)), (W * 0.64, int(W * 0.18))],
           fill=CARD_COLORS['orange'], width=4)
    name = title.split('|', 1)[-1].replace('《', '').replace('》', '').strip()
    if name.endswith('发布'):
        name = name[:-2]
    f_title = _font(64)

    def wrap_name(s, font):
        lines, cur = [], ''
        for ch in s:
            if d.textlength(cur + ch, font=font) > W - 140:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
        return lines

    lines = wrap_name(name, f_title)
    while len(lines) > 2:  # 放不下就缩字号
        f_title = _font(f_title.size - 6)
        lines = wrap_name(name, f_title)
    line_h = int(f_title.size * 1.42)
    ys = [int(W * 0.30)] if len(lines) == 1 else [
        int(W * 0.26), int(W * 0.26) + line_h]
    for ln, yy in zip(lines, ys):
        center(ln, yy, f_title, CARD_COLORS['white'])

    # 关键数字（从导语第一段提取，兼容"2392条"与"1.43万条"两种写法）
    import re as _re
    stats = []
    m = _re.search(r'([\d.]+万?)条在招岗位[、，]([\d.]+万?)家招聘企业[、，]'
                   r'([\d.]+万?)座城市', lead_para)
    if m:
        stats = [(m.group(1), '在招岗位'), (m.group(2), '招聘企业'),
                 (m.group(3), '覆盖城市')]
    f_num = _font(58)
    f_lab = _font(26)
    if stats:
        y0 = int(W * 0.585)
        seg = W // 3
        for i, (num, lab) in enumerate(stats):
            wn = d.textlength(num, font=f_num)
            wl = d.textlength(lab, font=f_lab)
            cx = seg * i + seg / 2
            fill = CARD_COLORS['orange'] if i == 0 else CARD_COLORS['white']
            d.text((cx - wn / 2, y0), num, font=f_num, fill=fill)
            d.text((cx - wl / 2, y0 + 72), lab, font=f_lab,
                   fill=CARD_COLORS['grey'])
        d.line([(W * 0.30, int(W * 0.52)), (W * 0.70, int(W * 0.52))],
               fill=(80, 110, 190), width=2)

    center('数据来源：优才知路平台数据库 · ' + brand_org, int(W * 0.90),
           _font(24), CARD_COLORS['grey'])
    im.save(out_path)
    print('  [卡片封面] %s (%dx%d)' % (os.path.basename(out_path), W, W))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--article', default=os.path.join(BASE, 'output', 'article',
                                                      'article.md'))
    ap.add_argument('--title', default=None, help='覆盖标题（<=32字）')
    ap.add_argument('--digest', default=None, help='覆盖摘要（<=120字）')
    ap.add_argument('--author', default=None)
    ap.add_argument('--theme', default='zhengwu',
                    help='卡片封面配色主题（assets/themes.json），'
                         '与 render_report.py --theme 保持一致')
    args = ap.parse_args()

    if not os.path.exists(MP_CFG):
        print('缺少 %s。请复制 mp_config.example.json 为 mp_config.json '
              '并填入 appid/secret。' % MP_CFG)
        sys_exit(1)
    with open(MP_CFG, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    with open(os.path.join(BASE, 'assets', 'brand.json'), 'r', encoding='utf-8') as f:
        brand = json.load(f)

    title, paras, images = load_article(args.article)
    title = args.title or title
    author = args.author or brand.get('org', '')
    digest = args.digest
    if not digest:
        # 摘要优先取导语段（分点信号之前的段落），没有再退回第一条分点
        lead = next((p for p in paras if not re.match(r'\d+[.、]', p)), '')
        seg = lead or next((p for p in paras if p.startswith('1.')),
                           paras[0] if paras else '')
        digest = re.sub(r'\*\*', '', seg)[:110]
    if len(title.encode('utf-8')) > 64:
        print('标题超 64 字节（当前 %d 字节，微信按UTF-8字节计，一个汉字3字节），'
              '请用 --title 指定短标题' % len(title.encode('utf-8')))
        sys_exit(1)

    def cut_bytes(s, n):
        while len(s.encode('utf-8')) > n:
            s = s[:-1]
        for stop in '。；！？，、':  # 在标点处收尾，避免半句话
            i = s.rfind(stop)
            if i >= 8:
                return s[:i + 1]
        return s
    digest = cut_bytes(digest, 120)

    token = get_token(cfg['appid'], cfg['secret'])

    # 1. 正文图片逐张上传（uploadimg 返回的 url 才能放进 content）
    print('上传正文图片 %d 张...' % len(images))
    img_urls = []
    for p in images:
        p2 = slim_image(p)
        r = upload_multipart(
            'https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=%s'
            % token, p2)
        if 'url' not in r:
            raise RuntimeError('图片上传失败 %s: %s %s' % (
                os.path.basename(p), r.get('errcode'), r.get('errmsg')))
        img_urls.append(r['url'])
        print('  [ok] %s' % os.path.basename(p))

    # 2. 封面：合成 900x900 分享卡片封面（微信卡片取居中正方形裁剪，
    #    长图封面会被裁出奇怪区域），上传为永久素材拿 media_id
    if not paras:
        print('文章没有正文段落')
        sys_exit(1)
    print('合成分享卡片封面...')
    cover = make_card_cover(title, paras[0], brand.get('org', ''),
                            os.path.join(BASE, 'output', 'article',
                                         'card_cover.png'),
                            theme=args.theme)
    print('上传封面...')
    r = upload_multipart(
        'https://api.weixin.qq.com/cgi-bin/material/add_material'
        '?access_token=%s&type=image' % token, cover)
    if 'media_id' not in r:
        raise RuntimeError('封面上传失败: %s %s' % (
            r.get('errcode'), r.get('errmsg')))
    thumb_media_id = r['media_id']

    # 3. 新增草稿
    content = build_content(paras, img_urls)
    print('正文 HTML %d 字符（限 2 万）...' % len(content))
    body = {
        'articles': [{
            'title': title,
            'author': author[:16],
            'digest': digest[:120],
            'content': content,
            'content_source_url': '',
            'thumb_media_id': thumb_media_id,
            'need_open_comment': 0,
            'only_fans_can_comment': 0,
        }]
    }
    r = http_json('https://api.weixin.qq.com/cgi-bin/draft/add?access_token=%s'
                  % token, body, 'POST')
    if r.get('errcode') == 40001 or r.get('errcode') == 42001:
        print('token 过期，刷新重试...')
        token = get_token(cfg['appid'], cfg['secret'], force=True)
        r = http_json('https://api.weixin.qq.com/cgi-bin/draft/add'
                      '?access_token=%s' % token, body, 'POST')
    if r.get('errcode') == 45110:
        print('author 超限（微信按字节计），去掉作者字段重试...')
        body['articles'][0]['author'] = ''
        r = http_json('https://api.weixin.qq.com/cgi-bin/draft/add'
                      '?access_token=%s' % token, body, 'POST')
    if 'media_id' not in r:
        raise RuntimeError('新增草稿失败: %s %s\n'
                           '（40164=IP未加白名单；45009=达到调用频率限制；'
                           '48001=api功能未授权/未认证）' % (
                               r.get('errcode'), r.get('errmsg')))

    print('\n✅ 已存入公众号草稿箱（未群发，需人工核验）')
    print('   草稿 media_id: %s' % r['media_id'])
    print('   标题: %s' % title)
    print('   摘要: %s' % digest[:60])
    print('   下一步: 登录 mp.weixin.qq.com -> 草稿箱 核验排版后手动发布')


def sys_exit(code):
    raise SystemExit(code)


if __name__ == '__main__':
    main()
