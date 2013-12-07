from command_line import last_commit, inDirectory, get_local_dir, git
from bottle import request
import json
from requests import HTTPError

__file__, local_dir = get_local_dir(globals())

def getter_setter(name):
    @property
    def get(self):
        return self.dict[name]
    @get.setter
    def set(self, value):
        self.dict[name] = value
    return set

class FakeGithubPullRequest(object):
    issue_url = 'https://github.com/niccokunzmann/spiele-mit-kindern/pull/9'

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
            return json.load(file, encoding = 'UTF-8')

    @classmethod
    def _save_pull_requests_dicts(cls, pull_requests):
        with inDirectory(local_dir):
            return json.dump(pull_requests, open(cls.file_name, 'wb'),
                             indent = 2, encoding = 'UTF-8')

    # creation functions

    required_names = 'branch repository commit title body base_branch '\
            'target_repository_owner target_repository push_remote repository_url'.split()
    all_names = required_names + 'tries'.split()
    identity_names = ['commit']

    instances = []
    initialized = False

    def __new__(cls, dict = {}, **kw):
        assert set(dict) & set(kw) == set()
        _dict = {}
        _dict.update(dict)
        _dict.update(kw)
        for required_name in cls.required_names:
            assert required_name in _dict, required_name
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
    def from_request(cls, branch, repository, push_remote, repository_url):
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
                   target_repository = 'spiele-mit-kindern',
                   push_remote = push_remote, repository_url = repository_url)

    @classmethod
    def all_failed(cls):
        return list(map(cls, cls._get_pull_request_dicts()))

    # github functions
    
    def create_on_github(self, github):
        git.checkout(self.branch)()
        # http://stackoverflow.com/questions/1519006/git-how-to-create-remote-branch
        git.push(self.push_remote, self.branch + ':' + self.github_branch_name)()
        try:
            pull_request = github.pull_requests.create({
                  "title": self.title,
                  "body": self.body,
                  "head": self.commit,
                  "base": self.base_branch
                }, self.target_repository_owner, self.target_repository)
##            pull_request = FakeGithubPullRequest() # test positive case
##            raise HTTPError() # test negative case
        except:
            self.github_failed()
            raise 
        else:
            self.github_succeeded()
        return pull_request

    def github_succeeded(self):
        list = self.all_failed()
        while self in list:
            list.remove(self)
        self._save_failed(list)

    def github_failed(self):
        self.one_more_try()
        list = self.all_failed()
        while self in list:
            list.remove(self)
        list.append(self)
        self._save_failed(list)

    def _save_failed(cls, list):
        dicts = []
        for pull_request in list:
            dicts.append(pull_request.dict)
        cls._save_pull_requests_dicts(dicts)
        
    # other functions
    
    def one_more_try(self):
        self.tries += 1

    def __eq__(self, other):
        for name in self.identity_names:
            if self.dict[name] != other.dict[name]:
                return False
        return True

    def __hash__(self):
        return hash(self.commit)

    @property
    def github_branch_name(self):
        return 'pull_request_' + self.commit

    @property
    def pushed_branch_link(self):
        return 'https://github.com/openpullrequests/' + self.repository + '/tree/' + self.github_branch_name

for name in PullRequest.all_names:
    setattr(PullRequest, name, getter_setter(name))

__all__ = ['PullRequest']


if __name__ == '__main__':
    import os
    class TestPullReqest(PullRequest):
        file_name = 'test_open_pull_requests.json'
    if os.path.isfile(TestPullReqest.file_name):
        os.remove(TestPullReqest.file_name)
    p1 = TestPullReqest(branch = 1, repository = 2, 
                   commit = 'ad', title = '', body = '',
                   base_branch = '',
                   target_repository_owner = 'niccokunzmann',
                   target_repository = 'spiele-mit-kindern')
    p2 = TestPullReqest(branch = 1, repository = 2, 
                   commit = 'af', title = '', body = '',
                   base_branch = '',
                   target_repository_owner = 'niccokunzmann',
                   target_repository = 'spiele-mit-kindern')

    p3 = TestPullReqest(branch = 1, repository = 2, 
                   commit = 'af', title = '', body = '',
                   base_branch = '',
                   target_repository_owner = '',
                   target_repository = 'spiele-mit-kindern')
    assert p3 == p2
    assert p3 is p2
    assert p3.target_repository_owner == 'niccokunzmann'

    p1.github_failed()
    assert len(TestPullReqest.all_failed())
    assert p1 in TestPullReqest.all_failed()
    p2.github_failed()
    p1.github_succeeded()
    assert TestPullReqest.all_failed() == [p2]
    p1.github_failed()
    assert TestPullReqest.all_failed() == [p2, p1], TestPullReqest.all_failed()
