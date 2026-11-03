"""Visible report prose shared by internal articles and the official draft bridge."""
import html


def prose_blocks(report):
    chapter_keys={row['key'] for row in report.get('analysis',{}).get('sections',[])}
    yield 'title',report['title']
    for screen in report['screens'][1:]:
        yield 'heading',screen['title']
        for paragraph in screen.get('paragraphs',[]):
            if screen.get('analysis_key') in chapter_keys and paragraph.startswith('行动建议：'):continue
            yield 'paragraph',paragraph
        if screen.get('summary'):yield 'paragraph',screen['summary']['text']
        for title,text in screen.get('blocks',[]):
            yield 'subheading',title
            yield 'paragraph',text


def html_prose(report):
    tags={'title':'h1','heading':'h2','subheading':'h3','paragraph':'p'}
    return '<section style="font-size:16px;line-height:1.9;color:#263248;overflow-wrap:anywhere">'+''.join(
        '<'+tags[kind]+'>'+html.escape(text)+'</'+tags[kind]+'>' for kind,text in prose_blocks(report))+'</section>'
