#!/usr/bin/python2.7
from bottle import route, post, default_app, request, redirect, static_file, get
import bottle
import os
from command_line import *
import mimetypes
import json
import pygithub3
from urllib import quote
from requests import HTTPError
from pull_request import *
import time
import threading
import traceback
import StringIO

__file__, local_dir = get_local_dir(globals())

REPOSITORIES_FOLDER = './repositories'
repositories_folder = os.path.abspath(os.path.join(local_dir, REPOSITORIES_FOLDER))

def configuration():
    with inDirectory(local_dir):
        return json.load(open('config.json'))

def github():
    config = configuration()
    return pygithub3.Github(login=config['user_name'], password=config['password'])

@route('/')
def root():
    s = '''<html><body><div style="margin:auto"><h1>Repositories</h1>
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
PUSH_REMOTE = 'remote_push'
PULL_REMOTE = 'remote_pull'
checkout_base_branch = git.checkout(BASE_BRANCH)
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
        assert request.method == 'GET'
        filepath = 'index.html'
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
    if filepath.endswith('/') or not filepath:
        filepath += 'index.html'
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


def traceback_for_html():
    file = StringIO.StringIO()
    traceback.print_exc(file = file)
    return '<pre class="PythonTraceback">\r\n' + file.getvalue() + '</pre>'

def _create_pull_request(branch, repository, filepath):
    _commit_changes(filepath)
    repository_url = quote(build_url_branch_repo_path(branch, repository, filepath), safe = u':/')
    pull_request = PullRequest.from_request(branch, repository, PUSH_REMOTE, repository_url)
    try:
        pull_request_url = pull_request.create_on_github(github()).view_github_html_url
    except Exception as e:
        # https://github.com/openpullrequests/spiele-mit-kindern/tree/autobranch6
        # todo: add pull request as unfulfilled
        pushed_branch_link = pull_request.pushed_branch_link
        if isinstance(e, HTTPError):
            error = ''
        else:
            error = traceback_for_html()
        return """
            <html><body><div style="margin:auto">
                <h1>Anfrage konnte noch nicht gestellt werden</h1>
                Ich werde es jetzt von Zeit zu Zeit nochmal versuchen.<br />
                <a href="{}">Hochgeladenes ansehen</a><br />
                <a href="{}">Zur&uuml;ck zur Webseite</a><br />
                <a href="/retry_pull_requests">Nochmal versuchen</a><br />
                Github meldet: <div class="GithubError">{}</div>
            </div>
            {}
            </body></html>""".format(pushed_branch_link, repository_url, e, error)
    pull_request_url = quote(pull_request_url, safe = u':/')
    return """
        <html><body><div style="margin:auto">
            <h1>Eine Anfrage wurde erstellt</h1>
            <a href="{}">Anfrage ansehen</a><br />
            <a href="{}">Zur&uuml;ck zur Webseite</a><br />
        </div></body></html>""".format(pull_request_url, repository_url)


@post('/pull/<repository>/')
@post('/pull/<repository>')
def github_repo_has_changed_hook(repository):
    check_repository(repository)
    with inRepository(repository):
        checkout_base_branch()
        text = git.pull(PULL_REMOTE, BASE_BRANCH)()
    return '''<html><body><div style="margin:auto"><h1>Repository successfully updated</h1>
                <p>from remote <strong>{}</strong></p><p>{}</p></div></body></html>'''.format(PULL_REMOTE, text.replace('\n', '\n<br />'))

@get('/I_am_here.js')
def get_niccokunzmann_pythonanywhere():
    return static_file('I_am_here.js', root = local_dir)

I_need_an_update = False
@post('/update')
def pull_own_source_code():
    global I_need_an_update
    I_need_an_update= True
    return '''<html><body><div style="margin:auto">Okay, Ich wei&szlig;, dass ich ein Update brauche.<br />
              <a href="/update">Update mich!</a></div></body></html>'''

@get('/update/')
@get('/update')
def my_sources_have_changed():
    with inDirectory(local_dir):
        text = git.pull()
    return '''<html><body><div style="margin:auto"><h1>Ich bin wieder up-to-date!</h1>
                <p><a href="https://www.pythonanywhere.com/user/niccokunzmann/webapps/">Starte mich neu!</a>
                </p><p>{}</p></div></body></html>'''.format(text.replace('\n', '\n<br />'))

@get('/retry_pull_requests')
def retry_all_failed_pull_requests():
    pull_requests = PullRequest.all_failed()
    failed = []
    succeeded = []
    for pull_request in pull_requests:
        try:
            with inRepository(pull_request.repository):
                git.checkout(pull_request.branch)()
                github_pull_request = pull_request.create_on_github(github())
        except HTTPError as error:
            failed.append((pull_request, error, ''))
        except Exception as error:
            failed.append((pull_request, error, traceback_for_html()))
        else:
            succeeded.append((pull_request, github_pull_request))
    succeeded_string = ''
    for pull_request, github_pull_request in succeeded:
        succeeded_string += '\n        <li><a href="{}">Zu Github</a> <a href="{}">Zur Webseite</a></li>'.format(
            github_pull_request.view_github_html_url, pull_request.repository_url)
    failed_string = ''
    for pull_request, error, tb in failed:
        failed_string += '''\n         <li><a href="{}">Zu Github</a> <a href="{}">Zur Webseite</a>
                                         Github meldet: <div class="GithubError">{}</div>
                                         {}
                                       </li>'''.format(
            pull_request.pushed_branch_link, pull_request.repository_url, error, tb)
    return """<html><body><div style="margin:auto"><h1>Offene Anfragen</h1>
    Diese Anfragen waren soeben erfolgreich:
    <ul>
        {}
    </ul>
    Diese Anfragen stehen noch aus:
    <ul>
        {}
    </ul>
</div></body></html>""".format(succeeded_string, failed_string)

last_retry_all_failed_pull_requests = time.time()
seconds_between_last_retry_all_failed_pull_requests = 60 * 60

def retry_all_failed_pull_requests_thread():
    global last_retry_all_failed_pull_requests
    while 1:
        while time.time() < last_retry_all_failed_pull_requests + seconds_between_last_retry_all_failed_pull_requests:
            time.sleep(1)
        print 'retrying all pull requests'
        try:
            retry_all_failed_pull_requests()
        except:
            traceback.print_exc()
        last_retry_all_failed_pull_requests = time.time()

thread = threading.Thread(target = retry_all_failed_pull_requests_thread)
thread.daemon = True
thread.start()

mimetypes.add_type('text/html; charset=UTF-8', '.html')
mimetypes.add_type('text/html; charset=UTF-8', '.htm')

application = default_app()

if __name__ == '__main__':
    from bottle import run
    run(host='localhost', port=8000, debug=True)
