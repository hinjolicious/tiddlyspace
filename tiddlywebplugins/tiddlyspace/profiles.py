"""
Start at the infrastructure for OStatus, including webfinger,
user profiles, etc.
"""

from tiddlyweb.control import filter_tiddlers
from tiddlyweb.store import StoreError, NoUserError
from tiddlyweb.model.collections import Tiddlers
from tiddlyweb.model.tiddler import Tiddler
from tiddlyweb.model.user import User
from tiddlyweb.web.http import HTTP404, HTTP400
from tiddlyweb.web.util import server_base_url, encode_name
from tiddlywebplugins.tiddlyspace.web import determine_host
from tiddlywebplugins.tiddlyspace.spaces import space_uri
from tiddlyweb.serializer import Serializer
from tiddlyweb.wikitext import render_wikitext


HOST_META_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<XRD xmlns="http://docs.oasis-open.org/ns/xri/xrd-1.0" xmlns:hm="http://host-meta.net/xrd/1.0">
<hm:Host xmlns="http://host-meta.net/xrd/1.0">%(host)s</hm:Host>
<Link rel="lrdd" template="%(server_host)s/webfinger?q={uri}">
<Title>Resource Descriptor</Title>
</Link>
</XRD>
"""


WEBFINGER_TEMPLATE = """<?xml version="1.0"?>
<XRD xmlns="http://docs.oasis-open.org/ns/xri/xrd-1.0">
<Subject>acct:%(username)s@%(host)s</Subject>
<Alias>%(server_host)s/profiles/%(username)s</Alias>
<Link rel="http://webfinger.net/rel/profile-page"
      href="%(server_host)s/profiles/%(username)s"
      type="text/html"/>
<Link rel="describedby"
      href="%(server_host)s/profiles/%(username)s"
      type="text/html"/>
<Link rel="http://schemas.google.com/g/2010#updates-from"
      href="%(server_host)s/search.atom?q=modifier:%(username)s"
      type="application/atom+xml"/>
</XRD>
"""

PROFILE_TEMPLATE = """
<div class="tiddler">
<img style="float:right" src="%(server_host)s%(avatar_path)s" alt="avatar"></img>
%(profile)s
</div>
<div>
<ul id="tiddlers" class="listing">
%(tiddlers)s
</div>
</ul>
"""



def add_profile_routes(selector):
    selector.add('/.well-known/host-meta', GET=host_meta)
    selector.add('/webfinger', GET=webfinger)
    selector.add('/profiles/{username}', GET=profile)


def profile(environ, start_response):
    http_host, host_url = determine_host(environ)
    if http_host != host_url:
        # Or should it be a 302?
        raise HTTP404('No profiles at this host: %s' % http_host)

    username = environ['wsgiorg.routing_args'][1]['username']
    current_user = environ['tiddlyweb.usersign']

    store = environ['tiddlyweb.store']

    try:
        user = store.get(User(username))
    except NoUserError:
        raise HTTP404('Profile not found for %s' % username)

    query_string_store = environ['QUERY_STRING']
    environ['QUERY_STRING'] = 'q=modified:%s' % username

    activity_feed = (space_uri(environ, username) +
            'search.atom?q=modifier:%s' % username)

    environ['tiddlyweb.links'] = [
           '<link rel="alternate" type="application/atom+xml" title="Atom activity feed" href="%s" />'
           % activity_feed]

    profile_tiddler = Tiddler('profile', '%s_public' % username)
    try:
        profile_tiddler = store.get(profile_tiddler)
    except StoreError, exc:
        raise HTTP404('No profile for %s: %s' % (username, exc))

    profile_text = render_wikitext(profile_tiddler, environ)

    tiddlers = store.search('modifier:cdent')
    tiddlers_list = []
    for tiddler in filter_tiddlers(tiddlers, 'sort=-modified;limit=20'):
        tiddlers_list.append('<li><a href="/bags/%s/tiddlers/%s">%s</a></li>'
                % (encode_name(tiddler.bag), encode_name(tiddler.title),
                    tiddler.title))
    profile_tiddlers = '\n'.join(tiddlers_list)

    avatar_path = '/recipes/%s_public/tiddlers/SiteIcon' % username

    start_response('200 OK', [
        ('Content-Type', 'text/html; charset=UTF-8')])

    environ['tiddlyweb.title'] = 'Profile for %s' % username
    environ['QUERY_STRING'] = query_string_store
    return [PROFILE_TEMPLATE % {'username': username,
        'avatar_path': avatar_path,
        'profile': profile_text, 'tiddlers': profile_tiddlers,
        'server_host': server_base_url(environ)}]


def host_meta(environ, start_response):
    http_host, host_url = determine_host(environ)
    if http_host != host_url:
        # Or should it be a 302?
        raise HTTP404('No host-meta at this host: %s' % http_host)

    start_response('200 OK', [
        ('Content-Type', 'application/xrd+xml')
        ])

    return [HOST_META_TEMPLATE % {'host': http_host, 'server_host':
        server_base_url(environ)}]


def webfinger(environ, start_response):
    http_host, host_url = determine_host(environ)
    if http_host != host_url:
        # Or should it be a 302?
        raise HTTP404('No webfinger at this host: %s' % http_host)

    username = environ['tiddlyweb.query'].get('q', [None])[0]

    if not username:
        raise HTTP400('No account provided to webfinger query')

    # XXX Do we validate user for existence at this stage of the game?
    if username.startswith('acct:'):
        username = username.split(':', 1)[1]
    username = username.split('@', 1)[0]

    start_response('200 OK', [
        ('Content-Type', 'application/xrd+xml')
        ])

    return [WEBFINGER_TEMPLATE % {'username': username,
        'host': http_host, 'server_host': server_base_url(environ)}]
