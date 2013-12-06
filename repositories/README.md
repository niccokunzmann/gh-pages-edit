Repositories
============

This is the location where the repositories shall be put.
Each repository has 2 remotes at least:

-	`remote_push`: where to push to and create pull requests from 
- 	`remote_pull`: where to pull new code from. It is usually the same as `origin`.

[openpullrequests](https://github.com/openpullrequests) must be contributor to the project you push to.

New Repository
--------------

First get the repository

	$ git clone https://github.com/niccokunzmann/spiele-mit-kindern.git

The `cd` into the repository:

	cd spiele-mit-kindern

When you see something like this:

	$ git config -l
	...
	remote.origin.url=https://github.com/niccokunzmann/spiele-mit-kindern.git
	remote.origin.fetch=+refs/heads/*:refs/remotes/origin/*
	...

those remotes must be added

	$ git remote add remote_pull https://github.com/niccokunzmann/spiele-mit-kindern.git
	$ git remote add remote_push git@github.com:openpullrequests/spiele-mit-kindern.git

and that should be all.