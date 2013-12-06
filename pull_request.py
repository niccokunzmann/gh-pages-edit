from command_line import last_commit, inDirectory
from bottle import request

def getter_setter(name):
    @property
    def get(self):
        return self.dict[name]
    @get.setter
    def set(self, value):
        self.dict[name] = value
    return set

class PullRequest(object):
    
    # loader functions
    file_name = 'open_pull_requests.json'

    @classmethod
    def _get_pull_request_dicts(cls):
        with inDirectory(local_dir):
            try:
                file = open(cls.file_name, 'rb')
            except IOError:
                return []
            return json.load(file)

    @classmethod
    def _save_pull_requests_dicts(pull_requests):
        with inDirectory(local_dir):
            return json.dump(pull_requests, open(cls.file_name, 'wb'), indent = '  ')

    # creation functions

    required_names = 'branch repository commit title body base_branch '\
            'target_repository_owner target_repository'.split()
    all_names = required_names + 'tries'.split()
    identity_names = ['commit']

    instances = []
    initialized = False

    def __new__(cls, dict = {}, **kw):
        assert set(dict) & set(kw) == set()
        _dict = {}
        _dict.update(dict)
        _dict.update(kw)
        obj = object.__new__(cls, dict, **kw)
        obj.dict = _dict
        instances = cls.instances
        if obj in instances:
            return instances[instances.index(obj)]
        instances.append(obj)
        return obj

    def __init__(self, dict = {}, **kw):
        if not self.initialized:
            self.initialized = True
            self.tries = 0

    @classmethod
    def from_request(cls, branch, repository):
        """create a pull request from the request to the bottle server"""
        title = request.forms.get('title')
        body = request.forms.get('body')
        if not title:
            title = request.forms.get('comment').split('\n', 1)[0]
        if not body:
            body = request.forms.get('comment')
        commit = last_commit()
        return cls(branch = branch, repository = repository,
                   commit = commit, title = title, body = body,
                   base_branch = 'gh-pages',
                   target_repository_owner = 'niccokunzmann',
                   target_repository = 'spiele-mit-kindern')

    @classmethod
    def to_do(cls):
        return list(map(cls, self._get_pull_request_dicts()))

    # github functions
    
    def create_on_github(self, github):
        with inRepository(self.repository):
            git.checkout(self.branch)()
            # http://stackoverflow.com/questions/1519006/git-how-to-create-remote-branch
            git.push(PUSH_LOCATION, branch)()
        try:
            pull_request = github.pull_requests.create({
                  "title": self.title,
                  "body": self.body,
                  "head": self.commit,
                  "base": self.base_branch
                }, self.target_repository_owner, self.target_repository)
        except:
            self.github_failed()
        else:
            self.github_successful()
        return pull_request

    def github_successful(self):
        list = self.to_do()
        while self in list:
            list.remove(self)
        self._save_todo(list)

    def github_failed(self):
        self.one_more_try()

    # other functions
    
    def one_more_try(self):
        self.tries += 1

    def __eq__(self, other):
        for name in self.identity_names:
            if self.dict[name] != other.dict[name]:
                return False
        return True


for name in PullRequest.all_names:
    setattr(PullRequest, name, getter_setter(name))

__all__ = ['PullRequest']


if __name__ == '__main__':
    p1 = PullRequest(branch = 1, repository = 2, 
                   commit = 'ad', title = '', body = '',
                   base_branch = '',
                   target_repository_owner = 'niccokunzmann',
                   target_repository = 'spiele-mit-kindern')
    p2 = PullRequest(branch = 1, repository = 2, 
                   commit = 'af', title = '', body = '',
                   base_branch = '',
                   target_repository_owner = 'niccokunzmann',
                   target_repository = 'spiele-mit-kindern')

    p3 = PullRequest(branch = 1, repository = 2, 
                   commit = 'af', title = '', body = '',
                   base_branch = '',
                   target_repository_owner = '',
                   target_repository = 'spiele-mit-kindern')
    assert p3 == p2
    assert p3 is p2
    assert p3.target_repository_owner == 'niccokunzmann'
