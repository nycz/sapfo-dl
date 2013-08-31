#!/usr/bin/env python3

import contextlib
import itertools
import os
import os.path
import re
import urllib.request

from libsyntyche.common import read_json, write_json, read_file, write_file
from libsyntyche.common import local_path, make_sure_config_exists


def expand_url(raw_url):
    """
    Expand an url with bash-like brace expansion.

    url{x,y,} -> urlx, urly and url
    url{1..3} -> url1, url2 and url3
    Negative dot-expressions like {3..1} is not supported.
    """
    dotexp = re.search(r'\{(0*)(\d+)\.\.(\d+)\}', raw_url)
    commaexp = re.search(r'\{(.+?)\}', raw_url)
    if dotexp is None and commaexp is None:
        return [raw_url]
    if dotexp:
        old = dotexp.group(0)
        zpadding, start, end = dotexp.groups()
        if int(start) > int(end):
            raise Exception('Negative dotexpansion not supported')
        new = [str(num).zfill(len(zpadding)+1)
               for num in range(int(start), int(end)+1)]
    elif commaexp:
        old = commaexp.group(0)
        new = commaexp.group(1).split(',')
    return [raw_url.replace(old, n) for n in new]


def sanitize_body(text, url):
    # Convert relative links to uh real ones whatsitcalled
    baseurl = '/'.join(url.split('/')[:-1]) + '/'
    text = re.sub(r'<a href="(?!http://|www)', '<a href="'+baseurl, text, re.IGNORECASE)
    # Kill font shit
    text = re.sub(r'(<font [^>]*?)face=".+?"', r'\1', text, re.IGNORECASE)
    text = re.sub(r'(<font [^>]*?)size=".+?"', r'\1', text, re.IGNORECASE)
    return text


def download_page(url, entries, n, maxn):
    for urlprefix in entries:
        if re.match(urlprefix, url, re.IGNORECASE):
            settings = entries[urlprefix]
            break
    else:
        raise Exception('No matching config entry')
    print('Downloading page {}/{}...'.format(n+1,maxn), end='')
    with contextlib.closing(urllib.request.urlopen(url)) as u:
        page = u.read().decode('utf-8', errors="replace")
    print('...done')
    def find(target):
        return re.search(settings[target], page, re.DOTALL|re.IGNORECASE)
    body = sanitize_body(find('body').group('data'), url)
    author = find('author')
    if 'url' in author.groupdict():
        author_url = settings.get('authorurl formstr', '{}').format(author.group('url'))
    else:
        author_url = '#'
    desc = find('description').group('data') if 'description' in settings else ''
    return {'body': body,
            'title': find('title').group('data'),
            'url': url,
            'author_name': author.group('name'),
            'author_url': author_url,
            'description': desc}


def create_directory(root_path, metadata):
    """ Create directory and a default metadata file """
    default_path = os.path.join(root_path, metadata['title'])
    path = default_path
    counter = itertools.count(2)
    while os.path.exists(path):
        path = default_path + '-' + str(next(counter))
    os.mkdir(path, mode=0o755)
    write_json(os.path.join(path, 'metadata.json'), metadata)
    return path


def save_pages(path, name, pages):
    template = read_file(local_path('pagetemplate.html'))
    for n, page in enumerate(pages):
        controls = gen_controls(name, n, len(pages))
        out = template.format(controls=controls, **page)
        fpath = os.path.join(path, name)
        if len(pages) > 1:
            fpath += ' - Page {:03}'.format(n+1)
        fpath += '.html'
        write_file(fpath, out)


def gen_controls(name, n, pagenum):
    template = '<div class="controls">{}</div>'
    if pagenum == 1:
        return template.format('')
    name += ' - Page {:03}.html'
    insert = ''
    if n > 0:
        insert += '<a href="{}"><-- Prev</a> | '.format(name.format(n))
    insert += '  <strong>Page {}/{}</strong>  '.format(n + 1, pagenum)
    if n < pagenum - 1:
        insert += ' | <a href="{}">Next --></a>'.format(name.format(n + 2))
    return template.format(insert)


def gen_metadata(page, args):
    return {
        'title': args.title if args.title else page['title'],
        'description': args.desc if args.desc else page['description'],
        'tags': re.split(r'\s*,\s*', args.tags) if args.tags else []
    }


def load_settings():
    config_file = os.path.join(os.getenv('HOME'), '.config', 'sapfo-dl', 'settings.json')
    make_sure_config_exists(config_file, local_path('default_settings.json'))
    return read_json(os.path.join(config_file))


def main():
    # Setup cmd argument parsing
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', metavar='TITLE', dest='title', default='',
                        help='set title explicitly')
    parser.add_argument('-d', metavar='DESC', dest='desc', default='',
                        help='set description')
    parser.add_argument('-t', metavar='TAGS', dest='tags', default='',
                        help='set tags')
    parser.add_argument('url', nargs='+')
    args = parser.parse_args()

    # Generate/expand all urls
    urls = [u for raw_url in args.url for u in expand_url(raw_url)]
    settings = load_settings()
    pages = [download_page(url, settings['entries'], n, len(urls))
             for n, url in enumerate(urls)]
    metadata = gen_metadata(pages[0], args)
    dirname = create_directory(settings['default']['path'],
                               metadata)
    save_pages(dirname, metadata['title'], pages)


if __name__ == '__main__':
    main()
