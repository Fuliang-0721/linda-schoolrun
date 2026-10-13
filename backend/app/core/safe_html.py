import html
from lxml import etree
from lxml import html as parser

ALLOWED = {"p", "br", "b", "strong", "i", "em", "u", "s", "ul", "ol", "li", "blockquote", "pre", "code", "h1", "h2", "h3", "table", "thead", "tbody", "tr", "th", "td", "span", "div"}

def sanitize_html(value):
    try:
        root = parser.fragment_fromstring(value or "", create_parent="div")
    except (etree.ParserError, ValueError):
        return html.escape(value or "")
    for node in list(root.iterdescendants()):
        if node.tag not in ALLOWED:
            node.drop_tree()
        else:
            node.attrib.clear()
    return (html.escape(root.text or "") + "".join(etree.tostring(child, encoding="unicode", method="html") for child in root))
