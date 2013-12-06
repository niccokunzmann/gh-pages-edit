#!/usr/bin/python2.7
from bottle import route, post, default_app, request, redirect, static_file, get
import bottle
import os
from command_line import *
import mimetypes
import json
import pygithub3
from urllib import quote
import urlparse
from requests import HTTPError

try:
    __file__
except NameError:
    local_dir = os.getcwd()
    __file__ = os.path.join(local_dir, 'bottle_app.py')
else:
    # f***ing git shell
    __file__ = os.path.abspath(__file__)
    local_dir = os.path.join(__file__, '..')

REPOSITORIES_FOLDER = './repositories'
repositories_folder = os.path.abspath(os.path.join(local_dir, REPOSITORIES_FOLDER))

def configuration():
    with inDirectory(local_dir):
        print os.getcwd(), local_dir
        return json.load(open('config.json'))

@DoUndo
def inDirectory(directory):
    here = os.getcwd()
    os.chdir(os.path.abspath(directory))
    yield
    os.chdir(here)

@route('/')
def root():
    s = '''<html><body><div align="center"><h1>Repositories</h1>
    <p>Hier siehts Du eine Liste bereitgestellter Repositories:<ul>'''
    for repository in os.listdir(repositories_folder):
        if not os.path.isdir(repository_to_path(repository)): continue
        s += '<li><a href="{}">{}</a></li>'.format('/repo/' + repository, repository)
    s += '</ul></p>'
    if I_need_an_update:
        s += '<p><a href="/update">Ich brauche ein Update! Huhu k&uuml;mmere Dich um mich!</a></p>'
    s += '''</div></body></html>'''
    return s

def urljoin(*parts):
    return '/'.join(parts)
    
bottle.debug(True)
BASE_BRANCH = 'gh-pages'
PUSH_LOCATION = 'remote_push'
PULL_LOCATION = 'remote_pull'
base_branch = BASE_BRANCH
checkout_base_branch = git.checkout(base_branch)
repository_to_path = lambda repository: os.path.join(repositories_folder, repository)
inRepository = lambda repository: inDirectory(repository_to_path(repository))

def check_filepath(repository, filepath):
    # from bottle static_file line 2073
    with inRepository(repository):
        absolute_filepath = os.path.abspath(filepath)
    assert absolute_filepath.startswith(os.path.abspath(repository_to_path(repository)))

def check_repository(repository):
    assert repository in os.listdir(repositories_folder)

def _repository_content(repository, filepath = ''):
    if filepath.endswith('/') or not filepath:
        filepath += 'index.html'
        return redirect(filepath)
    return static_file(filepath, root=repository_to_path(repository))

@get('/branch/<branch>/<repository>/')
@get('/branch/<branch>/<repository>/<filepath:path>')
def commit_repository_content(branch, repository, filepath = ''):
    check_repository(repository)
    with inRepository(repository):
        with stash():
            git.checkout(branch)()
            return _repository_content(repository, filepath)

@post('/branch/<branch>/<repository>/')
@post('/branch/<branch>/<repository>/<filepath:path>')
def change_repository_content(branch, repository, filepath = ''):
    check_repository(repository)
    check_filepath(repository, filepath)
    with inRepository(repository):
        with stash():
            git.checkout(branch)()
            return _change_repository_content(branch, repository, filepath)

def _commit_changes(filepath):
    comment = request.forms.get('comment')
    sourcecode = request.forms.get('sourceCode')
    with open(filepath, 'wb') as file:
        file.write(sourcecode)
    git.add(filepath)()
    try: git.commit('-m', comment)()
    except CalledProcessError as e:
        if 'nothing to commit, working directory clean' not in e.output:
            raise
    

def _change_repository_content(branch, repository, filepath):
    _commit_changes(filepath)
    return redirect('/branch/{}/{}/{}'.format(branch, repository, filepath))

@post('/repo/<repository>/')
@post('/repo/<repository>/<filepath:path>')
def change_repository_content(repository, filepath = ''):
    check_repository(repository)
    check_filepath(repository, filepath)
    with inRepository(repository):
        with stash():
            checkout_base_branch()
            branch = new_branch()
            return _change_repository_content(branch, repository, filepath)

@route('/repo/<repository>')
def repository_and_no_directory(repository):
    return redirect('/repo/' + repository + '/')
@get('/repo/<repository>/')
@get('/repo/<repository>/<filepath:path>')
def default_repository_content(repository, filepath = ''):
    check_repository(repository)
    with inRepository(repository):
        with stash():
            checkout_base_branch()
            return _repository_content(repository, filepath)

def build_url_repo_path(repository, filepath = ''):
    return urljoin('/repo', repository, filepath)

def build_url_branch_repo_path(branch, repository, filepath = ''):
    return urljoin('/branch', branch, repository, filepath)

@post('/publish/repo/<repository>/')
@post('/publish/repo/<repository>/<filepath:path>')
def create_pull_request_from_repository(repository, filepath = ''):
    check_repository(repository)
    check_filepath(repository, filepath)
    with inRepository(repository):
        with stash():
            checkout_base_branch()
            branch = new_branch()
            return _create_pull_request(branch, repository, filepath)

@post('/publish/branch/<branch>/<repository>/')
@post('/publish/branch/<branch>/<repository>/<filepath:path>')
def create_pull_request_from_branch(branch, repository, filepath = ''):
    check_repository(repository)
    check_filepath(repository, filepath)
    with inRepository(repository):
        with stash():
            git.checkout(branch)()
            return _create_pull_request(branch, repository, filepath)

def _create_pull_request(branch, repository, filepath):
    _commit_changes(filepath)
    repository_url = quote(build_url_branch_repo_path(branch, repository, filepath), safe = u':/')
    try:
        pull_request_url = create_pull_request_on_server(branch)
    except HTTPError as e:
        return """
            <html><body><div align="center">
                <h1>Anfrage konnte nicht gestellt werden</h1>
                <a href="{}">Zur&uuml;ck zur Webseite</a><br />
                Github meldet: {}
            </div></body></html>""".format(repository_url, e)
    pull_request_url = quote(pull_request_url, safe = u':/')
    return """
        <html><body><div align="center">
            <h1>Eine Anfrage wurde erstellt</h1>
            <a href="{}">Anfrage ansehen</a><br />
            <a href="{}">Zur&uuml;ck zur Webseite</a><br />
        </div></body></html>""".format(pull_request_url, repository_url)

def github():
    config = configuration()
    return pygithub3.Github(login=config['user_name'], password=config['password'])

def create_pull_request_on_server(branch):
    global pullrequest
    git.push(PUSH_LOCATION, branch)() # http://stackoverflow.com/questions/1519006/git-how-to-create-remote-branch
    title = request.forms.get('title')
    body = request.forms.get('body')
    if not title:
        title = request.forms.get('comment').split('\n', 1)[0]
    if not body:
        body = request.forms.get('comment')
    commit = last_commit()
    pullrequest = github().pull_requests.create({
          "title": title,
          "body": body,
          "head": commit,
          "base": base_branch
        }, 'niccokunzmann', 'spiele-mit-kindern')
    return pullrequest.issue_url

@route('/pull/<repository>/')
@route('/pull/<repository>')
def github_repo_has_changed_hook(repository):
    check_repository(repository)
    with inRepository(repository):
        checkout_base_branch()
        text = git.pull(PULL_LOCATION, BASE_BRANCH)()
    return '''<html><body><div align="center"><h1>Repository successfully updated</h1>
                <p>from remote <strong>{}</strong></p><p>{}</p></div></body></html>'''.format(PULL_LOCATION, text.replace('\n', '\n<br />'))

@get('/I_am_here.js')
def get_niccokunzmann_pythonanywhere():
    return static_file('I_am_here.js', root = local_dir)

I_need_an_update = False
@post('/update')
def pull_own_source_code():
    global I_need_an_update
    I_need_an_update= True
    return '''<html><body><div align="center">Okay, Ich wei&szlig;, dass ich ein Update brauche.<br />
              <a href="/update">Update mich!</a></div></body></html>'''

@get('/update/')
@get('/update')
def my_sources_have_changed():
    with inDirectory(local_dir):
        text = git.pull()
    return '''<html><body><div align="center"><h1>Ich bin wieder up-to-date!</h1>
                <p><a href="https://www.pythonanywhere.com/user/niccokunzmann/webapps/">Starte mich neu!</a>
                </p><p>{}</p></div></body></html>'''.format(text.replace('\n', '\n<br />'))

mimetypes.add_type('text/html; charset=UTF-8', '.html')
mimetypes.add_type('text/html; charset=UTF-8', '.htm')

application = default_app()

if __name__ == '__main__':
    from bottle import run
    run(host='localhost', port=8000, debug=True)
