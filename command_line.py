import subprocess
import os

class CalledProcessError(subprocess.CalledProcessError):
    def __str__(self):
        return subprocess.CalledProcessError.__str__(self) + '\noutput:\n' + self.output

def check_output(commands, **kw):
    commands = list(commands)
    print 'check_output:', commands
    p = subprocess.Popen(commands, stderr = subprocess.PIPE,
                         stdout = subprocess.PIPE, stdin = subprocess.PIPE)
    out, err = p.communicate(**kw)
    ret = p.wait()
    if ret:
        raise CalledProcessError(ret, commands, out + err)
    return out

class Command(object):
    def __init__(self, command = []):
        self.command = command
        self.called = False

    def __del__(self):
        if not self.called:
            print 'not called: {}'.format(' '.join(self.command))

    def __call__(self, *args):
        self.called = True
        if not args:
            return check_output(self.command)
        else:
            return self.__class__(self.command + list(args))

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return self(name)

def command_function(function):
    def command_function1(given_arguments):
        def command_function2(*args):
            if len(args) == 0:
                return function(*given_arguments)
            return command_function1(given_arguments + args)
        command_function2.__module__ = function.__module__
        command_function2.__name__ = function.__name__
        return command_function2
    return command_function1(())

_git = Command().git
git = Command().git

last_checkout = None
last_checkout_return_value = None
@command_function
def _checkout(commit):
    global last_checkout, last_checkout_return_value
    if commit != last_checkout:
        last_checkout_return_value = _git.checkout(commit)()
    last_checkout = commit
    return last_checkout_return_value
git.checkout = _checkout

def last_commit():
    return git('rev-list', '--parents', 'HEAD')().split()[0]

def new_branch(prefix = 'autobranch'):
    'create a new branch and return the name'
    number_of_branches = len(git.branch('-la')().split('\n')) # all branches
    branch_name = prefix + str(number_of_branches)
    _git.checkout('-b', branch_name)()
    return branch_name

class DoUndo(object):

    class DoUndoWith(object):
        def __init__(self, function, args, kw):
            self.function = function
            self.args = args
            self.kw = kw

        def __enter__(self):
            self.generator = self.function(*self.args, **self.kw)
            for has_value in self.generator:
                break

        def __exit__(self, *args):
            for has_value in self.generator:
                raise ValueError('Generator should have exited')

    def __init__(self, function):
        self.function = function

    def __call__(self, *args, **kw):
        return self.DoUndoWith(self.function, args, kw)

@DoUndo
def stash():
##    output = git.stash()
    yield
##    if 'No local changes to save'.lower() not in output.splitlines()[0].lower():
##        git.stash.pop()


@DoUndo
def inDirectory(directory):
    here = os.getcwd()
    os.chdir(os.path.abspath(directory))
    yield
    os.chdir(here)

def get_local_dir(globals):
    if '__file__' in globals:
        # f***ing git shell
        __file__ = os.path.abspath(globals['__file__'])
        local_dir = os.path.join(__file__, '..')
    else:
        local_dir = os.getcwd()
        __file__ = os.path.join(local_dir, globals['__name__'] + '.py')
    return __file__, local_dir
