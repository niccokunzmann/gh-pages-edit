from bottle import route, post, default_app, request, redirect, static_file, get
import bottle
import os
from command_line import *
import mimetypes
import json
import pygithub3

try:
    __file__
except NameError:
    __file__ = os.path.join(os.getcwd(), 'bottle_app.py')
local_dir = os.path.dirname(__file__)



REPOSITORIES_FOLDER = './repositories'
repositories_folder = os.path.join(local_dir, REPOSITORIES_FOLDER)

def configuration():
    return json.load(open('config.txt'))

@DoUndo
def inDirectory(directory):
    here = os.getcwd()
    os.chdir(os.path.abspath(directory))
    yield
    os.chdir(here)

@route('/')
def root():
    redirect('/repo/spiele-mit-kindern/')
    
bottle.debug(True)

base_branch = 'gh-pages'
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
        filepath = filepath + 'index.html'
        return redirect(repository + '/' + filepath)
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
    git.commit('-m', comment)()

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


@get('/repo/<repository>')
def repository_and_no_directory(repository):
    redirect('/repo/' + repository + '/')
@get('/repo/<repository>/')
@get('/repo/<repository>/<filepath:path>')
def default_repository_content(repository, filepath = ''):
    check_repository(repository)
    with inRepository(repository):
        with stash():
            checkout_base_branch()
            return _repository_content(repository, filepath)

@post('/publish/<repository>/')
@post('/publish/<repository>/<filepath:path>')
def change_repository_content(repository, filepath = ''):
    check_repository(repository)
    check_filepath(repository, filepath)
    with inRepository(repository):
        with stash():
            branch = new_branch()
            _commit_changes(filepath)
            create_pull_request(branch)

def github():
    config = configuration()
    return pygithub3.Github(login=config['username'], password=config['password'])

def create_pull_request(branch):
    global pullrequest
    git.push(branch, branch)() # http://stackoverflow.com/questions/1519006/git-how-to-create-remote-branch
    title = request.forms.get('title')
    body = request.forms.get('body')
    pullrequest = github().pull_requests.create({
          "title": title,
          "body": body,
          "head": branch,
          "base": base_branch
        }, 'niccokunzmann', 'spiele-mit-kindern')
    
    



mimetypes.add_type('text/html; charset=UTF-8', '.html')
mimetypes.add_type('text/html; charset=UTF-8', '.htm')

application = default_app()

if __name__ == '__main__':
    from bottle import run
    run(host='localhost', port=8080, debug=True)
